#!/usr/bin/env bash
# Autostart do OpenDash no DietPi (dietpi-autostart 17, script custom).
#
# O DietPi chama este script no login automatico do tty1, sem desktop.
# Ele sobe o X11 (xinit/startx) e executa a sessao que abre o painel.
# Se ja existir um DISPLAY (por exemplo, rodando de dentro do desktop),
# apenas executa a sessao, sem iniciar outro servidor X.
set -uo pipefail

HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
LOG="${CARDASH_DIETPI_LOG:-/tmp/opendash-dietpi.log}"
exec >>"$LOG" 2>&1
echo "=== $(date '+%Y-%m-%d %H:%M:%S') OpenDash DietPi autostart ==="

BASE="${CARDASH_URL:-http://127.0.0.1:8080/}"
BASE="${BASE%/}"

# Espera o servidor cardash.service responder.
for _ in $(seq 1 120); do
  if curl -sf -m 2 "${BASE}/health" >/dev/null 2>&1; then break; fi
  sleep 1
done

# Ja existe um X funcional (desktop, VNC, etc.): nao inicia outro.
if [ -n "${DISPLAY:-}" ] && command -v xdpyinfo >/dev/null 2>&1 \
   && xdpyinfo >/dev/null 2>&1; then
  echo "DISPLAY=${DISPLAY} ja ativo; abrindo a sessao"
  exec "$HERE/dietpi-session.sh"
fi

# Como root, "startx" falha por falta de logind; "xinit" e o caminho do DietPi.
STARTX=xinit
[ "$(id -u)" -eq 0 ] || STARTX=startx
if ! command -v "$STARTX" >/dev/null 2>&1; then
  echo "OpenDash: $STARTX ausente. Instale o X11: sudo dietpi-software install 6"
  exit 3
fi

# -nocursor esconde o ponteiro no X; se o servidor nao aceitar, tenta sem.
while :; do
  "$STARTX" "$HERE/dietpi-session.sh" -- :0 -nocursor -nolisten tcp \
    || "$STARTX" "$HERE/dietpi-session.sh" -- :0 -nolisten tcp
  echo "OpenDash: sessao X encerrada; reiniciando em 3s"
  sleep 3
done
