#!/usr/bin/env bash
# Constroi uma imagem OpenDash OS a partir da imagem oficial do Armbian.
#
# Uso: ./distro/build-image-armbian.sh <id-da-placa>
# Ex.: ./distro/build-image-armbian.sh zero3
#
# Nao precisa de root nem de loop device: usa mtools (FAT) e debugfs (ext4)
# diretamente no arquivo .img.
#
# Diferencas em relacao ao caminho DietPi (build-image.sh):
#   - a base vem de https://dl.armbian.com/<slug>/<Release>_<branch>_<variant>.img.xz
#   - a particao FAT de boot tem armbianEnv.txt (label armbi_boot), nao dietpi.txt
#   - o primeiro boot automatico e feito por /root/.not_logged_in_yet (preseed)
#     + /root/provisioning.sh (script de provisionamento), injetados na raiz ext4
set -euo pipefail

HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT="$(cd "$HERE/.." && pwd)"
BOARD="${1:-}"
BASE_URL="${BASE_URL:-https://dl.armbian.com}"
CACHE="${CACHE_DIR:-$HERE/cache}"
OUT_DIR="${OUT_DIR:-$HERE/out}"
VERSION="${VERSION:-$(tr -d '[:space:]' < "$HERE/VERSION")}"
CONF="${BOARDS_CONF:-$HERE/boards-armbian.conf}"

die() { echo "ERRO: $*" >&2; exit 1; }
need() { command -v "$1" >/dev/null 2>&1 || die "falta o comando '$1'"; }

[ -n "$BOARD" ] || die "informe a placa (ex.: zero3). Veja distro/boards-armbian.conf"
for c in curl xz sha256sum sfdisk mcopy mdir debugfs e2fsck dd awk sed; do need "$c"; done

LINE="$(grep -E "^${BOARD}\|" "$CONF" | head -1 || true)"
[ -n "$LINE" ] || die "placa '$BOARD' nao esta em $CONF"
IFS='|' read -r ID NAME SLUG RELEASE BRANCH VARIANT ENABLED <<< "$LINE"
[ -n "${SLUG:-}" ] || die "linha invalida para '$BOARD' em boards-armbian.conf"
RELEASE="${RELEASE:-Trixie}"
BRANCH="${BRANCH:-current}"
VARIANT="${VARIANT:-minimal}"

# Nome do arquivo na Armbian: <Release>_<branch>_<variant>.img.xz (release em
# minusculas no path do download estavel, ex.: Trixie -> Trixie).
REL_LC="$(printf '%s' "$RELEASE" | tr '[:upper:]' '[:lower:]')"
case "$REL_LC" in
  trixie|bookworm|resolute|noble|jammy|bullseye) ;;
  *) die "release Armbian desconhecida: $RELEASE" ;;
esac
BASE_NAME="${RELEASE}_${BRANCH}_${VARIANT}.img.xz"
# Armbian entrega imagens arm64 para as placas suportadas aqui.
ARCH=arm64

mkdir -p "$CACHE" "$OUT_DIR"
WORK="$(mktemp -d "$HERE/work.XXXXXX")"
trap 'rm -rf "$WORK"' EXIT

echo "== OpenDash OS (Armbian) $VERSION - $NAME ($ID, $ARCH) =="
echo "-- base: ${BASE_URL}/${SLUG}/${BASE_NAME}"
BASE="$CACHE/${SLUG}-${BASE_NAME}"
SHA="$BASE.sha"

fetch_base() {
  echo "-- baixando $BASE_NAME"
  curl -fL --retry 3 --connect-timeout 30 -o "$BASE.part" \
    "$BASE_URL/$SLUG/$BASE_NAME" || die "falha ao baixar a imagem base"
  mv -f "$BASE.part" "$BASE"
}

