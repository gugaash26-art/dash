#!/usr/bin/env bash
#
# install_waydroid.sh — instala o Waydroid (Android em contêiner LXC) no Orange Pi
# para rodar aplicativos Android como janelas do Linux, ao lado do OpenDash.
#
# ============================ LEIA ISTO =====================================
#  • Funciona em um Linux REAL (Armbian/Debian/Ubuntu) com kernel próprio.
#  • NÃO funciona dentro de PRoot/Termux (Android), WSL1, ou contêiner sem
#    privilégios: o Waydroid precisa criar contêineres LXC e usar os módulos de
#    kernel binder/ashmem. O script detecta e aborta nesses casos.
#  • O Waydroid exige uma sessão Wayland. O kiosk atual usa X11; use um
#    compositor (cage/weston) ou uma sessão Wayland (ver mensagem final).
#  • Precisa de ~4 GB de disco e ~2 GB de RAM livres. Recomendado: Orange Pi 5.
# ============================================================================
#
# Uso:
#   sudo ./install_waydroid.sh             # imagem VANILLA (sem Google)
#   sudo ./install_waydroid.sh --gapps     # com Google Play (GApps)
#   sudo ./install_waydroid.sh --check     # apenas diagnóstico, não instala
#   sudo ./install_waydroid.sh --help
set -euo pipefail

IMAGE_TYPE="VANILLA"
CHECK_ONLY=0
LOG_PREFIX="[waydroid]"

log()  { printf '%s %s\n' "$LOG_PREFIX" "$*"; }
warn() { printf '%s AVISO: %s\n' "$LOG_PREFIX" "$*" >&2; }
die()  { printf '%s ERRO: %s\n' "$LOG_PREFIX" "$*" >&2; exit 1; }

usage() {
  sed -n '2,26p' "$0" | sed 's/^# \{0,1\}//'
  exit 0
}

for arg in "$@"; do
  case "$arg" in
    --gapps)   IMAGE_TYPE="GAPPS" ;;
    --vanilla) IMAGE_TYPE="VANILLA" ;;
    --check)   CHECK_ONLY=1 ;;
    -h|--help) usage ;;
    *) die "argumento desconhecido: $arg (use --help)" ;;
  esac
done

# ---------------------------------------------------------------- ambiente ---
detect_env() {
  if [ -n "${TERMUX_VERSION:-}" ]; then
    die "Termux/Android detectado. O Waydroid exige um kernel Linux real — rode este script no Orange Pi (Armbian/Debian)."
  fi
  if grep -qa -e proot -e "PRoot" /proc/version 2>/dev/null \
     || [ -n "${PROOT_TMP_DIR:-}" ] || [ -n "${PROOT_L2S_DIR:-}" ]; then
    die "PRoot detectado. O Waydroid não funciona em PRoot — rode este script no Orange Pi (Armbian/Debian)."
  fi
  if ! command -v systemctl >/dev/null 2>&1; then
    warn "systemd não encontrado; o serviço waydroid-container precisará ser iniciado manualmente."
  fi
  if [ "$(id -u)" -ne 0 ] && [ "$CHECK_ONLY" -eq 0 ]; then
    die "execute com sudo/root para instalar."
  fi
}

ARCH="$(uname -m)"
check_arch() {
  case "$ARCH" in
    aarch64|armv7l|x86_64) log "arquitetura: $ARCH (suportada)" ;;
    *) die "arquitetura $ARCH não suportada pelo Waydroid." ;;
  esac
}

# ------------------------------------------------------- kernel binder/ashmem
binder_ok() {
  [ -e /dev/binderfs ] && return 0
  ls /dev/binder* >/dev/null 2>&1 && return 0
  grep -qw binder /proc/filesystems 2>/dev/null && return 0
  [ -d /sys/module/binder_linux ] || [ -d /sys/module/binder ] && return 0
  return 1
}

check_kernel() {
  log "kernel: $(uname -r)"
  if binder_ok; then
    log "binder: OK (Android pode rodar)"
    return 0
  fi
  warn "binder/ashmem NÃO encontrados no kernel."
  warn "É necessário um kernel com CONFIG_ANDROID_BINDERFS ou os módulos anbox/waydroid."
  warn "No Armbian, normalmente: sudo apt install anbox-modules-dkms  (e reboot)"
  warn "Verifique também /etc/modules-load.d e o overlay do DTB (binder, ashmem_linux)."
  return 1
}

