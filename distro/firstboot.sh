#!/bin/bash
# OpenDash OS - configuracao de primeiro boot.
# A DietPi copia este arquivo para /boot/Automation_Custom_Script.sh e o executa
# como root ao final da instalacao automatica do primeiro boot.
set -u

export PATH=/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin
export DEBIAN_FRONTEND=noninteractive
LOG=/var/lib/opendash/firstboot.log
mkdir -p /var/lib/opendash
exec > >(tee -a "$LOG") 2>&1

echo
echo "=== OpenDash OS: primeiro boot $(date -Is) ==="

CFG=/boot/dietpi.txt
[ -f "$CFG" ] || CFG=/boot/firmware/dietpi.txt
IMG_CFG=/opt/opendash-image.conf
get() {
  local v=""
  [ -f "$CFG" ] && v="$(sed -n "s/^[[:blank:]]*$1=//p" "$CFG" | tail -1)"
  [ -n "$v" ] || { [ -f "$IMG_CFG" ] && v="$(sed -n "s/^[[:blank:]]*$1=//p" "$IMG_CFG" | tail -1)"; }
  printf '%s' "$v"
}

MODE="$(get OPENDASH_MODE)";             MODE="${MODE:-kiosk}"
BROWSER="$(get OPENDASH_BROWSER)";       BROWSER="${BROWSER:-chromium}"
CAR_NAME="$(get OPENDASH_CAR_NAME)";     CAR_NAME="${CAR_NAME:-OpenDash}"
TOUCH_SIZE="$(get OPENDASH_TOUCH_SIZE)"; TOUCH_SIZE="${TOUCH_SIZE:-1024,600}"
BAR_SIZE="$(get OPENDASH_BAR_SIZE)";     BAR_SIZE="${BAR_SIZE:-1920,480}"
TOUCH_POS="$(get OPENDASH_TOUCH_POS)";   TOUCH_POS="${TOUCH_POS:-0,0}"
BAR_POS="$(get OPENDASH_BAR_POS)";       BAR_POS="${BAR_POS:-1024,0}"
REBOOT="$(get OPENDASH_REBOOT)";         REBOOT="${REBOOT:-1}"
PAYLOAD_URL="$(get OPENDASH_PAYLOAD_URL)"
PAYLOAD_URL="${PAYLOAD_URL:-https://github.com/gugaash26-art/dash/releases/latest/download/opendash-runtime.tar.gz}"
VERSION="$(get OPENDASH_VERSION)"
[ -n "$VERSION" ] && echo "OpenDash OS $VERSION" > /etc/opendash-release

echo "modo=$MODE navegador=$BROWSER carro=$CAR_NAME versao=${VERSION:-?}"

# --- payload (fonte do OpenDash) -----------------------------------------------
PAYLOAD=""
for p in /opt/opendash-runtime.tar.gz /boot/opendash-runtime.tar.gz \
         /boot/firmware/opendash-runtime.tar.gz; do
  if [ -f "$p" ]; then PAYLOAD="$p"; break; fi
done
if [ -z "$PAYLOAD" ]; then
  echo "payload local ausente; baixando $PAYLOAD_URL"
  if curl -fsSL --retry 3 --connect-timeout 20 "$PAYLOAD_URL" \
       -o /opt/opendash-runtime.tar.gz; then
    PAYLOAD=/opt/opendash-runtime.tar.gz
  fi
fi
if [ -z "$PAYLOAD" ]; then
  echo "ERRO: sem payload do OpenDash (SD sem a imagem correta e sem internet)." >&2
  exit 1
fi
if [ -f /opt/opendash-runtime.sha256 ]; then
  ( cd /opt && sha256sum -c opendash-runtime.sha256 ) || exit 1
fi

# --- rede e dependencias basicas ----------------------------------------------
if ! command -v python3 >/dev/null 2>&1 || ! python3 -m venv --help >/dev/null 2>&1; then
  echo "instalando python3/venv..."
  apt-get update -y || true
  apt-get install -y python3 python3-venv python3-pip python3-yaml python3-serial \
    curl unclutter xauth || true
fi
if [ "$BROWSER" = "app" ]; then
  echo "instalando WebKitGTK para o app nativo..."
  apt-get update -y || true
  apt-get install -y python3-gi gir1.2-gtk-3.0 || true
  apt-get install -y gir1.2-webkit2-4.1 || apt-get install -y gir1.2-webkit2-4.0 || true
fi

# --- configura Wi-Fi interativo se necessário ----------------------------------
if [ -x /opt/opendash/wifi-setup.sh ]; then
  /opt/opendash/wifi-setup.sh || true
fi

# --- instala o OpenDash -------------------------------------------------------
mkdir -p /opt/opendash
tar -xzf "$PAYLOAD" -C /opt/opendash
cp -f "$0" /opt/opendash/firstboot.sh 2>/dev/null || true
chmod +x /opt/opendash/install.sh /opt/opendash/kiosk/kiosk.sh \
  /opt/opendash/kiosk/dietpi-kiosk.sh /opt/opendash/kiosk/dietpi-session.sh 2>/dev/null || true

if [ -f /opt/opendash/config.yaml ]; then
  awk -v name="$CAR_NAME" '
    /^car:[[:space:]]*$/ { incar=1; print; next }
    incar && /^[^[:space:]]/ { incar=0 }
    incar && /^  name:/ { print "  name: " name; incar=0; next }
    { print }
  ' /opt/opendash/config.yaml > /opt/opendash/config.yaml.new \
    && mv /opt/opendash/config.yaml.new /opt/opendash/config.yaml
fi

ARGS=()
case "$MODE" in
  duo)                       ARGS+=(--duo) ;;
  cluster)                   ARGS+=(--cluster) ;;
  bar)                       ARGS+=(--kiosk-bar) ;;
  cluster-only|cluster_only) ARGS+=(--kiosk-cluster) ;;
  kiosk|*)                   ARGS+=(--kiosk) ;;
esac
[ "$BROWSER" = "app" ] && ARGS+=(--app)

cd /opt/opendash
echo "executando install.sh ${ARGS[*]}"
if ! CARDASH_DEPS_READY=1 \
     CARDASH_TOUCH_SIZE="$TOUCH_SIZE" CARDASH_TOUCH_POS="$TOUCH_POS" \
     CARDASH_BAR_SIZE="$BAR_SIZE" CARDASH_BAR_POS="$BAR_POS" \
     ./install.sh --no-apt "${ARGS[@]}"; then
  echo "ERRO: install.sh falhou; veja $LOG" >&2
  exit 1
fi

echo "OpenDash OS instalado. Servico:"
systemctl --no-pager --lines=0 status cardash.service || true

if [ "$REBOOT" = "1" ]; then
  echo "Reiniciando em 10 s para abrir o kiosk..."
  ( sleep 10; systemctl reboot ) >/dev/null 2>&1 &
fi
echo "=== fim do primeiro boot $(date -Is) ==="
