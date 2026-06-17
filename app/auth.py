import re
import secrets

from authlib.integrations.starlette_client import OAuth
from fastapi import APIRouter, Depends, Form, Request
from fastapi.responses import RedirectResponse
from sqlalchemy.orm import Session

from app.config import settings
from app.database import get_db
from app.models import SessionPassphrase, User, _utcnow
from app.utils.passphrase import ensure_utc, normalize

router = APIRouter(prefix="/auth", tags=["auth"])

oauth = OAuth()

oauth.register(
    name="google",
    client_id=settings.GOOGLE_CLIENT_ID,
    client_secret=settings.GOOGLE_CLIENT_SECRET,
    server_metadata_url="https://accounts.google.com/.well-known/openid-configuration",
    client_kwargs={"scope": "openid email profile"},
)

oauth.register(
    name="github",
    client_id=settings.GITHUB_CLIENT_ID,
    client_secret=settings.GITHUB_CLIENT_SECRET,
    authorize_url="https://github.com/login/oauth/authorize",
    access_token_url="https://github.com/login/oauth/access_token",
    api_base_url="https://api.github.com/",
    client_kwargs={"scope": "user:email"},
)


def _is_league_domain(email: str) -> bool:
    """True if email is from jointheleague.org or any subdomain."""
    domain = email.rsplit("@", 1)[-1].lower()
    return domain == "jointheleague.org" or domain.endswith(".jointheleague.org")


def _determine_admin(email: str) -> bool:
    """Admin if @jointheleague.org exactly (not any subdomain)."""
    return email.lower().endswith("@jointheleague.org") and "." not in email.lower().rsplit("@", 1)[-1].replace("jointheleague.org", "")


def _upsert_user(
    db: Session,
    *,
    email: str,
    display_name: str,
    avatar_url: str | None,
    provider: str,
    provider_id: str,
) -> User:
    user = db.query(User).filter(User.email == email).first()
    if user:
        user.display_name = display_name
        user.avatar_url = avatar_url
        user.last_login = _utcnow()
        user.is_admin = _determine_admin(email)
    else:
        user = User(
            email=email,
            display_name=display_name,
            avatar_url=avatar_url,
            provider=provider,
            provider_id=str(provider_id),
            is_admin=_determine_admin(email),
            is_approved=_is_league_domain(email),
            last_login=_utcnow(),
        )
        db.add(user)
    db.commit()
    db.refresh(user)
    return user


# --- User login (Google + GitHub) ---

@router.get("/login/google")
async def login_google(request: Request):
    redirect_uri = f"{settings.EXTERNAL_URL}/auth/callback/google"
    return await oauth.google.authorize_redirect(request, redirect_uri)


@router.get("/callback/google")
async def callback_google(request: Request, db: Session = Depends(get_db)):
    token = await oauth.google.authorize_access_token(request)
    userinfo = token.get("userinfo", {})
    if not userinfo:
        userinfo = await oauth.google.userinfo(token=token)

    user = _upsert_user(
        db,
        email=userinfo["email"],
        display_name=userinfo.get("name", userinfo["email"]),
        avatar_url=userinfo.get("picture"),
        provider="google",
        provider_id=userinfo["sub"],
    )
    request.session["user_id"] = user.id
    return RedirectResponse(url="/", status_code=302)


@router.get("/login/github")
async def login_github(request: Request):
    redirect_uri = f"{settings.EXTERNAL_URL}/auth/callback/github"
    return await oauth.github.authorize_redirect(request, redirect_uri)


@router.get("/callback/github")
async def callback_github(request: Request, db: Session = Depends(get_db)):
    token = await oauth.github.authorize_access_token(request)

    resp = await oauth.github.get("user", token=token)
    profile = resp.json()

    # GitHub may not include email in profile; fetch from emails endpoint
    email = profile.get("email")
    if not email:
        emails_resp = await oauth.github.get("user/emails", token=token)
        emails = emails_resp.json()
        primary = next((e for e in emails if e.get("primary") and e.get("verified")), None)
        if primary:
            email = primary["email"]
        elif emails:
            email = emails[0]["email"]

    if not email:
        return RedirectResponse(url="/auth/login?error=no_email", status_code=302)

    user = _upsert_user(
        db,
        email=email,
        display_name=profile.get("name") or profile.get("login", email),
        avatar_url=profile.get("avatar_url"),
        provider="github",
        provider_id=str(profile["id"]),
    )
    request.session["user_id"] = user.id
    return RedirectResponse(url="/", status_code=302)


# --- Admin login (Google only, jointheleague.org) ---

@router.get("/login/admin/google")
async def login_admin_google(request: Request):
    redirect_uri = f"{settings.EXTERNAL_URL}/auth/callback/admin/google"
    return await oauth.google.authorize_redirect(request, redirect_uri)


@router.get("/callback/admin/google")
async def callback_admin_google(request: Request, db: Session = Depends(get_db)):
    token = await oauth.google.authorize_access_token(request)
    userinfo = token.get("userinfo", {})
    if not userinfo:
        userinfo = await oauth.google.userinfo(token=token)

    email = userinfo["email"]
    if not _determine_admin(email):
        return RedirectResponse(
            url="/auth/login?error=Admin+login+requires+a+jointheleague.org+account",
            status_code=302,
        )

    user = _upsert_user(
        db,
        email=email,
        display_name=userinfo.get("name", email),
        avatar_url=userinfo.get("picture"),
        provider="google",
        provider_id=userinfo["sub"],
    )
    request.session["user_id"] = user.id
    return RedirectResponse(url="/", status_code=302)


# --- Student login (session passphrase) ---

def _slug(name: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-")
    return slug or "student"


@router.post("/login/passphrase")
async def login_passphrase(
    request: Request,
    name: str = Form(...),
    passphrase: str = Form(...),
    db: Session = Depends(get_db),
):
    name = name.strip()
    if not name:
        return RedirectResponse(
            url="/auth/login?error=Please+enter+your+name", status_code=303
        )

    active = (
        db.query(SessionPassphrase)
        .filter(SessionPassphrase.is_active == True)
        .order_by(SessionPassphrase.created_at.desc())
        .first()
    )
    if (
        not active
        or ensure_utc(active.expires_at) <= _utcnow()
        or normalize(passphrase) != normalize(active.phrase)
    ):
        return RedirectResponse(
            url="/auth/login?error=That+passphrase+is+not+valid+or+has+expired",
            status_code=303,
        )

    # Each passphrase login mints a lightweight, ephemeral student identity.
    # The synthesized email only satisfies the NOT NULL + unique constraint;
    # display_name (the entered name) is what shows on the queue.
    user = User(
        email=f"{_slug(name)}-{secrets.token_hex(4)}@session.local",
        display_name=name[:80],
        avatar_url=None,
        provider="passphrase",
        provider_id=secrets.token_hex(8),
        is_admin=False,
        is_approved=True,
        last_login=_utcnow(),
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    request.session["user_id"] = user.id
    return RedirectResponse(url="/", status_code=303)


@router.get("/logout")
async def logout(request: Request):
    request.session.clear()
    return RedirectResponse(url="/auth/login", status_code=302)
