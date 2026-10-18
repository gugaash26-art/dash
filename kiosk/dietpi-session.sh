#!/usr/bin/env bash
# Sessao X do OpenDash no DietPi: abre o painel completo e/ou a segunda tela.
#
# Configuracao gerada pelo install.sh em data/dietpi.env:
#   CARDASH_APP=0|1              usa navegador ou app nativo WebKitGTK
#   CARDASH_DIETPI_FULL=0|1      abre o painel completo (com menus)
#   CARDASH_DIETPI_SECOND=bar|cluster|   segunda tela (vazio = so uma)
#
# A geometria de duas telas vem de data/screens.env (install.sh).
set -uo pipefail

HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
DATA="$HERE/../data"

set -a
[ -f "$DATA/dietpi.env" ] && . "$DATA/dietpi.env"
[ -f "$DATA/screens.env" ] && . "$DATA/screens.env"
set +a

export CARDASH_APP="${CARDASH_APP:-0}"

if command -v xset >/dev/null 2>&1; then
  xset s off 2>/dev/null || true
  xset -dpms 2>/dev/null || true
  xset s noblank 2>/dev/null || true
fi

if command -v unclutter >/dev/null 2>&1; then
  unclutter -idle 0.5 -root &
fi

pids=()

run_screen() { # full | bar | cluster
  local scr="$1"
  echo "OpenDash: iniciando tela $scr"
  while :; do
    CARDASH_SCREEN="$scr" CARDASH_APP="$CARDASH_APP" "$HERE/kiosk.sh"
    echo "OpenDash: tela $scr terminou; reiniciando em 3s"
    sleep 3
  done
}

trap 'kill "${pids[@]}" 2>/dev/null || true; exit 0' INT TERM

[ "${CARDASH_DIETPI_FULL:-1}" = "1" ] && { run_screen full & pids+=("$!"); }
if [ -n "${CARDASH_DIETPI_SECOND:-}" ]; then
  run_screen "$CARDASH_DIETPI_SECOND" & pids+=("$!")
fi

if [ "${#pids[@]}" -eq 0 ]; then
  echo "OpenDash: nenhuma tela configurada em data/dietpi.env"
  exit 0
fi

# Se o servidor X cair, encerra as telas para o startx poder reiniciar.
if command -v xset >/dev/null 2>&1; then
  (
    while xset q >/dev/null 2>&1; do sleep 2; done
    echo "OpenDash: servidor X encerrado; fechando as telas"
    kill "${pids[@]}" 2>/dev/null || true
  ) &
fi

wait
