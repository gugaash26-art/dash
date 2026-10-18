#!/usr/bin/env bash
# Constroi uma imagem OpenDash OS a partir da imagem oficial do DietPi.
#
# Uso: ./distro/build-image.sh <id-da-placa>
# Ex.: ./distro/build-image.sh zero3
#
# Nao precisa de root nem de loop device: usa mtools (FAT) e debugfs (ext4)
# diretamente no arquivo .img.
set -euo pipefail

HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT="$(cd "$HERE/.." && pwd)"
BOARD="${1:-}"
BASE_URL="${BASE_URL:-https://dietpi.com/downloads/images}"
CACHE="${CACHE_DIR:-$HERE/cache}"
OUT_DIR="${OUT_DIR:-$HERE/out}"
VERSION="${VERSION:-$(tr -d '[:space:]' < "$HERE/VERSION")}"

die() { echo "ERRO: $*" >&2; exit 1; }
need() { command -v "$1" >/dev/null 2>&1 || die "falta o comando '$1'"; }

[ -n "$BOARD" ] || die "informe a placa (ex.: zero3). Veja distro/boards.conf"
for c in curl xz sha256sum sfdisk mcopy mdir debugfs e2fsck dd awk sed; do need "$c"; done

LINE="$(grep -E "^${BOARD}\|" "$HERE/boards.conf" | head -1 || true)"
[ -n "$LINE" ] || die "placa '$BOARD' nao esta em distro/boards.conf"
IFS='|' read -r ID NAME IMAGE ENABLED <<< "$LINE"
[ -n "${IMAGE:-}" ] || die "linha invalida para '$BOARD' em boards.conf"
case "$IMAGE" in
  *ARMv8*|*arm64*) ARCH=arm64 ;;
  *ARMv7*)         ARCH=armhf ;;
  *ARMv6*)         ARCH=armv6 ;;
  *)               ARCH=arm64 ;;
esac

mkdir -p "$CACHE" "$OUT_DIR"
WORK="$(mktemp -d "$HERE/work.XXXXXX")"
trap 'rm -rf "$WORK"' EXIT

echo "== OpenDash OS $VERSION - $NAME ($ID, $ARCH) =="
BASE="$CACHE/$IMAGE"
SHA="$BASE.sha256"

fetch_base() {
  echo "-- baixando $IMAGE"
  curl -fL --retry 3 --connect-timeout 30 -o "$BASE.part" "$BASE_URL/$IMAGE" \
    || die "falha ao baixar a imagem base"
  mv -f "$BASE.part" "$BASE"
}

verify_base() {
  if [ ! -s "$SHA" ]; then
    curl -fsSL --retry 3 --connect-timeout 30 -o "$SHA" "$BASE_URL/$IMAGE.sha256" \
      || return 1
  fi
  ( cd "$CACHE" && sha256sum -c "$(basename "$SHA")" ) \
    || return 1
}

[ -f "$BASE" ] || fetch_base
if ! verify_base; then
  echo "-- SHA256 nao confere; baixando novamente"
  rm -f "$BASE"
  fetch_base
  verify_base || die "SHA256 da imagem base continua invalido"
fi

IMG="$WORK/$ID.img"
echo "-- descompactando"
xz -dc "$BASE" > "$IMG"

# --- localiza a particao de configuracao (FAT com dietpi.txt) e a raiz --------
FAT_SETUP=""; FAT_OTHER=""; FAT_SIZE=""; ROOT_START=""; ROOT_SIZE=""
while read -r START SIZE TYPE; do
  OFF=$((START * 512))
  if mdir -i "$IMG@@$OFF" ::/dietpi.txt >/dev/null 2>&1; then
    LABEL="$(mdir -i "$IMG@@$OFF" ::/ 2>/dev/null | sed -n '1s/.* is //p' | tr -d '\r')"
    if [ "$LABEL" = "DIETPISETUP" ]; then
      FAT_SETUP="$OFF"; FAT_SIZE="$SIZE"
    elif [ -z "$FAT_OTHER" ]; then
      FAT_OTHER="$OFF"; FAT_SIZE="$SIZE"
    fi
  fi
  if [ "$TYPE" = "83" ] && [ "$SIZE" -gt "${ROOT_SIZE:-0}" ]; then
    ROOT_START="$START"; ROOT_SIZE="$SIZE"
  fi
