# OpenDash — painel automotivo estilo Tesla para Orange Pi + Arduino

Painel digital completo (cluster + energia + mídia + clima + diagnóstico) que roda no
**Orange Pi** com tela touch, lendo os sensores do carro por um **Arduino** (OBD‑II via
CAN bus + sensores analógicos e digitais). Interface web em tela cheia (kiosk),
tema escuro estilo Tesla, animações suaves e alertas em tempo real.

```
┌────────────────────┐   USB serial    ┌──────────────────────────┐   WebSocket   ┌──────────────┐
│  Arduino Mega      │  (JSON @115200) │  Orange Pi               │  (10 Hz)      │  Tela touch  │
│  OBD‑II (MCP2515)  │ ───────────────▶│  server Python (stdlib)  │ ─────────────▶│  Chromium    │
│  sensores analóg.  │ ◀─────────────── │  SQLite (viagens, DTC)   │  REST + WS    │  kiosk       │
│  entradas digitais │   comandos      │  simulação embutida      │               │  UI web      │
└────────────────────┘                 └──────────────────────────┘               └──────────────┘
```

---

## 1. Recursos

**Painel (cluster)**
- Velocímetro com arco animado em SVG, marcha (P/R/N/D/S), autonomia, odômetro e viagem
- Conta-giros em barra segmentada com zona vermelha, acelerador e carga do motor
- Medidores circulares: água, óleo (pressão), bateria, carga
- Ícones de status: setas, faróis, alto, pisca, freio de mão, cinto, portas, injeção (MIL)
- Nível de combustível com barra vertical colorida (verde/âmbar/vermelho)

**Energia**
- Nível do tanque em litros, autonomia calculada, consumo instantâneo e médio
- Gráfico dos últimos 15 minutos (velocidade, temperatura da água, combustível)
- Viagens salvas em SQLite (distância, duração, velocidade média/máxima, litros)

**Mídia e Clima**
- Player de interface (fontes: rádio/Bluetooth/USB/aux, progresso e volume)
- Climatização: velocidade do ventilador (0–4) e ar‑condicionado **enviam comandos
  reais ao Arduino**, que aciona os relés configurados

**Diagnóstico**
- Leitura e limpeza de códigos DTC (modo 03/04), descrição em português
- Grade de sensores em tempo real, status do link serial/OBD
- Botão “simular falha” para demonstrar alertas na bancada

**Navegação (GPS)**
- Mapa **OpenStreetMap** (Leaflet) com posição, rastro percorrido e rumo; Google opcional
- HUD com latitude/longitude, velocidade do GPS, satélites, altitude, HDOP e fonte
- Busca de endereço (geocodificação) e traçado de rota (**OSRM**), com botão centralizar
- GPS vindo do **Arduino** (NMEA no `Serial1`) ou de um módulo **USB** no Orange Pi,
  com detecção automática da fonte

**Apps (lançador)**
- Grade de aplicativos com YouTube, Spotify, Mapas e navegador embutido (páginas web)
- Overlay em tela cheia com recarregar e “abrir em nova aba”
- **Cadastro de apps** (lojinha): adicione qualquer serviço informando nome e URL
- Como não há instalação de apps nativos, cada app é uma página web incorporada
  (para apps **Android nativos** reais, veja o **Waydroid** opcional na seção 10)

**Ajustes**
- Unidades (km/h↔mph, °C↔°F, L↔gal), tema claro/escuro/auto, brilho, animação de boot
- Modo simulação (sem Arduino), porta serial, tanque, consumo nominal, odômetro, nome do carro
- Reiniciar/desligar (opcional, requer `CARDASH_ALLOW_POWER=1`)

**Sistema**
- Alertas em tempo real com histerese e reconhecimento por toque (∞ superaquecimento,
  bateria baixa, combustível, pressão de óleo, cinto, porta, freio de mão, sem comunicação)
- Som de seta (clique) e bipes de alerta via WebAudio
- Navegação por toque, **swipe** lateral e setas do teclado
- Modo simulação embutido para desenvolver/testar sem o carro

---

## 2. Hardware

