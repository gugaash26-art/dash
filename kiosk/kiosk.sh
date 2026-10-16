#!/usr/bin/env bash
set -uo pipefail

URL="${CARDASH_URL:-http://127.0.0.1:8080/}"

for i in $(seq 1 60); do
  if curl -sf -m 2 "${URL}health" >/dev/null 2>&1 || curl -sf -m 2 "$URL" >/dev/null 2>&1; then
    break
  fi
  sleep 1
done

if command -v xset >/dev/null 2>&1; then
  xset s off 2>/dev/null || true
  xset -dpms 2>/dev/null || true
  xset s noblank 2>/dev/null || true
fi

if command -v unclutter >/dev/null 2>&1; then
  unclutter -idle 0.5 -root &
fi

COMMON_FLAGS=(
  "--kiosk"
  "--noerrdialogs"
  "--disable-infobars"
  "--disable-session-crashed-bubble"
  "--disable-translate"
  "--disable-features=Translate,BackForwardCache"
  "--autoplay-policy=no-user-gesture-required"
  "--overscroll-history-navigation=0"
  "--password-store=basic"
  "--check-for-update-interval=31536000"
  "--user-data-dir=/tmp/cardash-kiosk"
)

if command -v chromium >/dev/null 2>&1; then
  exec chromium "${COMMON_FLAGS[@]}" --app="$URL"
elif command -v chromium-browser >/dev/null 2>&1; then
  exec chromium-browser "${COMMON_FLAGS[@]}" --app="$URL"
elif command -v google-chrome >/dev/null 2>&1; then
  exec google-chrome "${COMMON_FLAGS[@]}" --app="$URL"
elif command -v firefox >/dev/null 2>&1; then
  exec firefox --kiosk "$URL"
else
  echo "Nenhum navegador encontrado (instale chromium)." >&2
  exit 1
fi
