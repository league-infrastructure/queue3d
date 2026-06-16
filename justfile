# Queue3D task runner. Run `just` to list recipes.

# Developer name for local config overrides (config/local/<user>/).
user := "eric"

# List available recipes.
default:
    @just --list

# Run the development server: assemble .env from config/dev, then reload.
dev:
    dotconfig load -d dev -l {{user}}
    uv run uvicorn app.main:app --reload --host 0.0.0.0 --port 8100

# Run the server without auto-reload.
run:
    uv run uvicorn app.main:app --host 0.0.0.0 --port 8100

# Run the test suite.
test:
    uv run --extra dev pytest tests/ -v

# Lint.
lint:
    uv run --extra dev ruff check app/ tests/

# Initialize the database.
init-db:
    uv run python -c "from app.database import init_db; init_db()"

# Build and start the production stack (secrets decrypted in-container via SOPS_AGE_KEY).
deploy:
    SOPS_AGE_KEY="$(cat $SOPS_AGE_KEY_FILE)" docker compose up -d --build

# Stop the stack.
down:
    docker compose down

# Stop the stack and remove volumes + images.
destroy:
    docker compose down -v --rmi all

# Tail container logs.
logs:
    docker compose logs -f