check_resources() {
  local mem_mb disk_mb
  mem_mb=$(awk '/MemTotal/{print int($2/1024)}' /proc/meminfo 2>/dev/null || echo 0)
  disk_mb=$(df -Pm / 2>/dev/null | awk 'NR==2{print $4}' || echo 0)
  log "memória: ${mem_mb} MB livres  |  disco (/): ${disk_mb} MB livres"
  [ "$mem_mb" -lt 1500 ] && warn "menos de 1,5 GB de RAM: o Android pode ficar lento (Orange Pi 5 recomendado)."
  [ "$disk_mb" -lt 4500 ] && warn "menos de 4,5 GB livres: a imagem do Android pode não caber."
}

check_wayland() {
  if [ "${XDG_SESSION_TYPE:-}" = "wayland" ] || [ -n "${WAYLAND_DISPLAY:-}" ]; then
    log "sessão Wayland: detectada"
  else
    warn "sessão atual não é Wayland (XDG_SESSION_TYPE=${XDG_SESSION_TYPE:-?})."
    warn "O Waydroid precisa de Wayland. No X11, use um compositor aninhado:"
    warn "  sudo apt install cage    &&    cage waydroid show-full-ui"
  fi
}

diagnose() {
  detect_env
  check_arch
  check_kernel || true
  check_resources
  check_wayland
  if command -v waydroid >/dev/null 2>&1; then
    log "waydroid já instalado: $(waydroid --version 2>/dev/null || echo '?')"
  else
    log "waydroid ainda não instalado"
  fi
}

# ---------------------------------------------------------------- instalação ---
install_deps() {
  log "instalando dependências base..."
  export DEBIAN_FRONTEND=noninteractive
  apt-get update -y
  apt-get install -y curl ca-certificates wget gnupg lxc python3 python3-pip
}

add_repo() {
  if [ -f /etc/apt/sources.list.d/waydroid.list ] \
     || grep -rqs "repo.waydro.id" /etc/apt/ 2>/dev/null; then
    log "repositório do Waydroid já configurado"
    return
  fi
  log "adicionando repositório oficial do Waydroid..."
  curl -fsSL https://repo.waydro.id/ | bash
}

install_waydroid() {
  log "instalando o Waydroid..."
  apt-get install -y waydroid
}

init_image() {
  log "baixando a imagem do Android ($IMAGE_TYPE) — pode demorar bastante..."
  if [ "$IMAGE_TYPE" = "GAPPS" ]; then
    waydroid init -s GAPPS
  else
    waydroid init
  fi
}

enable_service() {
  if command -v systemctl >/dev/null 2>&1; then
    log "habilitando o serviço waydroid-container..."
    systemctl enable --now waydroid-container || warn "não foi possível iniciar o serviço agora."
  fi
}

enable_multi_window() {
  # Faz cada app Android abrir como uma janela separada do Linux.
  if command -v waydroid >/dev/null 2>&1; then
    waydroid prop set persist.waydroid.multi_windows true 2>/dev/null \
      && log "modo multi-janela ativado" \
      || warn "não foi possível ativar o multi-janela (faça após iniciar a sessão)."
  fi
}

final_hint() {
  cat <<'EOT'

[waydroid] Instalação concluída.

Próximos passos:
  1) Inicie a sessão em um ambiente Wayland (ou com compositor aninhado):
       cage waydroid show-full-ui          # janela cheia
       waydroid session start &            # sessão em segundo plano
  2) Abra um app Android específico como janela:
       waydroid app list                   # lista os pacotes
       waydroid app launch com.android.settings
  3) Instale um APK baixado:
       waydroid app install /caminho/app.apk
  4) Ative janelas separadas por app (modo multi-janela):
       waydroid prop set persist.waydroid.multi_windows true

Dentro do OpenDash, o "Waydroid" aparece como um aplicativo do sistema; a UI web
não incorpora janelas Android (elas abrem em janela própria do compositor).
EOT
}

main() {
  if [ "$CHECK_ONLY" -eq 1 ]; then
    log "modo diagnóstico (--check): nada será instalado"
    diagnose
    exit 0
  fi

  detect_env
  check_arch
  if ! check_kernel; then
    die "kernel sem binder/ashmem. Instale os módulos (ex.: anbox-modules-dkms), reinicie e rode de novo. Dica: ./install_waydroid.sh --check"
  fi
  check_resources
  check_wayland

  install_deps
  add_repo
  install_waydroid
  init_image
  enable_service
  enable_multi_window
  final_hint
}

main "$@"
