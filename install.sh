#!/usr/bin/env bash
set -euo pipefail

HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
USER_NAME="${SUDO_USER:-$(id -un)}"
INSTALL_KIOSK=0
INSTALL_KIOSK_BAR=0
INSTALL_KIOSK_CLUSTER=0
USE_APP=0
SKIP_APT=0
CHECK_ONLY=0

for arg in "$@"; do
  case "$arg" in
    --kiosk) INSTALL_KIOSK=1 ;;
    --kiosk-bar) INSTALL_KIOSK_BAR=1 ;;
    --kiosk-cluster) INSTALL_KIOSK_CLUSTER=1 ;;
    --duo) INSTALL_KIOSK=1; INSTALL_KIOSK_BAR=1 ;;
    --cluster) INSTALL_KIOSK=1; INSTALL_KIOSK_CLUSTER=1 ;;
    --app) USE_APP=1 ;;
    --no-apt) SKIP_APT=1 ;;
    --check) CHECK_ONLY=1 ;;
    -h|--help)
      echo "uso: ./install.sh [--check] [--kiosk] [--duo] [--cluster] [--kiosk-bar] [--kiosk-cluster] [--app] [--no-apt]"
      echo "  --check           só diagnóstico: verifica dependências e recursos (não instala)"
      echo "  --kiosk           autostart do painel completo (uma tela, com menus)"
      echo "  --duo             duas telas: painel completo + cluster em barra"
      echo "  --cluster         duas telas: painel completo (menus) + painel de velocidade (sem menus)"
      echo "  --kiosk-bar       somente o cluster em barra (segunda tela)"
      echo "  --kiosk-cluster   somente o painel de velocidade, velocímetro redondo (segunda tela)"
      echo "  --app             usa o aplicativo nativo (WebKitGTK) em vez do navegador"
      echo "                    (combine com --kiosk/--duo/--cluster; ex.: ./install.sh --app --cluster)"
      exit 0 ;;
  esac
done

app_deps() {
  sudo apt-get install -y python3-gi gir1.2-gtk-3.0 gir1.2-webkit2-4.1 \
    || sudo apt-get install -y python3-gi gir1.2-gtk-3.0 gir1.2-webkit2-4.0 || true
}

say() { printf "\033[1;31m[OpenDash]\033[0m %s\n" "$1"; }

# ----------------------------------------------------------------- diagnóstico
HAVE_OK=0; HAVE_OPT=0; MISS_REQ=0
m_tag()  { local c="$1" t="$2"; shift 2; printf "  [\033[%sm%-5s\033[0m] %s\n" "$c" "$t" "$*"; }
m_ok()   { m_tag 32 OK "$@";    HAVE_OK=$((HAVE_OK+1)); }
m_opt()  { m_tag 33 OPC "$@";   HAVE_OPT=$((HAVE_OPT+1)); }
m_req()  { m_tag 31 FALTA "$@"; MISS_REQ=$((MISS_REQ+1)); }
have()   { command -v "$1" >/dev/null 2>&1; }