| Item | Sugestão |
|---|---|
| Computador de bordo | Orange Pi Zero 3 / 3 / 5 / PC (Debian/Armbian) |
| Tela | HDMI touch (1024×600 ou 800×480) |
| Microcontrolador | Arduino Mega 2560 (**recomendado** — pinos suficientes) |
| CAN bus | Módulo MCP2515 (TJA1050) 5 V com cristal 8 ou 16 MHz |
| Sensores | Pressão de óleo 0,5–4,5 V, nível de combustível (boia), temperatura de óleo |
| Alimentação | Conversor DC‑DC 12 V → 5 V 3 A (**com fusível** de 2–3 A) |

> O Arduino Uno funciona apenas com conjunto reduzido (ver seção 8 – FAQ).

### 2.1 Ligação do Arduino Mega

**Barramento CAN / tomada OBD‑II**

| MCP2515 | Arduino Mega | OBD‑II |
|---|---|---|
| VCC | 5V | 16 (+12 V, opcional) |
| GND | GND | 4/5 |
| CS | D10 | — |
| SCK | D52 | — |
| SI (MOSI) | D51 | — |
| SO (MISO) | D50 | — |
| CAN‑H | — | pino 6 |
| CAN‑L | — | pino 14 |

**Sensores analógicos**

| Sensor | Pino | Calibração (config.h) |
|---|---|---|
| Pressão do óleo (0,5–4,5 V) | A0 | `OIL_PSI_MIN_V`, `OIL_PSI_MAX` |
| Nível de combustível (boia) | A1 | `FUEL_ADC_EMPTY`, `FUEL_ADC_FULL` |
| Temperatura do óleo (0,5–4,5 V) | A2 | `OILT_SCALE` |
| Tensão da bateria (divisor) | A3 | `BATT_DIVIDER` |

Divisor de tensão para A3 (12 V → ~3–4 V): **R1 = 30 kΩ** (do +12 V para A3) e
**R2 = 10 kΩ** (de A3 para GND) → `BATT_DIVIDER = 4.0`. Nunca ligue 12 V direto no pino.

**Entradas digitais** (chave para GND, usa `INPUT_PULLUP` — ativo em LOW)

| Função | Pino | Função | Pino |
|---|---|---|---|
| Seta esquerda | D2 | Cinto | D7 |
| Seta direita | D3 | Porta aberta | D8 |
| Farol baixo | D4 | Pisca alerta | D9 |
| Farol alto | D5 | Ignição (pós‑chave) | D22 |
| Freio de mão | D6 | | |

**Saídas**

| Saída | Pino | Uso |
|---|---|---|
| Buzzer ativo | D12 | aviso sonoro |
| LED status | D13 | pisca = OBD online |
| Relé ventilador | D44 | clima (passo > 0) |
| Relé ar‑condicionado | D45 | clima (A/C ligado) |

---

## 3. Software do Arduino

1. Instale a IDE do Arduino e a biblioteca **MCP_CAN** (Library Manager →
   “mcp_can by coryjfowler”) ou Seeed “CAN_BUS_Shield”.
2. Abra `arduino/car_dash/car_dash.ino` (ajuste `config.h` se necessário:
   pinos, cristal do MCP2515, calibração dos sensores).
3. Selecione **Arduino Mega 2560** e grave.
4. Sem CAN conectado o firmware entra em **modo demo** e envia dados sintéticos
   (útil para testes de bancada). Desative com `DEMO_WITHOUT_CAN 0`.

Formato enviado pela serial (1 linha JSON a cada 100 ms):

```json
{"v":1,"ms":12345,"obd":1,"mil":0,"dtcn":0,"speed":64,"rpm":2340,"coolant":88,
 "iat":30,"oilt":90,"throttle":12,"fuel":61,"volt":14.12,"oilp":42.0,"batt":14.0,
 "runtime":900,"load":34,"hl":1,"hb":0,"lt":0,"rt":0,"hz":0,"brk":0,"sbl":0,
 "door":0,"ign":1,"fan":0,"ac":0,"dtc":[]}
```

Comandos aceitos (linhas JSON enviadas pelo servidor):

```json
{"cmd":"climate","fan":2,"ac":1}
{"cmd":"beep","ms":250}
{"cmd":"dtc_read"}   {"cmd":"dtc_clear"}   {"cmd":"reset"}
```