done < <(sfdisk -d "$IMG" | sed -nE \
  's/^[^:]+ : start=[[:space:]]*([0-9]+), size=[[:space:]]*([0-9]+), type=([0-9a-fA-F]+).*/\1 \2 \3/p')

FAT_OFF="${FAT_SETUP:-$FAT_OTHER}"
[ -n "$FAT_OFF" ] && echo "-- config FAT: offset $FAT_OFF ($((FAT_SIZE * 512 / 1024 / 1024)) MiB)"

[ -n "$FAT_OFF" ] || die "nao achei a particao FAT com dietpi.txt"
[ -n "$ROOT_START" ] || die "nao achei a particao raiz ext4"
echo "-- raiz: setor $ROOT_START ($((ROOT_SIZE * 512 / 1024 / 1024)) MiB)"

# --- payload do OpenDash (fonte + servidor + UI) -----------------------------
echo "-- gerando payload"
"$HERE/make-runtime.sh" "$WORK/opendash-runtime.tar.gz"
( cd "$WORK" && sha256sum opendash-runtime.tar.gz > opendash-runtime.sha256 )

cat > "$WORK/opendash-image.conf" <<EOF
OPENDASH_VERSION=$VERSION
OPENDASH_MODE=kiosk
OPENDASH_BROWSER=chromium
OPENDASH_CAR_NAME=OpenDash
OPENDASH_TOUCH_SIZE=1024,600
OPENDASH_BAR_SIZE=1920,480
OPENDASH_TOUCH_POS=0,0
OPENDASH_BAR_POS=1024,0
OPENDASH_REBOOT=1
EOF

# --- dietpi.txt (config FAT) --------------------------------------------------
echo "-- configurando dietpi.txt"
mtype -i "$IMG@@$FAT_OFF" ::/dietpi.txt > "$WORK/dietpi.txt"
python3 "$HERE/patch-dietpi.py" "$WORK/dietpi.txt" "$WORK/dietpi.new" \
  --set "AUTO_SETUP_AUTOMATED=1" \
  --set "AUTO_SETUP_GLOBAL_PASSWORD=opendash" \
  --set "AUTO_SETUP_NET_HOSTNAME=OpenDash" \
  --set "AUTO_SETUP_NET_ETHERNET_ENABLED=1" \
  --set "AUTO_SETUP_NET_WIFI_ENABLED=0" \
  --set "AUTO_SETUP_NET_WIFI_COUNTRY_CODE=BR" \
  --set "AUTO_SETUP_BOOT_WAIT_FOR_NETWORK=1" \
  --set "AUTO_SETUP_LOCALE=pt_BR.UTF-8" \
  --set "AUTO_SETUP_KEYBOARD_LAYOUT=br" \
  --set "AUTO_SETUP_TIMEZONE=America/Sao_Paulo" \
  --set "AUTO_SETUP_AUTOSTART_TARGET_INDEX=17" \
  --set "AUTO_SETUP_AUTOSTART_LOGIN_USER=root" \
  --set "AUTO_SETUP_INSTALL_SOFTWARE_ID=6 113" \
  --set "AUTO_SETUP_APT_INSTALLS=python3 python3-venv python3-pip python3-serial python3-yaml curl git unclutter xauth avahi-daemon libnss-mdns" \
  --set "AUTO_SETUP_CUSTOM_SCRIPT_EXEC=0" \
  --set "AUTO_SETUP_SSH_SERVER_INDEX=0" \
  --set "SURVEY_OPTED_IN=0" \
  --set "OPENDASH_VERSION=$VERSION" \
  --set "OPENDASH_MODE=kiosk" \
  --set "OPENDASH_BROWSER=chromium" \
  --set "OPENDASH_CAR_NAME=OpenDash" \
  --set "OPENDASH_TOUCH_SIZE=1024,600" \
  --set "OPENDASH_BAR_SIZE=1920,480" \
  --set "OPENDASH_TOUCH_POS=0,0" \
  --set "OPENDASH_BAR_POS=1024,0" \
  --set "OPENDASH_REBOOT=1"

