#!/usr/bin/env bash
set -euo pipefail

HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
SKIP_APT=0
PREFER="auto"

for arg in "$@"; do
  case "$arg" in
    --no-apt) SKIP_APT=1 ;;
    --apt) PREFER="apt" ;;
    --flatpak) PREFER="flatpak" ;;
    -h|--help)
      echo "uso: ./tools/install_gnome_maps.sh [--apt|--flatpak] [--no-apt]"
      echo "  instala o GNOME Maps (app de mapas nativo) via apt ou Flatpak"
      echo "  e habilita o lancamento no painel (CARDASH_ALLOW_NATIVE=1)."
      exit 0 ;;
  esac
done

say() { printf "\033[1;35m[gnome-maps]\033[0m %s\n" "$1"; }

have() { command -v "$1" >/dev/null 2>&1; }

installed_apt() { have gnome-maps; }
installed_flatpak() {
  have flatpak && flatpak info org.gnome.Maps >/dev/null 2>&1
}

if installed_apt || installed_flatpak; then
  say "GNOME Maps ja instalado"
else
  if [ "$PREFER" = "flatpak" ] || { [ "$PREFER" = "auto" ] && ! have apt-get; }; then
    if ! have flatpak; then
      say "instale o Flatpak primeiro (https://flatpak.org/setup/)"; exit 1
    fi
    say "instalando GNOME Maps via Flatpak"
    flatpak remote-add --if-not-exists flathub https://flathub.org/repo/flathub.flatpakrepo || true
    flatpak install -y flathub org.gnome.Maps
  else
    if [ "$SKIP_APT" -eq 0 ]; then
      say "instalando GNOME Maps via apt"
      sudo apt-get update -y
      sudo apt-get install -y gnome-maps || true
    fi
    if ! installed_apt; then
      if have flatpak; then
        say "apt nao encontrou gnome-maps; tentando Flatpak"
        flatpak remote-add --if-not-exists flathub https://flathub.org/repo/flathub.flatpakrepo || true
        flatpak install -y flathub org.gnome.Maps
      else
        say "nao foi possivel instalar pelo apt. Reexecute com --flatpak."
        exit 1
      fi
    fi
  fi
fi

# --------------------------------------------- habilita o lancamento no painel
ENV_FILE="$HERE/data/screens.env"
if [ -f "$ENV_FILE" ] && ! grep -q "CARDASH_ALLOW_NATIVE" "$ENV_FILE" 2>/dev/null; then
  echo "CARDASH_ALLOW_NATIVE=1" >> "$ENV_FILE"
  say "adicionado CARDASH_ALLOW_NATIVE=1 em data/screens.env"
fi

say "pronto!"
echo
echo "  O painel abre o GNOME Maps no display X (config.yaml > native:)."
echo "  Habilite o lancamento com:  export CARDASH_ALLOW_NATIVE=1"
echo "  ou adicione essa linha ao service do painel / data/screens.env."
echo
echo "  Observacao: o GNOME Maps inicia no destino/busca informado,"
echo "  mas a rota precisa ser confirmada dentro do proprio app."
