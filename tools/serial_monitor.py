#!/usr/bin/env python3
"""Le e imprime o JSON que o Arduino envia pela serial (diagnostico de bancada)."""
import argparse
import json
import sys
import time

try:
    import serial
    from serial.tools import list_ports
except ImportError:
    print("instale o pyserial: pip install pyserial", file=sys.stderr)
    raise SystemExit(1)


def autodetect():
    for p in list_ports.comports():
        if "USB" in p.device or "ACM" in p.device or "AMA" in p.device:
            return p.device
    return None


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--port", default=None)
    ap.add_argument("--baud", type=int, default=115200)
    ap.add_argument("--raw", action="store_true", help="mostra a linha crua")
    ap.add_argument("--send", default=None, help="envia um comando JSON e sai")
    args = ap.parse_args()

    port = args.port or autodetect()
    if not port:
        print("porta nao encontrada; use --port", file=sys.stderr)
        return 1
    print(f"abrindo {port} @ {args.baud}", file=sys.stderr)
    dev = serial.Serial(port, args.baud, timeout=0.5)
    time.sleep(0.5)
    dev.reset_input_buffer()

    if args.send:
        line = (args.send if args.send.strip().startswith("{")
                else json.dumps({"cmd": args.send}))
        dev.write((line + "\n").encode())
        dev.flush()
        print(f"enviado: {line}", file=sys.stderr)

    keys = ["speed", "rpm", "coolant", "iat", "fuel", "volt", "oilp",
            "throttle", "load", "obd", "mil", "dtc"]
    n = 0
    try:
        while True:
            raw = dev.readline().decode("utf-8", "ignore").strip()
            if not raw:
                continue
            n += 1
            if args.raw:
                print(raw)
                continue
            try:
                obj = json.loads(raw)
            except json.JSONDecodeError:
                print("??", raw[:120])
                continue
            if n % 5 == 0:
                summary = "  ".join(f"{k}={obj.get(k)}" for k in keys)
                print(f"[{n:05d}] {summary}")
    except KeyboardInterrupt:
        pass
    finally:
        dev.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
