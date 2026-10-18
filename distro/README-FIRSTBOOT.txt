OpenDash OS - guia rapido (antes do primeiro boot)
==================================================

Esta imagem ja contem o OpenDash e o kiosk. No primeiro boot ela:
  1. instala X11 + Chromium e as dependencias;
  2. instala o OpenDash em /opt/opendash;
  3. configura o autostart no DietPi;
  4. reinicia para abrir o painel.

WI-FI
-----
1. Abra dietpi-wifi.txt e preencha `aWIFI_SSID[0]` e `aWIFI_KEY[0]`.
2. Abra dietpi.txt e mude:
     AUTO_SETUP_NET_WIFI_ENABLED=1
   (o pais ja vem como BR; ajuste AUTO_SETUP_NET_WIFI_COUNTRY_CODE se preciso)

MODO DE TELA (dietpi.txt)
-------------------------
  OPENDASH_MODE=kiosk         uma tela (padrao)
  OPENDASH_MODE=duo           painel completo + cluster em barra
  OPENDASH_MODE=cluster       painel completo + velocimetro redondo
  OPENDASH_MODE=bar           somente cluster em barra (2a tela)
  OPENDASH_MODE=cluster-only  somente velocimetro redondo (2a tela)

  OPENDASH_TOUCH_SIZE=1024,600   tela principal
  OPENDASH_BAR_SIZE=1920,480     segunda tela
  OPENDASH_TOUCH_POS=0,0
  OPENDASH_BAR_POS=1024,0

  OPENDASH_BROWSER=chromium      navegador (padrao)
  OPENDASH_BROWSER=app           app nativo WebKitGTK (instala WebKit no boot)

OUTROS
------
  OPENDASH_CAR_NAME=OpenDash    nome no painel
  OPENDASH_REBOOT=1             reinicia sozinho ao terminar (0 = nao)

ACESSO
------
  Painel: http://opendash.local:8080 (ou http://IP:8080)
  Usuario: root   Senha: opendash   (SSH desativado por padrao)
  Para ativar SSH: dietpi-config > SSH, ou edite AUTO_SETUP_SSH_SERVER_INDEX
  em dietpi.txt antes do primeiro boot. Troque a senha com "passwd".

Se algo falhar, entre no console (HDMI/teclado) e rode:
  sudo /boot/Automation_Custom_Script.sh
  # ou, depois do primeiro boot:
  sudo /opt/opendash/firstboot.sh
Log: /var/lib/opendash/firstboot.log
