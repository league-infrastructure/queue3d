FROM python:3.12-slim

WORKDIR /app

# Install SOPS and age for runtime secret decryption
RUN apt-get update && apt-get install -y --no-install-recommends curl && \
    curl -Lo /usr/local/bin/sops https://github.com/getsops/sops/releases/download/v3.9.4/sops-v3.9.4.linux.amd64 && \
    chmod +x /usr/local/bin/sops && \
    curl -Lo /tmp/age.tar.gz https://github.com/FiloSottile/age/releases/download/v1.2.1/age-v1.2.1-linux-amd64.tar.gz && \
    tar -xzf /tmp/age.tar.gz -C /tmp && \
    mv /tmp/age/age /usr/local/bin/age && \
    mv /tmp/age/age-keygen /usr/local/bin/age-keygen && \
    rm -rf /tmp/age /tmp/age.tar.gz && \
    apt-get purge -y curl && apt-get autoremove -y && rm -rf /var/lib/apt/lists/*

COPY --from=ghcr.io/astral-sh/uv:latest /uv /usr/local/bin/uv

COPY pyproject.toml uv.lock ./
RUN uv sync --frozen --no-dev

COPY app/ app/
COPY secrets/ secrets/
COPY .sops.yaml .
COPY entrypoint.sh .
RUN chmod +x entrypoint.sh

RUN mkdir -p data/uploads

EXPOSE 8000

ENTRYPOINT ["./entrypoint.sh"]
CMD ["uv", "run", "uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
