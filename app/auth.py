from authlib.integrations.starlette_client import OAuth
from fastapi import APIRouter, Depends, Request
from fastapi.responses import RedirectResponse
from sqlalchemy.orm import Session

from app.config import settings
from app.database import get_db
from app.models import User, _utcnow

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


def _determine_admin(email: str) -> bool:
    """Admin if @jointheleague.org but NOT @students.jointheleague.org."""
    if email.endswith("@students.jointheleague.org"):
        return False
    if email.endswith("@jointheleague.org"):
        return True
    return False


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
            last_login=_utcnow(),
        )
        db.add(user)
    db.commit()
    db.refresh(user)
    return user


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


@router.get("/logout")
async def logout(request: Request):
    request.session.clear()
    return RedirectResponse(url="/auth/login", status_code=302)
