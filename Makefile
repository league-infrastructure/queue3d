.PHONY: dev run decrypt decrypt-prod test lint init-db deploy down destroy logs

dev:
	uv run uvicorn app.main:app --reload --host 0.0.0.0 --port 8100

run:
	uv run uvicorn app.main:app --host 0.0.0.0 --port 8100

decrypt-dev:
	sops -d secrets/dev.env > .env

decrypt-prod:
	sops -d secrets/prod.env > .env

encrypt-dev:
	cp .env secrets/dev.env && sops -e -i secrets/dev.env

encrypt-prod:
	cp .env secrets/prod.env && sops -e -i secrets/prod.env

edit-secrets-dev:
	sops secrets/dev.env

edit-secrets-prod:
	sops secrets/prod.env

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