Ferramenta de bancada para inspecionar a serial:

```bash
python3 tools/serial_monitor.py --port /dev/ttyUSB0 --baud 115200
```

---

## 4. Instalação no Orange Pi

Pré‑requisitos: Armbian/Debian com acesso à internet e um usuário com `sudo`.

```bash
git clone <este-repositorio> car-dash      # ou copie a pasta
cd car-dash
./install.sh                               # instala deps, venv, serviço systemd
./install.sh --kiosk                       # (opcional) autostart do navegador kiosk
```

O instalador:
- instala `python3-venv`, `python3-pip` e o navegador (`chromium`) via apt;
- cria o virtualenv `.venv` e instala `pyserial` e `PyYAML`;
- adiciona seu usuário ao grupo `dialout` (acesso à serial);
- registra o serviço **`cardash.service`** (inicia no boot) e o habilita.

### Instalação manual

```bash
sudo apt update
sudo apt install -y python3-venv python3-pip curl
python3 -m venv .venv
./.venv/bin/pip install -r requirements.txt
./.venv/bin/python run.py                  # http://IP:8080
```

### Modo simulação (sem Arduino)

Ative em **Ajustes → Conexão e modo → Modo simulação**, ou no `config.yaml`:

```yaml
simulation:
  enabled: true
```

### Kiosk na tela do carro

```bash
./kiosk/kiosk.sh          # abre o navegador em tela cheia já apontando ao painel
```
O `install.sh --kiosk` cria o autostart em `~/.config/autostart/cardash-kiosk.desktop`
para abrir sozinho após o login automático do desktop.

---

## 5. Uso do painel

| Ação | Resultado |
|---|---|
| Tocar nas abas / **swipe** lateral / **← →** | troca de página |
| Tocar em um alerta | reconhece (remove) aquele aviso |
| Tecla **D** | reconhece todos os alertas |
| Diagrama de RPM > 85 % | zona vermelha |
| Aba **Diagnóstico** | ler/apagar códigos e ver sensores ao vivo |
| Aba **Navegação** | mapa com GPS, rastro, busca de destino e rota |
| Aba **Apps** | abrir YouTube/Spotify/Mapas/navegador e cadastrar novos apps |

---

## 6. Configuração

`config.yaml` (pode ser sobrescrito pela tela **Ajustes**, que grava no SQLite):

```yaml
server:   { host: 0.0.0.0, port: 8080 }
serial:   { enabled: true, port: /dev/ttyUSB0, baud: 115200, auto_detect: true }
rates:    { broadcast_hz: 10, log_hz: 1 }
thresholds:
  coolant_warn_c: 100
  coolant_crit_c: 106
  volt_warn_v: 12.2
  fuel_warn_pct: 12
  oil_warn_psi: 25
trip:     { fuel_capacity_l: 55, consumption_l100: 8.5, odometer_km: 0 }
units:    { speed: kmh, temp: c, volume: l }
gps:      { enabled: true, source: auto, baud: 9600 }   # source: auto|arduino|usb|off
maps:     { provider: osm, tile_url: "https://tile.openstreetmap.org/{z}/{x}/{y}.png" }
```

> **GPS.** Com `source: auto` o servidor usa o USB (se presente) e, senão, o GPS do
> Arduino. Ajuste em **Ajustes → GPS**; para o GPS USB é preciso pertencer ao grupo
> `dialout` (o instalador já adiciona). Suporta NEO‑6M/8M em 9600/38400 baud.

Variáveis de ambiente:

| Variável | Efeito |
|---|---|
| `CARDASH_CONFIG` | caminho de outro arquivo de configuração |
| `CARDASH_ALLOW_POWER=1` | habilita reiniciar/desligar pela interface |
| `CARDASH_LOG=1` | log detalhado (requisições HTTP, ticks) |

---

## 7. API (para integrar mídia/telemetria)

