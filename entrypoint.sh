#!/bin/bash
set -e

# Assemble the runtime .env from the dotconfig-managed config/ tree.
# Public values live in config/<deploy>/public.env (plaintext); secrets live
# in config/<deploy>/secrets.env (SOPS/age-encrypted). Secrets are appended
# after public so they win on any key conflict (dotconfig last-write order).
DEPLOY="${DEPLOY:-prod}"

if [ -n "$SOPS_AGE_KEY" ] && [ -d "config/$DEPLOY" ]; then
    echo "Assembling '$DEPLOY' config from config/ ..."
    : > .env
    [ -f "config/$DEPLOY/public.env" ] && cat "config/$DEPLOY/public.env" >> .env
    [ -f "config/$DEPLOY/secrets.env" ] && sops -d "config/$DEPLOY/secrets.env" >> .env
elif [ -f .env ]; then
    echo "Using existing .env file"
else
    echo "WARNING: No config found. Set SOPS_AGE_KEY or provide .env"
fi

exec "$@"
