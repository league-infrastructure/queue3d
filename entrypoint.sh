#!/bin/bash
set -e

# Decrypt production secrets using SOPS + age
if [ -n "$SOPS_AGE_KEY" ] && [ -f secrets/prod.env ]; then
    echo "Decrypting production secrets..."
    sops -d secrets/prod.env > .env
elif [ -f .env ]; then
    echo "Using existing .env file"
else
    echo "WARNING: No secrets found. Set SOPS_AGE_KEY or provide .env"
fi

exec "$@"
