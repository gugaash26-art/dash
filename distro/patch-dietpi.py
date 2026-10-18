#!/usr/bin/env python3
"""Aplica as configuracoes do OpenDash OS em um dietpi.txt existente."""
import argparse
import re
import sys

BLOCK = "##### OpenDash OS #####"


def set_key(text: str, key: str, value: str):
    pattern = re.compile(r"^[ \t]*#?[ \t]*" + re.escape(key) + r"[ \t]*=.*$", re.M)
    line = f"{key}={value}"
    if pattern.search(text):
        return pattern.sub(line, text, count=1), True
    return text, False


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("src")
    ap.add_argument("dst")
    ap.add_argument("--set", action="append", default=[], metavar="CHAVE=VALOR")
    args = ap.parse_args()

    with open(args.src, encoding="utf-8", errors="replace") as fh:
        text = fh.read().replace("\r\n", "\n")

    missing = []
    for item in args.set:
        if "=" not in item:
            print(f"ignorando (sem '='): {item}", file=sys.stderr)
            continue
        key, value = item.split("=", 1)
        key = key.strip()
        value = value.strip()
        if not key or "\n" in value or "\r" in value:
            print(f"valor invalido para {key!r}", file=sys.stderr)
            return 2
        text, found = set_key(text, key, value)
        if not found:
            missing.append(f"{key}={value}")

    if missing:
        if BLOCK not in text:
            text = text.rstrip("\n") + "\n\n" + BLOCK + "\n"
        text = text.rstrip("\n") + "\n" + "\n".join(missing) + "\n"

    with open(args.dst, "w", encoding="utf-8", newline="\n") as fh:
        fh.write(text)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
