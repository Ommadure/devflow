#!/usr/bin/env bash
# Phase 1 exit check: drive the whole auth flow against a running API with curl.
#   docker compose up -d && cd backend && uv run alembic upgrade head
#   uv run uvicorn app.main:app      (in another terminal)
#   ./scripts/smoke_auth.sh [http://localhost:8000]
set -euo pipefail

API="${1:-http://localhost:8000}/api/v1"
JAR="$(mktemp)"
trap 'rm -f "$JAR"' EXIT
EMAIL="smoke-$(date +%s)@example.com"
PASSWORD="Smoke-Test-Pass-1"
NEW_PASSWORD="Smoke-Test-Pass-2"
ORIGIN="http://localhost:5173"

step() { printf '\n\033[1m%s\033[0m\n' "$1"; }
token() { python3 -c 'import json,sys; print(json.load(sys.stdin)["access_token"])'; }
# The API sets a Secure cookie; curl only sends those over https, so read it from the jar.
cookie() { awk '$6 == "devflow_refresh" { print $7 }' "$JAR"; }
refresh() {
  curl -sS -o /dev/null -w '%{http_code}' -X POST "$API/auth/refresh" \
    -H "Origin: $ORIGIN" -H "Cookie: devflow_refresh=$1"
}

step "1. register $EMAIL"
ACCESS=$(curl -sSf -c "$JAR" -X POST "$API/auth/register" -H 'Content-Type: application/json' \
  -d "{\"email\":\"$EMAIL\",\"password\":\"$PASSWORD\"}" | token)
echo "access token: ${ACCESS:0:24}…"

step "2. GET /me"
curl -sSf "$API/me" -H "Authorization: Bearer $ACCESS"; echo

step "3. log in again"
curl -sSf -c "$JAR" -X POST "$API/auth/login" -H 'Content-Type: application/json' \
  -d "{\"email\":\"$EMAIL\",\"password\":\"$PASSWORD\"}" | token >/dev/null && echo ok
FIRST=$(cookie)

step "4. refresh rotates the cookie"
ROTATED=$(curl -sSf -c "$JAR" -X POST "$API/auth/refresh" -H "Origin: $ORIGIN" \
  -H "Cookie: devflow_refresh=$FIRST" | token)
SECOND=$(cookie)
[ "$FIRST" != "$SECOND" ] && echo "rotated: ${FIRST:0:8}… → ${SECOND:0:8}…"

step "5. replaying the old cookie right away is benign (expect 401 REFRESH_TOKEN_ROTATED)"
curl -sS -X POST "$API/auth/refresh" -H "Origin: $ORIGIN" -H "Cookie: devflow_refresh=$FIRST"; echo

step "6. change password (signs out everywhere, returns a fresh session)"
curl -sSf -c "$JAR" -X POST "$API/me/password" -H "Authorization: Bearer $ROTATED" \
  -H 'Content-Type: application/json' \
  -d "{\"current_password\":\"$PASSWORD\",\"new_password\":\"$NEW_PASSWORD\"}" | token >/dev/null
FRESH=$(cookie)
echo "old session refresh: $(refresh "$SECOND") (expect 401)"

step "7. log out"
curl -sSf -o /dev/null -w '%{http_code}\n' -X POST "$API/auth/logout" -H "Origin: $ORIGIN" \
  -H "Cookie: devflow_refresh=$FRESH"
echo "refresh after logout: $(refresh "$FRESH") (expect 401)"

step "✓ auth flow works end to end"