# O .sha da Armbian tem uma linha "<hash> <arquivo>"; normalizamos para o
# formato que o sha256sum -c entende dentro do CACHE.
verify_base() {
  if [ ! -s "$SHA" ]; then
    curl -fsSL --retry 3 --connect-timeout 30 -o "$SHA.raw" \
      "$BASE_URL/$SLUG/${BASE_NAME%.img.xz}.sha" || return 1
  fi
  local want
  want="$(awk '{print $1; exit}' "$SHA.raw" 2>/dev/null || true)"
  [ -n "$want" ] || return 1
  printf '%s  %s\n' "$want" "$(basename "$BASE")" > "$SHA"
  ( cd "$CACHE" && sha256sum -c "$(basename "$SHA")" ) >/dev/null
}

[ -f "$BASE" ] || fetch_base
if ! verify_base; then
  echo "-- SHA256 nao confere; baixando novamente"
  rm -f "$BASE"
  fetch_base
  verify_base || die "SHA256 da imagem base continua invalido"
fi
BASE_SHA="$(awk '{print $1; exit}' "$SHA")"

IMG="$WORK/$ID.img"
echo "-- descompactando"
xz -dc "$BASE" > "$IMG"

# --- localiza a particao FAT de boot (armbianEnv.txt) e a raiz ext4 -----------
FAT_OFF=""; FAT_SIZE=""; ROOT_START=""; ROOT_SIZE=""
while read -r START SIZE TYPE; do
  OFF=$((START * 512))
  if mdir -i "$IMG@@$OFF" ::/armbianEnv.txt >/dev/null 2>&1; then
    FAT_OFF="$OFF"; FAT_SIZE="$SIZE"
  fi
  if [ "$TYPE" = "83" ] && [ "$SIZE" -gt "${ROOT_SIZE:-0}" ]; then
    ROOT_START="$START"; ROOT_SIZE="$SIZE"
  fi
done < <(sfdisk -d "$IMG" | sed -nE \
  's/^[^:]+ : start=[[:space:]]*([0-9]+), size=[[:space:]]*([0-9]+), type=([0-9a-fA-F]+).*/\1 \2 \3/p')

[ -n "$FAT_OFF" ] && echo "-- boot FAT: offset $FAT_OFF ($((FAT_SIZE * 512 / 1024 / 1024)) MiB)"
[ -n "$FAT_OFF" ] || die "nao achei a particao FAT com armbianEnv.txt"
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

# --- preseed do primeiro boot (/root/.not_logged_in_yet) ----------------------
# Deixa o primeiro boot 100% automatico: senha de root, usuario padrao kiosk,
# locale, teclado e timezone brasileiros e Wi-Fi habilitado. O Wi-Fi fica sem
# SSID/senha (preenchidos pelo wifi-setup.sh ou pelo assistente), mas o stack e
# trazido no primeiro boot pela Armbian.
echo "-- escrevendo preseed de primeiro boot"
cat > "$WORK/not_logged_in_yet" <<EOF
PRESET_ROOT_PASSWORD="opendash"
PRESET_USER_NAME="kiosk"
PRESET_USER_PASSWORD="opendash"
PRESET_USER_REALNAME="OpenDash"
PRESET_DEFAULT_REALNAME="OpenDash"
PRESET_DEFAULT_LOCALE="pt_BR.UTF-8"
PRESET_DEFAULT_KEYBOARD="br"
PRESET_DEFAULT_TIMEZONE="America/Sao_Paulo"
PRESET_HOSTNAME="OpenDash"
# Wi-Fi: deixe SSID/senha vazios para configurar depois (wifi-setup.sh / nmtui).
PRESET_NET_CHANGE_DEFAULTS="1"
PRESET_NET_WIFI_ENABLED="1"
PRESET_NET_WIFI_SSID=""
PRESET_NET_WIFI_KEY=""
PRESET_NET_WIFI_COUNTRYCODE="BR"
EOF