diagnose() {
  local port native_ok=0 browser_ok=0 browser=""

  printf '\n\033[1;31m[OpenDash]\033[0m diagnóstico (--check): nada será alterado\n\n'

  if [ -n "${TERMUX_VERSION:-}" ] \
     || grep -qa -e proot -e "PRoot" /proc/version 2>/dev/null \
     || [ -n "${PROOT_TMP_DIR:-}" ]; then
    m_opt "ambiente: PRoot/Termux (desenvolvimento) — apt/systemd reais podem faltar"
  fi
  printf "  arquitetura: %s  |  SO: %s %s\n\n" "$(uname -m)" "$(uname -s)" "$(uname -r)"

  # --- essenciais (núcleo servidor) ---
  if have python3; then m_ok "python3 ($(python3 -V 2>&1 | awk '{print $2}'))"
  else m_req "python3 (sudo apt install python3)"; fi
  if have curl; then m_ok "curl"; else m_req "curl (sudo apt install curl)"; fi
  if have git; then m_ok "git"; else m_opt "git (necessário só para atualização pelo GitHub)"; fi

  if [ -x "$HERE/.venv/bin/python" ]; then
    if "$HERE/.venv/bin/python" -c "import yaml, serial" 2>/dev/null; then
      m_ok "Python (venv) com PyYAML e pyserial"
    else
      m_req "venv sem PyYAML/pyserial — rode ./install.sh"
    fi
  else
    m_req ".venv ausente — rode ./install.sh para criar"
  fi

  # --- servidor rodando ---
  port="$(sed -n 's/^[[:space:]]*port:[[:space:]]*\([0-9]\+\).*/\1/p' "$HERE/config.yaml" 2>/dev/null | head -1 || true)"
  port="${port:-8080}"
  if curl -sf -m 2 "http://127.0.0.1:${port}/health" >/dev/null 2>&1; then
    m_ok "servidor OpenDash respondendo em http://127.0.0.1:${port}"
  else
    m_opt "servidor não está respondendo na porta ${port} (inicia com o serviço cardash)"
  fi

  # --- kiosk / app nativo ---
  if python3 -c "import gi; gi.require_version('Gtk','3.0'); gi.require_version('WebKit2','4.1'); from gi.repository import Gtk, WebKit2" 2>/dev/null; then
    m_ok "app nativo: PyGObject + GTK3 + WebKitGTK 4.1"; native_ok=1
  else
    m_opt "app nativo indisponível (sudo apt install python3-gi gir1.2-gtk-3.0 gir1.2-webkit2-4.1)"
  fi
  for b in chromium chromium-browser google-chrome firefox; do
    if have "$b"; then browser="$b"; break; fi
  done
  if [ -n "$browser" ]; then m_ok "navegador para kiosk: $browser"; browser_ok=1
  else m_opt "nenhum navegador (chromium/firefox)"; fi
  if [ "$native_ok" -eq 1 ] || [ "$browser_ok" -eq 1 ]; then
    :
  else
    m_req "kiosk precisa do app nativo OU de um navegador (instale um dos dois)"
  fi
  if have systemctl; then m_ok "systemd (autostart do kiosk/serviço)"
  else m_opt "systemctl ausente (sem autostart por serviço)"; fi
  for h in xset unclutter; do
    if have "$h"; then m_ok "kiosk helper: $h"
    else m_opt "$h ausente (opcional: sem protetor de tela/cursor) — sudo apt install x11-xserver-utils unclutter"; fi
  done

  # --- integrações (desativam recursos se faltar) ---
  if have nmcli; then m_ok "Wi-Fi: nmcli"; else m_opt "Wi-Fi: nmcli ausente (Ajustes desativa a aba)"; fi
  if have bluetoothctl; then m_ok "Bluetooth: bluetoothctl"; else m_opt "Bluetooth: bluetoothctl ausente"; fi
  if have gnome-maps || have flatpak; then m_ok "mapa nativo: gnome-maps/flatpak"
  else m_opt "mapa nativo ausente (sudo apt install gnome-maps) — a Navegação web continua"; fi
  if have waydroid; then m_ok "Waydroid (apps Android)"; else m_opt "Waydroid ausente (veja install_waydroid.sh)"; fi
  if have aplay; then m_ok "áudio (aplay)"; else m_opt "aplay ausente (sem avisos sonoros)"; fi
  if have arecord; then m_ok "microfone (arecord)"; else m_opt "arecord ausente (assistente de voz sem entrada)"; fi
  if have whisper-cli; then m_ok "voz→texto: whisper-cli"; else m_opt "whisper-cli ausente (assistente usa transcrição na nuvem)"; fi
  if have ffmpeg; then m_ok "ffmpeg (gera os vídeos de tutorial/propaganda)"
  else m_opt "ffmpeg ausente (só para regerar os vídeos)"; fi

  # --- serial (Arduino/GPS) ---
  if id -nG "$USER_NAME" 2>/dev/null | tr ' ' '\n' | grep -qx dialout; then
    m_ok "usuário '$USER_NAME' no grupo dialout (Arduino/GPS)"
  else
    m_opt "usuário '$USER_NAME' fora do grupo dialout — sudo usermod -aG dialout $USER_NAME"
  fi

  # --- resumo ---
  printf '\n  ---- resumo ----\n'
  printf "  essenciais faltando: %d   |   opcionais ausentes: %d\n\n" "$MISS_REQ" "$HAVE_OPT"
  if [ "$MISS_REQ" -eq 0 ]; then
    printf '  \033[1;32mTudo pronto para rodar.\033[0m  Experimente:  ./install.sh --app --kiosk\n'
  else
    printf '  \033[1;31mFaltam %d item(ns) essencial(is).\033[0m  Rode:  ./install.sh --app --kiosk\n' "$MISS_REQ"
  fi
  printf '  Um item "OPC" ausente não impede rodar: apenas desativa um recurso.\n\n'
  return 0
}

