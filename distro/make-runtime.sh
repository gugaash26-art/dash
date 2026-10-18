#!/usr/bin/env bash
# Gera o tarball minimo que vai dentro da imagem (sem docs, hardware ou .git).
set -euo pipefail

HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT="$(cd "$HERE/.." && pwd)"
OUT="${1:-$HERE/out/opendash-runtime.tar.gz}"
mkdir -p "$(dirname "$OUT")"

cd "$ROOT"
tar --sort=name --mtime="@0" --owner=0 --group=0 --numeric-owner \
  --exclude='.git' \
  --exclude='.venv' \
  --exclude='docs' \
  --exclude='data' \
  --exclude='hardware' \
  --exclude='arduino' \
  --exclude='__pycache__' \
  --exclude='*.pyc' \
  --exclude='ui/react/preview.png' \
  -cf - \
  install.sh run.py config.yaml requirements.txt README.md \
  server ui kiosk systemd tools \
  | gzip -9n > "$OUT"

printf '%s  %s\n' "$(sha256sum "$OUT" | awk '{print $1}')" "$(basename "$OUT")" \
  > "$OUT.sha256"
echo "runtime: $OUT ($(du -h "$OUT" | awk '{print $1}'))"
