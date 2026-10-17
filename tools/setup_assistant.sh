#!/usr/bin/env bash
set -euo pipefail

HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
MODEL="base"
SKIP_APT=0
WHISPER_DIR="$HERE/third_party/whisper.cpp"
MODELS_DIR="$HERE/models"

for arg in "$@"; do
  case "$arg" in
    --model) shift; MODEL="${1:-base}" ;;
    --model=*) MODEL="${arg#*=}" ;;
    --no-apt) SKIP_APT=1 ;;
    -h|--help)
      echo "uso: ./tools/setup_assistant.sh [--model base|small|medium] [--no-apt]"
      echo "  instala o assistente de voz: alsa-utils, ffmpeg, whisper.cpp e edge-tts"
      exit 0 ;;
  esac
done

say() { printf "\033[1;35m[assistente]\033[0m %s\n" "$1"; }

if [ "$SKIP_APT" -eq 0 ]; then
  say "instalando dependencias do sistema (apt)"
  sudo apt-get update -y
  sudo apt-get install -y alsa-utils ffmpeg git cmake build-essential python3-pip || true
fi

# ---------------------------------------------------------------- whisper.cpp
if [ ! -x "$WHISPER_DIR/build/bin/whisper-cli" ]; then
  say "compilando whisper.cpp (voz -> texto)"
  mkdir -p "$(dirname "$WHISPER_DIR")"
  if [ ! -d "$WHISPER_DIR/.git" ]; then
    git clone --depth 1 https://github.com/ggml-org/whisper.cpp "$WHISPER_DIR"
  fi
  cmake -S "$WHISPER_DIR" -B "$WHISPER_DIR/build" -DCMAKE_BUILD_TYPE=Release
  cmake --build "$WHISPER_DIR/build" -j --config Release
  WHISPER_BIN="$WHISPER_DIR/build/bin/whisper-cli"
  if command -v sudo >/dev/null && [ -w /usr/local/bin ]; then
    sudo ln -sf "$WHISPER_BIN" /usr/local/bin/whisper-cli
  fi
else
  say "whisper.cpp ja compilado"
fi

# ------------------------------------------------------------------- modelo
mkdir -p "$MODELS_DIR"
MODEL_FILE="$MODELS_DIR/ggml-$MODEL.bin"
if [ ! -f "$MODEL_FILE" ]; then
  say "baixando modelo Whisper '$MODEL' (pode demorar)"
  URL="https://huggingface.co/ggerganov/whisper.cpp/resolve/main/ggml-$MODEL.bin"
  if command -v curl >/dev/null; then
    curl -L --fail -o "$MODEL_FILE" "$URL"
  else
    wget -O "$MODEL_FILE" "$URL"
  fi
fi
say "modelo em $MODEL_FILE"

# --------------------------------------------------------------------- TTS
say "instalando edge-tts no virtualenv"
if [ -x "$HERE/.venv/bin/pip" ]; then
  "$HERE/.venv/bin/pip" install --quiet edge-tts || true
else
  python3 -m pip install --quiet --break-system-packages edge-tts || true
fi

say "pronto!"
echo
echo "  Configure a chave da IA Groq (gratuita em https://console.groq.com/keys):"
echo "    echo 'GROQ_API_KEY=gsk_...' > $HERE/data/agent.env && chmod 600 $HERE/data/agent.env"
echo "  (arquivo ignorado pelo git; tambem aceita 'export GROQ_API_KEY=...'"
echo "   ou colar a chave em Ajustes > Assistente de voz (IA) no painel.)"
echo
echo "  Ajuste em config.yaml > agent:"
echo "    whisper_model: $MODEL_FILE"
echo "    mic_device: default   # veja os dispositivos com: arecord -l"
echo
echo "  Teste o microfone:  arecord -d 3 -f S16_LE -r 16000 -c 1 /tmp/teste.wav && aplay /tmp/teste.wav"