# --- injeta payload + preseed + provisioning na raiz ext4 --------------------
echo "-- injetando payload e provisionamento na raiz ext4"
ROOT_IMG="$WORK/root.ext4"
dd if="$IMG" of="$ROOT_IMG" bs=512 skip="$ROOT_START" count="$ROOT_SIZE" status=none

rm_rootfs() { debugfs -w -R "rm $1" "$ROOT_IMG" >/dev/null 2>&1 || true; }
ensure_dir() { debugfs -w -R "mkdir $1" "$ROOT_IMG" >/dev/null 2>&1 || true; }
write_rootfs() {
  debugfs -w -R "write $1 $2" "$ROOT_IMG" >/dev/null
  debugfs -w -R "set_inode_field $2 uid 0" "$ROOT_IMG" >/dev/null
  debugfs -w -R "set_inode_field $2 gid 0" "$ROOT_IMG" >/dev/null
  debugfs -w -R "set_inode_field $2 mode $3" "$ROOT_IMG" >/dev/null
}

ensure_dir /opt
ensure_dir /root

rm_rootfs /opt/opendash-runtime.tar.gz
rm_rootfs /opt/opendash-runtime.sha256
rm_rootfs /opt/opendash-image.conf
rm_rootfs /root/.not_logged_in_yet
rm_rootfs /root/provisioning.sh

write_rootfs "$WORK/opendash-runtime.tar.gz" /opt/opendash-runtime.tar.gz 0100644
write_rootfs "$WORK/opendash-runtime.sha256" /opt/opendash-runtime.sha256 0100644
write_rootfs "$WORK/opendash-image.conf" /opt/opendash-image.conf 0100644
write_rootfs "$WORK/not_logged_in_yet" /root/.not_logged_in_yet 0100600
write_rootfs "$HERE/firstboot-armbian.sh" /root/provisioning.sh 0100755

e2fsck -fn "$ROOT_IMG" >/dev/null 2>&1 || die "filesystem ext4 da raiz nao passou no e2fsck"
dd if="$ROOT_IMG" of="$IMG" bs=512 seek="$ROOT_START" conv=notrunc status=none

# --- verificacoes -------------------------------------------------------------
echo "-- verificando imagem"
mdir -i "$IMG@@$FAT_OFF" ::/armbianEnv.txt >/dev/null
debugfs -R 'stat /root/provisioning.sh' "$ROOT_IMG" 2>/dev/null | grep -q 'Inode:'
debugfs -R 'stat /root/.not_logged_in_yet' "$ROOT_IMG" 2>/dev/null | grep -q 'Inode:'
debugfs -R 'stat /opt/opendash-runtime.tar.gz' "$ROOT_IMG" 2>/dev/null | grep -q 'Inode:'
( cd /tmp && debugfs -R "dump /opt/opendash-runtime.tar.gz $WORK/check.tar.gz" "$ROOT_IMG" >/dev/null 2>&1
  sha256sum "$WORK/check.tar.gz" | awk '{print $1}' ) \
  | grep -qx "$(awk '{print $1}' "$WORK/opendash-runtime.sha256")" \
  || die "payload dentro da imagem nao confere"

# --- comprime e publica -------------------------------------------------------
OUT="$OUT_DIR/OpenDash-OS-Armbian-${VERSION}-${ID}-${ARCH}.img.xz"
echo "-- comprimindo $OUT"
xz -T0 -6 -c "$IMG" > "$OUT"
xz -t "$OUT"
( cd "$OUT_DIR" && sha256sum "$(basename "$OUT")" > "$(basename "$OUT").sha256" )

cat > "$OUT.info" <<EOF
board=$ID
name=$NAME
distro=armbian
armbian_slug=$SLUG
version=$VERSION
arch=$ARCH
base=$BASE_NAME
base_sha256=$BASE_SHA
out=$(basename "$OUT")
sha256=$(awk '{print $1}' "$OUT.sha256")
EOF

echo
echo "OK: $OUT"
echo "    $(du -h "$OUT" | awk '{print $1}')  $(awk '{print $1}' "$OUT.sha256")"