| Método | Rota | Descrição |
|---|---|---|
| GET | `/api/state` | estado completo atual (JSON) |
| GET | `/api/history?minutes=15` | amostras (1 Hz) para gráficos |
| GET | `/api/trips?limit=20` | viagens salvas |
| GET | `/api/dtc` | códigos ativos |
| POST | `/api/dtc/clear` | apaga códigos |
| GET | `/api/gps/track?minutes=180` | rastro GPS (lat/lon/vel/rumo) |
| GET | `/api/apps` | lista de apps + configuração de mapas |
| POST | `/api/apps` | cria/atualiza app (`{name,url,icon,color,kind}`) |
| DELETE | `/api/apps/{id}` | remove um app |
| GET/POST | `/api/settings` | lê/salva ajustes |
| GET | `/api/system` | versão, conexão, uptime |
| POST | `/api/command` | `{"cmd":"climate","fan":2,"ac":1}`, `beep`, `dtc_read`, `sim_dtc` |
| GET | `/ws` | WebSocket: recebe `{"type":"state","data":{…}}`, envia `{"type":"cmd",…}` |

---

## 8. Estrutura do projeto

```
car-dash/
├── docs/tutorial/         vídeo-tutorial (slides narrados) + gerador
├── arduino/car_dash/      sketch + config.h do Arduino Mega
├── server/               servidor (biblioteca padrão do Python)
│   ├── main.py           HTTP + WebSocket + rotas REST
│   ├── hub.py            serial, estado, viagens, GPS, comandos
│   ├── gps.py            parser NMEA + leitor do GPS USB
│   ├── sim.py            gerador de dados para bancada (inclui GPS)
│   ├── alerts.py         regras de alerta
│   ├── store.py          SQLite (amostras, viagens, DTC, ajustes, apps, rastro)
│   ├── config.py         config.yaml + validação
│   └── ws.py             WebSocket (RFC 6455)
├── ui/                   interface (HTML/CSS/JS, sem build)
│   ├── index.html  css/style.css  js/app.js  js/gauges.js
│   └── vendor/leaflet/   Leaflet (mapa offline, sem CDN)
├── systemd/              serviços cardash.service e kiosk
├── kiosk/kiosk.sh        lançador do navegador em tela cheia
├── tools/                utilitários (monitor serial)
├── run.py                entrada do servidor
├── install.sh            instalador para Orange Pi
├── install_waydroid.sh   instala apps Android (Waydroid) — opcional
└── config.yaml           configuração
```

---

## 9. Solução de problemas

| Sintoma | Causa provável / solução |
|---|---|
| Badge “sem sinal” / `conn: off` | cabo USB, porta errada (`ls /dev/ttyUSB* /dev/ttyACM*`), falta de permissão (`dialout`), Arduino não gravado |
| `obd: 0` no painel | MCP2515 sem resposta — confira CAN‑H/CAN‑L invertidos, cristal (8/16 MHz), terminação 120 Ω e se a ignição está ligada |
| Sensores analógicos errados | ajuste as constantes em `config.h` (calibração) |
| Tela em branco no kiosk | rode `./kiosk/kiosk.sh` no terminal e veja o erro; teste `curl http://127.0.0.1:8080/health` |
| Sem som de seta/alerta | o navegador exige interação; o kiosk já usa `--autoplay-policy=no-user-gesture-required` |
| Não atualiza unidades | salve em Ajustes; o valor fica no SQLite (`data/cardash.db`) |

---

## 10. Apps Android reais (Waydroid, opcional)

Os “apps” da página **Apps** são páginas web incorporadas (rápidas e leves, ideais
para o painel). Se você quiser **aplicativos Android nativos** (Spotify, YouTube,
Waze…), dá para rodar o **Waydroid** — um Android (LineageOS) em contêiner **LXC**
que usa o hardware da própria máquina. No **modo multi‑janela**, cada app Android
abre como uma **janela comum do Linux**, ao lado do OpenDash.

> ⚠️ **Não funciona neste ambiente de desenvolvimento** (PRoot/Termux sobre Android):
> o Waydroid precisa de kernel real e de contêineres LXC. Rode no **Orange Pi com
> Armbian/Debian**. O script detecta PRoot/Termux e aborta com mensagem clara.

**Requisitos**
- Kernel com `binder`/`ashmem` (ou `anbox-modules-dkms` + reboot)
- Sessão **Wayland** (no X11 use um compositor aninhado: `cage`)
- ~4 GB de disco e ~2 GB de RAM livres — **Orange Pi 5 recomendado** (OPi 3/Zero 3 fica no limite)
- Sem Google Play na imagem *vanilla*; para a Play Store use a imagem **GApps**