if [ "$CHECK_ONLY" -eq 1 ]; then diagnose; exit 0; fi

register_unit() { # tpl dest touch_size touch_pos bar_size bar_pos
  local tpl="$1" dest="$2" tmp
  tmp="$(mktemp)"
  sed -e "s|__DIR__|$HERE|g" -e "s|__USER__|$USER_NAME|g" \
      -e "s|__APP__|${USE_APP:-0}|g" \
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
    if [ "$USE_APP" -eq 1 ]; then app_deps
    else sudo apt-get install -y chromium x11-xserver-utils || sudo apt-get install -y chromium-browser || true; fi
  fi
  AUTFILE="/home/$USER_NAME/.config/autostart/cardash-kiosk.desktop"
  sudo -u "$USER_NAME" mkdir -p "$(dirname "$AUTFILE")"
  cat > "$AUTFILE" <<EOF
[Desktop Entry]
Type=Application
Name=OpenDash Kiosk
Comment=Painel automotivo em tela cheia
Exec=env CARDASH_APP=$USE_APP $HERE/kiosk/kiosk.sh
X-GNOME-Autostart-enabled=true
Terminal=false
EOF
  say "autostart criado: $AUTFILE"
fi

if [ "$INSTALL_KIOSK_BAR" -eq 1 ] || [ "$INSTALL_KIOSK_CLUSTER" -eq 1 ]; then
  if [ "$INSTALL_KIOSK_CLUSTER" -eq 1 ]; then
    SECOND_UNIT="cardash-kiosk-cluster.service"
    SECOND_SRC="$HERE/systemd/cardash-kiosk-cluster.service"
    SECOND_DESC="painel de velocidade (velocimetro, sem menus)"
  else
    SECOND_UNIT="cardash-kiosk-bar.service"
    SECOND_SRC="$HERE/systemd/cardash-kiosk-bar.service"
    SECOND_DESC="cluster em barra"
  fi
  say "configurando duas telas (painel completo + $SECOND_DESC)"
  if [ "$SKIP_APT" -eq 0 ]; then
    if [ "$USE_APP" -eq 1 ]; then app_deps
    else sudo apt-get install -y chromium x11-xserver-utils || sudo apt-get install -y chromium-browser || true; fi
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
  register_unit "$SECOND_SRC" "$SECOND_UNIT" \
    "$TOUCH_SIZE" "$TOUCH_POS" "$BAR_SIZE" "$BAR_POS"
  sudo systemctl daemon-reload
  sudo systemctl enable cardash-kiosk.service "$SECOND_UNIT"
  sudo systemctl restart cardash-kiosk.service "$SECOND_UNIT"
  say "telas: painel ${TOUCH_SIZE}@${TOUCH_POS}  |  $SECOND_DESC ${BAR_SIZE}@${BAR_POS}"
  say "ajuste com CARDASH_TOUCH_SIZE/POS e CARDASH_BAR_SIZE/POS se necessario"
fi

if [ "$USE_APP" -eq 1 ]; then
  say "instalando atalho do aplicativo OpenDash"
  if [ "$SKIP_APT" -eq 0 ]; then app_deps; fi
  TMP_DESK="$(mktemp)"
  sed -e "s|__DIR__|$HERE|g" "$HERE/kiosk/opendash.desktop" > "$TMP_DESK"
  sudo install -d /usr/share/applications
  sudo cp "$TMP_DESK" /usr/share/applications/opendash.desktop
  rm -f "$TMP_DESK"
  say "atalho: /usr/share/applications/opendash.desktop (menu de aplicativos)"
fi

IP="$(hostname -I 2>/dev/null | awk '{print $1}')"
say "pronto! abra o painel em http://${IP:-localhost}:8080"
say "servico: sudo systemctl status cardash"
say "logs:    journalctl -u cardash -f"
say "Para modo simulacao: Ajustes > Conexao e modo > Modo simulacao"
