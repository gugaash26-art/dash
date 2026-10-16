#!/usr/bin/env bash
set -uo pipefail

# Tela a abrir:
#   CARDASH_SCREEN=full  (padrão)  -> interface completa (páginas/apps)
#   CARDASH_SCREEN=bar             -> cluster horizontal (ex.: 1920x480)
#
# Para duas telas no mesmo servidor X (Xinerama), defina a geometria de cada uma:
#   CARDASH_WINDOW_SIZE=1024,600  CARDASH_WINDOW_POS=0,0     (touch 8")
#   CARDASH_WINDOW_SIZE=1920,480  CARDASH_WINDOW_POS=1024,0  (barra 11.3")
# Sem CARDASH_WINDOW_SIZE o navegador abre em modo kiosk (tela cheia na primária).

URL="${CARDASH_URL:-http://127.0.0.1:8080/}"
BASE="${URL%/}/"
SCREEN="${CARDASH_SCREEN:-full}"

case "$SCREEN" in
  bar)  PAGE="${BASE}bar.html"; NAME="cardash-bar" ;;
  *)    PAGE="${BASE}";         NAME="cardash-full" ;;
esac

for i in $(seq 1 60); do
  if curl -sf -m 2 "${BASE}health" >/dev/null 2>&1 || curl -sf -m 2 "$PAGE" >/dev/null 2>&1; then
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
  "--noerrdialogs"
  "--disable-infobars"
  "--disable-session-crashed-bubble"
  "--disable-translate"
  "--disable-features=Translate,BackForwardCache"
  "--autoplay-policy=no-user-gesture-required"
  "--overscroll-history-navigation=0"
  "--password-store=basic"
  "--check-for-update-interval=31536000"
  "--user-data-dir=/tmp/${NAME}"
)

POS_FLAGS=()
if [ -n "${CARDASH_WINDOW_SIZE:-}" ]; then
  # janela posicionada (para conviver com a outra tela); sem --kiosk
  POS_FLAGS+=( "--window-size=${CARDASH_WINDOW_SIZE}" )
  [ -n "${CARDASH_WINDOW_POS:-}" ] && POS_FLAGS+=( "--window-position=${CARDASH_WINDOW_POS}" )
  POS_FLAGS+=( "--window-name=${NAME}" )
else
  POS_FLAGS+=( "--kiosk" )
fi

if command -v chromium >/dev/null 2>&1; then
  exec chromium "${COMMON_FLAGS[@]}" "${POS_FLAGS[@]}" --app="$PAGE"
elif command -v chromium-browser >/dev/null 2>&1; then
  exec chromium-browser "${COMMON_FLAGS[@]}" "${POS_FLAGS[@]}" --app="$PAGE"
elif command -v google-chrome >/dev/null 2>&1; then
  exec google-chrome "${COMMON_FLAGS[@]}" "${POS_FLAGS[@]}" --app="$PAGE"
elif command -v firefox >/dev/null 2>&1; then
  exec firefox --kiosk "$PAGE"
else
  echo "Nenhum navegador encontrado (instale chromium)." >&2
  exit 1
fi
