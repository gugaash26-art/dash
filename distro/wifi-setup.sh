#!/bin/bash
# Primeiro boot: configurar Wi-Fi interativamente caso nao configurado
set -u

LOG=/var/lib/opendash/wifi_setup.log
mkdir -p /var/lib/opendash
if [ "${WIFI_TTY:-0}" = 1 ] && [ -c /dev/tty1 ]; then
  exec </dev/tty1 >/dev/tty1 2>&1
else
  exec >>"$LOG" 2>&1
fi

CFG=/boot/dietpi.txt
[ -f "$CFG" ] || CFG=/boot/firmware/dietpi.txt
WIFI=/boot/dietpi-wifi.txt
[ -f "$WIFI" ] || WIFI=/boot/firmware/dietpi-wifi.txt

need_wifi_config() {
  if [ ! -f "$WIFI" ]; then
    return 0
  fi
  if grep -q '^aWIFI_SSID\[0\]=' "$WIFI" && grep -q '^aWIFI_KEY\[0\]=' "$WIFI"; then
    ssid=$(sed -n 's/^aWIFI_SSID\[0\]=//p' "$WIFI" | tail -1)
    key=$(sed -n 's/^aWIFI_KEY\[0\]=//p' "$WIFI" | tail -1)
    if [ -n "$ssid" ] && [ -n "$key" ] && [ "$ssid" != "mySuperDopeWiFiName" ] && [ "$key" != "mySuperDuperSecureWiFiKey" ]; then
      return 1
    fi
  fi
  return 0
}

if ! need_wifi_config; then
  exit 0
fi

echo "=== Wi-Fi setup $(date -Is) ==="

if command -v nmtui >/dev/null 2>&1; then
  clear
  echo "Primeiro boot: configure Wi-Fi"
  nmtui
elif command -v nmcli >/dev/null 2>&1; then
  clear
  echo "Redes Wi-Fi disponíveis:"
  nmcli device wifi list
  read -p "SSID: " ssid
  read -s -p "Senha: " key; echo
  nmcli device wifi connect "$ssid" password "$key" || true
elif command -v dietpi-config >/dev/null 2>&1 || [ -x /boot/dietpi/dietpi-config ]; then
  clear
  echo "Configure o Wi-Fi em: Network Options: Adapters > WiFi"
  echo "Depois volte e selecione 'Apply'."
  if command -v dietpi-config >/dev/null 2>&1; then
    dietpi-config
  else
    /boot/dietpi/dietpi-config
  fi
else
  echo "Nenhuma ferramenta interativa encontrada; preencha $WIFI e reinicie."
fi
echo "=== fim ==="
