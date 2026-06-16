.PHONY: dev run load-dev load-prod save edit-dev edit-prod audit test lint init-db deploy down destroy logs

dev:
	uv run uvicorn app.main:app --reload --host 0.0.0.0 --port 8100

run:
	uv run uvicorn app.main:app --host 0.0.0.0 --port 8100

# --- dotconfig-managed environment configuration ---
# Source of truth: config/ (per-deploy public.env + SOPS-encrypted secrets.env).
DEV_USER ?= eric

# Assemble .env for local development (dev deploy + your local overrides).
load-dev:
	dotconfig load -d dev -l $(DEV_USER) --no-export

# Assemble .env for production.
load-prod:
	dotconfig load -d prod --no-export

# Round-trip .env edits back to config/ (re-encrypts secrets via SOPS).
save:
	dotconfig save

# Edit dev config: load, open .env in $$EDITOR, then save back.
edit-dev:
	dotconfig load -d dev -l $(DEV_USER) --no-export && $${EDITOR:-vi} .env && dotconfig save

# Edit prod config: load, open .env in $$EDITOR, then save back.
edit-prod:
	dotconfig load -d prod --no-export && $${EDITOR:-vi} .env && dotconfig save

# Verify no plaintext secrets are stored under config/.
audit:
	dotconfig audit

test:
	uv run pytest tests/ -v

lint:
	uv run ruff check app/ tests/

init-db:
	uv run python -c "from app.database import init_db; init_db()"

deploy:
	SOPS_AGE_KEY="$$(cat $(SOPS_AGE_KEY_FILE))" docker compose up -d --build

down:
	docker compose down

destroy:
	docker compose down -v --rmi all

logs:
	docker compose logs -f