**Instalação (no Orange Pi)**

```bash
sudo ./install_waydroid.sh --check     # diagnóstico (kernel, binder, RAM, disco, Wayland)
sudo ./install_waydroid.sh             # imagem VANILLA (sem Google)
sudo ./install_waydroid.sh --gapps     # imagem com Google Play
```

O script instala dependências, adiciona o repositório oficial, instala o Waydroid,
baixa a imagem, habilita o serviço `waydroid-container` e ativa o **multi‑janela**.

**Uso**

```bash
cage waydroid show-full-ui              # Android em tela cheia (Wayland)
waydroid app list                       # lista os pacotes instalados
waydroid app launch com.android.settings
waydroid app install /caminho/app.apk   # instala um APK baixado
waydroid prop set persist.waydroid.multi_windows true   # janela por app
```

**Integração com o painel.** A UI web **não** incorpora janelas Android — elas são
janelas do compositor. No kiosk, o prático é abrir o Waydroid em tela cheia por um
atalho (ex.: um item que executa `cage waydroid show-full-ui` e, ao sair, volta ao
painel). A página **Apps** continua sendo a opção leve/instantânea.

---

## 11. Tutorial em vídeo

Em `docs/tutorial/` há um vídeo de **6m47s** (24 cenas com realces visuais e *callouts*,
narração neural em português e música de fundo) cobrindo hardware, ligação, gravação do
Arduino, instalação no Orange Pi, configuração, kiosk, **telas reais da interface**
(incluindo **Navegação** e **Apps**), a **animação de boot** e uma **demonstração final
do sistema rodando em modo simulação**:

```bash
mpv docs/tutorial/opendash-tutorial.mp4     # ou qualquer player
```

Para regerar (requer `ffmpeg` e `edge-tts`, com internet para a voz neural):

```bash
/car-dash/.venv/bin/python docs/tutorial/build_tutorial.py
```

As imagens reais da UI ficam em `docs/tutorial/assets/` e são capturadas por
`docs/tutorial/capture_ui.py` (WebKitGTK + Xvfb, rodando contra o servidor em modo
simulação); ele gera `page_*.png` (uma por página) e `ui-anim.mp4` (animação).
Para recapturar:

```bash
SHOT_URL=http://127.0.0.1:8080/ SHOT_MODE=shots xvfb-run -a -s "-screen 0 1024x600x24" \
  python3 docs/tutorial/capture_ui.py        # screenshots em assets/ (ajuste SHOT_OUT)
SHOT_MODE=video python3 ... capture_ui.py    # sequência de frames para a animação
```

A narração usa a voz neural **pt-BR-ThalitaMultilingualNeural** via `edge-tts` e a
música é gerada por síntese; o roteiro e o visual ficam em `build_tutorial.py`
(ajuste `VOICE`, `RATE`, `PITCH`, `MUSIC_LEVEL` e a lista `SCENES`). Cenas aceitam
`kind: "slide"` (padrão), `"ui"` (usa `assets/page_*.png`, com `callouts` opcionais que
desenham caixas e rótulos sobre a tela) e `"anim"` (usa `assets/ui-anim.mp4`, ou uma
`clip` própria, como `assets/ui-boot.mp4` na cena de boot). Há também
`compare_voices.py`, que compara as vozes pt-BR.

---

## 12. Segurança elétrica (leia)

- Alimente o Orange Pi/Arduino por um **conversor DC‑DC 12 V→5 V com fusível** (2–3 A);
  não use o carregador original na tomada 12 V.
- **Nunca** ligue sinais de 12 V direto nos pinos do Arduino — use divisores/optoacopladores.
- Use o positivo **após a chave de ignição** para desligar tudo com o carro.
- Faça todas as conexões com o carro desligado e a bateria desconectada.
- Este projeto lê dados pela porta OBD‑II; **não** altere a ECU. Modificações no
  veículo são de sua responsabilidade — siga as leis locais e não use comandos que
  interfiram na direção, freios ou airbag.
