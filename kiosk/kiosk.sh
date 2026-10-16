#!/usr/bin/env bash
set -uo pipefail

# Tela a abrir:
#   CARDASH_SCREEN=full  (padrão)  -> interface completa (páginas/apps)
#   CARDASH_SCREEN=bar             -> cluster horizontal (ex.: 1920x480)
#
# Para duas telas no mesmo servidor X (Xinerama), defina a geometria de cada uma:
#   CARDASH_TOUCH_SIZE=1024,600  CARDASH_TOUCH_POS=0,0     (painel / touch 8")
#   CARDASH_BAR_SIZE=1920,480    CARDASH_BAR_POS=1024,0    (cluster / barra 11.3")
# Estes valores vem de data/screens.env (Ajustes > Telas) ou podem ser exportados
# direto; CARDASH_WINDOW_SIZE/POS continuam aceitos e tem prioridade.
# Sem geometria o navegador abre em modo kiosk (tela cheia na primária).

URL="${CARDASH_URL:-http://127.0.0.1:8080/}"
BASE="${URL%/}/"
SCREEN="${CARDASH_SCREEN:-full}"

case "$SCREEN" in
  bar)  PAGE="${BASE}bar.html"; NAME="cardash-bar"
        WIN_SIZE="${CARDASH_WINDOW_SIZE:-${CARDASH_BAR_SIZE:-}}"
        WIN_POS="${CARDASH_WINDOW_POS:-${CARDASH_BAR_POS:-}}" ;;
  *)    PAGE="${BASE}";         NAME="cardash-full"
        WIN_SIZE="${CARDASH_WINDOW_SIZE:-${CARDASH_TOUCH_SIZE:-}}"
        WIN_POS="${CARDASH_WINDOW_POS:-${CARDASH_TOUCH_POS:-}}" ;;
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
if [ -n "${WIN_SIZE:-}" ]; then
  # janela posicionada (para conviver com a outra tela); sem --kiosk
  POS_FLAGS+=( "--window-size=${WIN_SIZE}" )
  [ -n "${WIN_POS:-}" ] && POS_FLAGS+=( "--window-position=${WIN_POS}" )
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