mcopy -o -i "$IMG@@$FAT_OFF" "$WORK/dietpi.new" ::/dietpi.txt
mcopy -o -i "$IMG@@$FAT_OFF" "$HERE/firstboot.sh" ::/Automation_Custom_Script.sh
mcopy -o -i "$IMG@@$FAT_OFF" "$HERE/README-FIRSTBOOT.txt" ::/README-OPENDASH.txt

# --- injeta o payload na raiz ext4 -------------------------------------------
echo "-- injetando payload na raiz ext4"
ROOT_IMG="$WORK/root.ext4"
dd if="$IMG" of="$ROOT_IMG" bs=512 skip="$ROOT_START" count="$ROOT_SIZE" status=none
debugfs -w -R "rm /opt/opendash-runtime.tar.gz" "$ROOT_IMG" >/dev/null 2>&1 || true
debugfs -w -R "rm /opt/opendash-runtime.sha256" "$ROOT_IMG" >/dev/null 2>&1 || true
debugfs -w -R "rm /opt/opendash-image.conf" "$ROOT_IMG" >/dev/null 2>&1 || true
debugfs -w -R "write $WORK/opendash-runtime.tar.gz /opt/opendash-runtime.tar.gz" "$ROOT_IMG" >/dev/null
debugfs -w -R "write $WORK/opendash-runtime.sha256 /opt/opendash-runtime.sha256" "$ROOT_IMG" >/dev/null
debugfs -w -R "write $WORK/opendash-image.conf /opt/opendash-image.conf" "$ROOT_IMG" >/dev/null
for f in /opt/opendash-runtime.tar.gz /opt/opendash-runtime.sha256 /opt/opendash-image.conf; do
  debugfs -w -R "set_inode_field $f uid 0" "$ROOT_IMG" >/dev/null
  debugfs -w -R "set_inode_field $f gid 0" "$ROOT_IMG" >/dev/null
  debugfs -w -R "set_inode_field $f mode 0100644" "$ROOT_IMG" >/dev/null
done
e2fsck -fn "$ROOT_IMG" >/dev/null 2>&1 || die "filesystem ext4 da raiz nao passou no e2fsck"
dd if="$ROOT_IMG" of="$IMG" bs=512 seek="$ROOT_START" conv=notrunc status=none

# --- verificacoes -------------------------------------------------------------
echo "-- verificando imagem"
mdir -i "$IMG@@$FAT_OFF" ::/dietpi.txt >/dev/null
mdir -i "$IMG@@$FAT_OFF" ::/Automation_Custom_Script.sh >/dev/null
mtype -i "$IMG@@$FAT_OFF" ::/dietpi.txt | grep -q '^OPENDASH_MODE='
mtype -i "$IMG@@$FAT_OFF" ::/dietpi.txt | grep -q '^AUTO_SETUP_AUTOMATED=1'
debugfs -R 'stat /opt/opendash-runtime.tar.gz' "$ROOT_IMG" 2>/dev/null \
  | grep -q 'Inode:'
debugfs -R 'stat /opt/opendash-image.conf' "$ROOT_IMG" 2>/dev/null \
  | grep -q 'Inode:'
( cd /tmp && debugfs -R "dump /opt/opendash-runtime.tar.gz $WORK/check.tar.gz" "$ROOT_IMG" >/dev/null 2>&1
  sha256sum "$WORK/check.tar.gz" | awk '{print $1}' ) \
  | grep -qx "$(awk '{print $1}' "$WORK/opendash-runtime.sha256")" \
  || die "payload dentro da imagem nao confere"

# --- comprime e publica -------------------------------------------------------
OUT="$OUT_DIR/OpenDash-OS-${VERSION}-${ID}-${ARCH}.img.xz"
echo "-- comprimindo $OUT"
xz -T0 -6 -c "$IMG" > "$OUT"
xz -t "$OUT"
sha256sum "$OUT" > "$OUT.sha256"

cat > "$OUT.info" <<EOF
board=$ID
name=$NAME
version=$VERSION
arch=$ARCH
base=$IMAGE
base_sha256=$(awk '{print $1}' "$SHA")
out=$(basename "$OUT")
sha256=$(awk '{print $1}' "$OUT.sha256")
EOF

echo
echo "OK: $OUT"
echo "    $(du -h "$OUT" | awk '{print $1}')  $(awk '{print $1}' "$OUT.sha256")"
