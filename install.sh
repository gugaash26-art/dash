#!/usr/bin/env bash
set -euo pipefail

HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
USER_NAME="${SUDO_USER:-$(id -un)}"
INSTALL_KIOSK=0
INSTALL_KIOSK_BAR=0
SKIP_APT=0

for arg in "$@"; do
  case "$arg" in
    --kiosk) INSTALL_KIOSK=1 ;;
    --kiosk-bar) INSTALL_KIOSK_BAR=1 ;;
    --duo) INSTALL_KIOSK_BAR=1 ;;
    --no-apt) SKIP_APT=1 ;;
    -h|--help)
      echo "uso: ./install.sh [--kiosk] [--kiosk-bar] [--duo] [--no-apt]"
      echo "  --kiosk       autostart do painel completo (uma tela)"
      echo "  --duo         duas telas via systemd: painel completo + cluster em barra"
      echo "  --kiosk-bar   somente o cluster em barra (segunda tela)"
      exit 0 ;;
  esac
done

say() { printf "\033[1;31m[OpenDash]\033[0m %s\n" "$1"; }

register_unit() { # tpl dest touch_size touch_pos bar_size bar_pos
  local tpl="$1" dest="$2" tmp
  tmp="$(mktemp)"
  sed -e "s|__DIR__|$HERE|g" -e "s|__USER__|$USER_NAME|g" \
      -e "s|__TOUCH_SIZE__|${3:-}|g" -e "s|__TOUCH_POS__|${4:-}|g" \
      -e "s|__BAR_SIZE__|${5:-}|g" -e "s|__BAR_POS__|${6:-}|g" \
      "$tpl" > "$tmp"
  sudo cp "$tmp" "/etc/systemd/system/$dest"
  rm -f "$tmp"
}

if [ "$SKIP_APT" -eq 0 ]; then
  say "instalando dependencias do sistema (apt)"
  sudo apt-get update -y
  sudo apt-get install -y python3 python3-venv python3-pip curl || true
fi

if [ ! -d "$HERE/.venv" ]; then
  say "criando virtualenv"
  python3 -m venv "$HERE/.venv"
fi

say "instalando dependencias Python"
if ! "$HERE/.venv/bin/pip" install -q -r "$HERE/requirements.txt"; then
  say "pip falhou; tentando pacotes do sistema"
  sudo apt-get install -y python3-serial python3-yaml || true
fi

mkdir -p "$HERE/data"
chmod +x "$HERE/kiosk/kiosk.sh" 2>/dev/null || true

if [ "$SKIP_APT" -eq 0 ]; then
  say "adicionando $USER_NAME ao grupo dialout (acesso serial)"
  sudo usermod -aG dialout "$USER_NAME" || true
fi

say "registrando servico systemd (cardash.service)"
TMP_SVC="$(mktemp)"
sed -e "s|__DIR__|$HERE|g" -e "s|__USER__|$USER_NAME|g" \
  "$HERE/systemd/cardash.service" > "$TMP_SVC"
sudo cp "$TMP_SVC" /etc/systemd/system/cardash.service
rm -f "$TMP_SVC"
sudo systemctl daemon-reload
sudo systemctl enable cardash.service
sudo systemctl restart cardash.service

if [ "$INSTALL_KIOSK" -eq 1 ]; then
  say "configurando autostart do kiosk para $USER_NAME"
  if [ "$SKIP_APT" -eq 0 ]; then
    sudo apt-get install -y chromium x11-xserver-utils || sudo apt-get install -y chromium-browser || true
  fi
  AUTFILE="/home/$USER_NAME/.config/autostart/cardash-kiosk.desktop"
  sudo -u "$USER_NAME" mkdir -p "$(dirname "$AUTFILE")"
  cat > "$AUTFILE" <<EOF
[Desktop Entry]
Type=Application
Name=OpenDash Kiosk
Comment=Painel automotivo em tela cheia
Exec=$HERE/kiosk/kiosk.sh
X-GNOME-Autostart-enabled=true
Terminal=false
EOF
  say "autostart criado: $AUTFILE"
fi

if [ "$INSTALL_KIOSK_BAR" -eq 1 ]; then
  say "configurando duas telas (painel completo + cluster em barra)"
  if [ "$SKIP_APT" -eq 0 ]; then
    sudo apt-get install -y chromium x11-xserver-utils || sudo apt-get install -y chromium-browser || true
  fi
  TOUCH_SIZE="${CARDASH_TOUCH_SIZE:-1024,600}"
  BAR_SIZE="${CARDASH_BAR_SIZE:-1920,480}"
  TOUCH_POS="${CARDASH_TOUCH_POS:-0,0}"
  TOUCH_W="${TOUCH_SIZE%%,*}"
  BAR_POS="${CARDASH_BAR_POS:-${TOUCH_W},0}"

  cat > "$HERE/data/screens.env" <<EOF
CARDASH_TOUCH_SIZE=$TOUCH_SIZE
CARDASH_TOUCH_POS=$TOUCH_POS
CARDASH_BAR_SIZE=$BAR_SIZE
CARDASH_BAR_POS=$BAR_POS
EOF

  register_unit "$HERE/systemd/cardash-kiosk.service" cardash-kiosk.service \
    "$TOUCH_SIZE" "$TOUCH_POS" "$BAR_SIZE" "$BAR_POS"
  register_unit "$HERE/systemd/cardash-kiosk-bar.service" cardash-kiosk-bar.service \
    "$TOUCH_SIZE" "$TOUCH_POS" "$BAR_SIZE" "$BAR_POS"
  sudo systemctl daemon-reload
  sudo systemctl enable cardash-kiosk.service cardash-kiosk-bar.service
  sudo systemctl restart cardash-kiosk.service cardash-kiosk-bar.service
  say "telas: painel ${TOUCH_SIZE}@${TOUCH_POS}  |  cluster ${BAR_SIZE}@${BAR_POS}"
  say "ajuste com CARDASH_TOUCH_SIZE/POS e CARDASH_BAR_SIZE/POS se necessario"
fi

IP="$(hostname -I 2>/dev/null | awk '{print $1}')"
say "pronto! abra o painel em http://${IP:-localhost}:8080"
say "servico: sudo systemctl status cardash"
say "logs:    journalctl -u cardash -f"
say "Para modo simulacao: Ajustes > Conexao e modo > Modo simulacao"
