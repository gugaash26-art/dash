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
- **Papel de parede** da página Mídia: use uma **URL** ou **envie uma imagem** do
  aparelho (PNG/JPG/WEBP/GIF/BMP, até 8 MB); a imagem fica salva e é restaurada sozinha
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
- **Apps nativos** do sistema (ex.: **GNOME Maps**) abrem direto no painel, via
  URI `geo:`/`maps:` (para apps **Android nativos** reais, veja o **Waydroid** na seção 10)

**Assistente de voz (IA)**
- **Push‑to‑talk**: segure o botão na página **Mídia**, fale e solte — o assistente
  entende e executa (abrir app, tocar música, traçar rota, mexer no clima, trocar de página)
- **100% gratuito e de código aberto**: voz→texto com **whisper.cpp**, respostas com uma
  IA **OpenAI‑compatível** (padrão **Groq**, grátis) e fala com **edge‑tts**
- Também aceita **texto** (caixa de digitação) — útil para testar sem microfone

**Conectividade (Wi‑Fi e Bluetooth)**
- **Wi‑Fi**: liga/desliga o rádio, lista as redes, conecta (com senha) e desconecta —
  direto pela tela **Ajustes** (usa o NetworkManager/`nmcli`)
- **Bluetooth**: liga/desliga, procura aparelhos (celular, caixa de som), pareia,
  conecta e desconecta (usa o BlueZ/`bluetoothctl`)
- Sem as ferramentas instaladas o painel apenas informa o que falta — nada quebra

**Atualizações via GitHub**
- Um botão em **Ajustes → Atualizações do sistema** verifica se você subiu commits
  novos no repositório, **baixa e instala** (`git pull` + dependências) e reinicia o painel
- Verificação automática ao ligar e a cada algumas horas, com aviso no painel

**Telas (monitores HDMI)**
- Ao ligar um **HDMI**, o painel detecta os monitores (`xrandr`) em **Ajustes → Telas e
  monitores** e deixa você **escolher o que vai em cada um**: painel principal (com menus) e
  segunda tela — painel de velocidade (velocímetro, sem menus) ou cluster em barra
- Opcionalmente organiza sozinho (segunda tela à direita do painel) e grava a geometria em
  `data/screens.env`, posicionando as janelas e reiniciando o kiosk

**Mapas nativos (GNOME Maps)**
- Abre o **GNOME Maps instalado no sistema** direto da página **Navegação**, levando o
  destino/coordenadas para o app (URI `geo:`/`maps:`); instala com `tools/install_gnome_maps.sh`
- Lançamento habilitado por `CARDASH_ALLOW_NATIVE=1` (segurança); a rota é iniciada no app

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
./install.sh --app --cluster               # (opcional) aplicativo nativo: painel + painel de velocidade
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

### Aplicativo nativo (sem navegador)

Além do navegador em modo kiosk, o OpenDash pode rodar como um **aplicativo nativo**
(uma janela própria, **sem barra de endereço, abas ou qualquer cara de navegador**),
usando **WebKitGTK**. É o mesmo motor web por baixo, mas vira um "app" de verdade — com
atalho no menu e autostart — em vez de abrir o Chromium:

```bash
sudo ./install.sh --app --cluster    # app nativo: painel completo (menus) + painel de velocidade
# ou
sudo ./install.sh --app --kiosk      # app nativo em uma tela só (painel completo)
```

Isso instala as dependências (`python3-gi`, `gir1.2-gtk-3.0` e `gir1.2-webkit2-4.1`),
registra o atalho `/usr/share/applications/opendash.desktop` e faz os serviços do kiosk
usarem a janela nativa (`CARDASH_APP=1`) em vez do navegador. O lançador é
`kiosk/opendash.py` e aceita as mesmas variáveis do kiosk:

```bash
CARDASH_SCREEN=cluster CARDASH_CLUSTER_SIZE=1280,400 CARDASH_CLUSTER_POS=1024,0 \
  python3 kiosk/opendash.py            # abre o painel de velocidade numa janela nativa
python3 kiosk/opendash.py --print      # só imprime a URL e a geometria, sem abrir janela
```

Para abrir uma janela sem moldura, em tela cheia, escondendo o cursor (padrão), com
`F11` alternando tela cheia e `Ctrl+Q` para sair. Em placas antigas (ex.: H618) use
`CARDASH_SOFTWARE=1` para desligar a aceleração de hardware do WebKit.

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

### Duas telas (painel com menus + painel de velocidade)

O OpenDash tem **três interfaces** no mesmo servidor:

| Tela | URL | Indicada para |
|---|---|---|
| **Painel completo** | `/` (ou `/?screen=full`) | touch 8" — todas as páginas, apps e **menus** |
| **Painel de velocidade** | `/?screen=cluster` | segunda tela — **velocímetro redondo, sem menus** |
| **Cluster em barra** | `/bar.html` (ou `/?screen=bar`) | monitor longo tipo **1920×480** (11.3"/8.8"/7.9") |

O **painel de velocidade** (`?screen=cluster`) é a mesma tela do velocímetro redondo do
painel completo, mas **isolada**: mostra velocímetro, marcha, rotação, indicadores, tanque,
mini‑medidores e odômetro — e **esconde as abas/menus** e o widget de mídia, para ficar
numa HDMI dedicada (a multimídia com menus fica na outra). Os menus **só** aparecem no
painel completo (`/`).

O **cluster em barra** mostra, lado a lado: setas e indicadores, **velocímetro** com marcha,
**rotação** + acelerador, autonomia/odômetro/viagem, resumo (consumo, combustível, água),
mini‑medidores (água, óleo, bateria, carga) e o **tanque** vertical. Ele lê o mesmo
estado em tempo real, com alertas e relógio.

Para rodar as duas juntas (mesmo servidor X, lado a lado):

```bash
# geometria de cada tela (ajuste às suas resoluções/posições)
export CARDASH_TOUCH_SIZE=1024,600 CARDASH_TOUCH_POS=0,0
export CARDASH_BAR_SIZE=1920,480   CARDASH_BAR_POS=1024,0

sudo ./install.sh --cluster   # painel completo (com menus) + painel de velocidade (sem menus)
# ou
sudo ./install.sh --duo       # painel completo (com menus) + cluster em barra
```

`--cluster` cria/ativa `cardash-kiosk.service` (painel completo, com menus) e
`cardash-kiosk-cluster.service` (painel de velocidade, sem menus); `--duo` usa o
`cardash-kiosk-bar.service` (barra) no lugar do segundo. Para uma tela só, o
`./install.sh --kiosk` continua valendo. Também dá para abrir manualmente:

```bash
CARDASH_SCREEN=cluster CARDASH_BAR_SIZE=1920,480 CARDASH_BAR_POS=1024,0 ./kiosk/kiosk.sh
```

**Escolher o monitor pela tela:** depois de instalar, abra **Ajustes → Telas e monitores
(HDMI)**, toque em **Detectar** e escolha qual monitor recebe o **painel principal** e qual
recebe a **segunda tela** (barra ou velocidade, conforme o kiosk instalado); marque
*Organizar sozinho* se quiser a segunda tela à direita do painel. O servidor descobre a
geometria com `xrandr`, grava `data/screens.env` e reinicia os serviços do kiosk. As janelas
são posicionadas exatamente sobre cada monitor.

> **Hardware:** duas saídas de vídeo dependem da placa — **RK3588 (Orange Pi 5)** tem
> 2× HDMI; **H6 (Orange Pi 3)** costuma ter 1× HDMI (use um adaptador USB→HDMI ou uma
> placa com duas saídas). Alternativamente, use dois servidores X (`DISPLAY=:0` e `:1`).

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
agent:                                                   # assistente de voz (seção 12)
  enabled: true
  whisper_bin: whisper-cli
  whisper_model: models/ggml-base.bin
  stt_lang: pt
  mic_device: default
  record_seconds: 6
  llm_base_url: "https://api.groq.com/openai/v1"        # qualquer IA OpenAI-compatível
  llm_model: llama-3.3-70b-versatile
  llm_key_env: GROQ_API_KEY                              # nome da variável de ambiente
  llm_key: ""                                            # ou cole a chave aqui
  tts: edge
  tts_voice: pt-BR-ThalitaMultilingualNeural
  speak: true
  play_local: false
  spotify_client_id: ""
  spotify_client_secret: ""
update:                                                  # atualização via GitHub (seção 13)
  enabled: true
  remote: origin
  branch: main
  auto_check: true
  check_hours: 6
  install_deps: true
  restart_command: ""                                    # vazio: systemctl restart cardash ou re-exec
media:                                                   # papel de parede da página Mídia
  wallpaper: ""                                          # URL externa ou /media/wallpaper (upload)
  fit: cover                                             # cover | contain | fill
screens:                                                 # escolha de monitores HDMI (seção 5)
  enabled: false                                         # true após aplicar em Ajustes > Telas
  main: HDMI-1                                           # saída xrandr do painel principal
  bar: HDMI-2                                            # saída xrandr do cluster em barra
  arrange: false                                         # organiza o cluster à direita do painel
  display: ":0"                                          # servidor X usado para detectar monitores
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
| GET | `/api/agent` | estado do assistente (mic, STT, IA, TTS) |
| POST | `/api/agent/ask` | `{"text":"..."}` → resposta + ações + áudio |
| POST | `/api/agent/listen/start` | inicia a gravação do microfone (push‑to‑talk) |
| POST | `/api/agent/listen/stop` | encerra, transcreve e responde (via chat/WS) |
| POST | `/api/agent/say` | `{"text":"..."}` → áudio TTS em base64 |
| GET | `/api/network` | status do Wi‑Fi e do Bluetooth (+ ferramentas disponíveis) |
| GET | `/api/wifi?scan=1` | lista de redes Wi‑Fi (com `scan=1` reescaneia) |
| POST | `/api/wifi` | `{"action":"scan\|connect\|disconnect\|forget\|enable\|disable","ssid":…,"password":…}` |
| GET | `/api/bluetooth` | aparelhos Bluetooth conhecidos |
| POST | `/api/bluetooth` | `{"action":"scan\|pair\|connect\|disconnect\|remove\|enable\|disable","mac":…}` |
| GET | `/api/update` | versão atual, remoto e se há atualização |
| POST | `/api/update` | `{"action":"check\|install\|restart","restart":true}` |
| GET | `/api/media` | papel de parede atual da Mídia (`wallpaper`, `fit`) |
| POST | `/api/media/wallpaper` | `{"url":"https://…"}`, `{"data":"data:image/…;base64,…"}` ou `{"clear":true}` |
| GET | `/media/wallpaper` | serve a imagem de papel de parede enviada (upload) |
| GET | `/api/screens` | monitores detectados (`xrandr`) + escolha atual painel/cluster |
| POST | `/api/screens` | `{"main":"HDMI-1","bar":"HDMI-2","arrange":true,"enabled":true}` aplica e reinicia o kiosk |
| GET | `/api/native` | apps nativos disponíveis (GNOME Maps) + se o lançamento está habilitado |
| POST | `/api/native/launch` | `{"app":"gnome-maps","lat":…,"lon":…}` ou `{"query":"…"}` abre o app nativo |
| POST | `/api/native/close` | `{"app":"gnome-maps"}` fecha o app nativo |
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
│   ├── agent.py          assistente de voz (STT + IA + TTS + ações)
│   ├── net.py            Wi-Fi (nmcli) e Bluetooth (bluetoothctl)
│   ├── updater.py        atualização via Git (verificar/instalar/reiniciar)
│   ├── screens.py        monitores HDMI (xrandr) + escolha painel/cluster
│   ├── wallpaper.py      papel de parede da Mídia (URL ou upload)
│   ├── native.py         apps nativos (GNOME Maps) — abrir/fechar
│   ├── sim.py            gerador de dados para bancada (inclui GPS)
│   ├── alerts.py         regras de alerta
│   ├── store.py          SQLite (amostras, viagens, DTC, ajustes, apps, rastro)
│   ├── config.py         config.yaml + validação
│   └── ws.py             WebSocket (RFC 6455)
├── ui/                   interface (HTML/CSS/JS, sem build)
│   ├── index.html        painel completo (touch) e painel de velocidade (?screen=cluster)
│   ├── bar.html          cluster em barra (ex.: 1920x480)
│   ├── css/style.css  css/bar.css
│   ├── js/app.js  js/bar.js  js/gauges.js
│   └── vendor/leaflet/   Leaflet (mapa offline, sem CDN)
├── systemd/              cardash.service, kiosk, kiosk-bar e kiosk-cluster
├── kiosk/kiosk.sh        lançador do navegador em tela cheia (ou do app nativo)
├── kiosk/opendash.py     aplicativo nativo (WebKitGTK, sem navegador)
├── kiosk/opendash.desktop  atalho do aplicativo (menu/autostart)
├── tools/                utilitários (monitor serial, setup do assistente, GNOME Maps)
├── models/               modelo do Whisper (baixado pelo setup_assistant.sh)
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

Em `docs/tutorial/` há **três** vídeos, com narração neural em português e música:

### Tutorial com avatar (novidades do sistema) — `opendash-tutorial-avatar.mp4`

Um vídeo de **5m20s** (20 cenas) **apresentado por um avatar** que fala no canto da tela
(e abre e encerra acenando). Ele mostra o painel e, principalmente, as **novas funções**:
o **assistente de voz** com IA, o **Wi-Fi** e o **Bluetooth** nas configurações, a
**atualização pelo GitHub** e o **cluster em barra** para segunda tela.

```bash
mpv docs/tutorial/opendash-tutorial-avatar.mp4
```

Para regerar (precisa do avatar e das telas novas):

```bash
python3 docs/tutorial/capture_avatar.py      # gera os PNGs do avatar (fundo transparente)
SHOT_URL=http://127.0.0.1:8099/ python3 docs/tutorial/capture_new_ui.py   # telas novas
/car-dash/.venv/bin/python docs/tutorial/build_tutorial_avatar.py
```

O avatar é um **SVG** (`docs/tutorial/avatar.html`) renderizado por `capture_avatar.py`
(WebKitGTK + Xvfb, com canal alfa) em quatro poses — parado, falando, piscando e acenando —
que o roteiro sobrepõe com `overlay` e expressões `enable` para dar vida à boca e aos olhos.
As telas novas (Wi-Fi/Bluetooth, atualizações, assistente e o cluster) são capturadas por
`capture_new_ui.py`, que também injeta dados de demonstração para os cartões aparecerem
preenchidos. O roteiro e o visual ficam em `build_tutorial_avatar.py` (lista `SCENES`,
com `kind: "slide"`, `"ui"`, `"anim"` e `"presenter"`).

### Tutorial de instalação — `opendash-tutorial.mp4`

Um vídeo de **6m47s** (24 cenas com realces visuais e *callouts*) cobrindo hardware,
ligação, gravação do Arduino, instalação no Orange Pi, configuração, kiosk, **telas reais
da interface** (incluindo **Navegação** e **Apps**), a **animação de boot** e uma
**demonstração final do sistema rodando em modo simulação**:

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

### Tutorial de instalação passo a passo (Debian/Armbian) — `opendash-tutorial-instalacao.mp4`

Um vídeo de **5m28s** (20 cenas) **do zero até o painel rodando**, com todos os comandos
num painel de **terminal** e o avatar narrando. Cobre **Debian 12 e Armbian** numa Orange Pi
Zero 3, em **12 passos**: baixar a imagem, gravar o cartão SD, primeiro boot e SSH, atualizar
o sistema, instalar a base, baixar o OpenDash, rodar o `install.sh`, testar no navegador,
kiosk em tela cheia e os extras (Arduino/GPS, assistente de voz e GNOME Maps nativo), além
de dicas para 1.5 GB de RAM:

```bash
mpv docs/tutorial/opendash-tutorial-instalacao.mp4
```

Para regerar (requer `ffmpeg`, `ffprobe` e `edge-tts`, com internet para a voz):

```bash
python3 docs/tutorial/capture_avatar.py        # uma vez: gera os PNGs do avatar
/car-dash/.venv/bin/python docs/tutorial/build_tutorial_install.py
```

O roteiro fica em `build_tutorial_install.py` (lista `SCENES`). É o mesmo motor dos outros
vídeos, com um tipo de cena a mais: `kind: "term"`, que desenha um **painel de terminal**
com `term_title` e `lines` (linhas começando com `#` viram comentários em cinza; as demais
ganham o prompt verde `$`). Para teste rápido, use `TUT_ONLY=4` para gerar só as primeiras
cenas.

---

## 12. Assistente de voz (IA) — grátis e de código aberto

Na página **Mídia** há o cartão **Assistente · IA**. **Segure** o botão do microfone,
fale e solte: o áudio é gravado no Orange Pi, transcrito (voz→texto), enviado a uma IA
que decide **o que fazer** e responde — e a resposta pode ser **falada**.

O que ele sabe fazer (via *function calling*):

| Você diz | O assistente faz |
|---|---|
| “abre o YouTube”, “abre o Spotify” | abre o app cadastrado (ou a página **Apps**) |
| “toca Imagine no Spotify”, “põe um vídeo de jazz” | busca e abre a mídia (Spotify usa a API; YouTube por embed) |
| “pausa”, “toca”, “próxima faixa” | controla o player |
| “traça rota para a avenida Paulista” | vai para **Navegação** e calcula a rota |
| “liga o ar, ventilador 3” | envia o clima ao Arduino (relés) |
| “abre o diagnóstico” | troca de página |
| “como está o carro?”, “qual a autonomia?” | lê o estado real do veículo (ferramenta) |

### Como funciona (tudo local + IA gratuita)

- **Voz→texto**: **whisper.cpp** (`whisper-cli`), 100% offline após baixar o modelo.
- **IA**: qualquer endpoint **OpenAI‑compatível**. O padrão é o **Groq** (chave gratuita
  em `https://console.groq.com/keys`) com `llama-3.3-70b-versatile`. Sem internet, o
  resto do painel continua funcionando normalmente.
- **Fala**: **edge‑tts** (voz `pt-BR-ThalitaMultilingualNeural`), tocada no navegador
  do painel; opcionalmente também no alto‑falante do Orange Pi (`play_local: true`).

### Instalação

```bash
cd /car-dash
./tools/setup_assistant.sh              # instala arecord/ffmpeg, compila whisper.cpp e baixa o modelo
export GROQ_API_KEY="gsk_sua_chave"     # ou cole em Ajustes > Assistente de voz (IA)
arecord -l                              # veja o nome do microfone e ajuste mic_device
sudo systemctl restart cardash         # se usar o serviço
```

O script aceita `--model base|small|medium` (maior = mais preciso e mais pesado) e
`--no-apt`. O microfone é um **USB/P2** comum; sem microfone, o assistente ainda
responde ao que você **digitar** na caixa de texto.

### Ajustes (tela Ajustes)

Liga/desliga o assistente, escolhe microfone e idioma, define a **URL/modelo/chave** da
IA, a voz do TTS, “falar as respostas” e “tocar no Orange Pi”. As chaves ficam no
SQLite (`config.yaml` é o valor inicial).

---

## 13. Wi‑Fi, Bluetooth, telas, mapas nativos e atualizações

### Wi‑Fi e Bluetooth (tela Ajustes)

Os cartões **Wi‑Fi** e **Bluetooth** controlam o sistema do Orange Pi:

- **Wi‑Fi**: liga/desliga o rádio, **Escanear** lista as redes com sinal e cadeado,
  **Conectar** pede a senha (rede aberta conecta direto), **Desconectar** para a rede atual.
- **Bluetooth**: liga/desliga, **Escanear** procura aparelhos por 8 s, **Parear** pareia
  (e conecta), **Conectar/Desconectar** alternam o aparelho ativo.

Requisitos no Orange Pi:

```bash
sudo apt-get install -y network-manager bluez
sudo systemctl enable --now NetworkManager bluetooth
```

Sem essas ferramentas o cartão mostra o que falta (nada quebra). O estado atual aparece
no cabeçalho de cada cartão (rede conectada + IP, ou aparelho ativo).

### Atualizações via GitHub

Na tela **Ajustes → Atualizações do sistema**:

- **Verificar**: faz `git fetch` no repositório configurado e mostra quantos commits há
  à frente, o resumo (`latest`) e a versão atual.
- **Atualizar agora**: quando há novidade, executa `git pull --ff-only`,
  reinstala dependências (`pip install -r requirements.txt`) e **reinicia o painel**.
  Os “alterações locais” são guardados em `git stash` antes do pull.

O servidor também verifica sozinho ao iniciar e a cada `check_hours` horas, avisando no
painel quando há versão nova.

Configuração (`config.yaml`):

```yaml
update:
  enabled: true
  remote: origin
  branch: main
  auto_check: true
  check_hours: 6
  install_deps: true
  restart_command: ""   # ex.: "sudo systemctl restart cardash"
```

> Para repositório **privado**, configure a autenticação do Git no Orange Pi (um token no
> remote: `https://usuario:TOKEN@github.com/usuario/repo.git`) ou use uma chave SSH — o
> botão reaproveita as credenciais do próprio `git`.

### Telas (monitores HDMI)

Com dois monitores ligados (ex.: touch 1024×600 + barra 1920×480), abra **Ajustes → Telas e
monitores (HDMI)**:

- **Detectar** lista as saídas detectadas pelo `xrandr` (nome, resolução, posição, principal).
- Escolha, nos seletores, a saída do **Painel principal** e a da **segunda tela** (barra ou
  painel de velocidade, conforme o kiosk instalado).
- **Organizar sozinho** tenta colocar a segunda tela à direita do painel (`xrandr --right-of`).
- **Aplicar e reiniciar** grava a geometria em `data/screens.env` (lida pelos serviços do
  kiosk) e reinicia os serviços do kiosk instalados (`cardash-kiosk.service` e
  `cardash-kiosk-bar.service` ou `cardash-kiosk-cluster.service`).

Requisitos: ambiente **X11** com `xrandr` (`sudo apt-get install -y x11-xserver-utils`) e o
kiosk instalado (`./install.sh --cluster` ou `--duo`). Sem `xrandr` o cartão apenas informa o
que falta.

### Papel de parede (Mídia)

Na página **Mídia**, o cartão **Papel de parede** troca o fundo da página:

- **Imagem por URL**: cole um endereço `http(s)` e toque em **Usar URL**.
- **Enviar imagem**: escolha um arquivo do aparelho (PNG, JPG, WEBP, GIF ou BMP, até 8 MB) —
  ele é salvo em `data/wallpapers/` e servido em `/media/wallpaper`.
- **Remover** volta ao fundo padrão. A escolha fica salva no SQLite e é restaurada sozinha.

### GNOME Maps (app nativo)

O painel pode **abrir o GNOME Maps instalado no sistema** (app nativo, não é página web).
Na página **Navegação**, o cartão **GNOME Maps (nativo)** mostra se o app está instalado e
traz os botões **Abrir no GNOME Maps** e **Fechar**. Ao abrir, o destino buscado (ou as
coordenadas do GPS) é levado para o app via URI `geo:`/`maps:`.

Instalação (no Orange Pi):

```bash
./tools/install_gnome_maps.sh            # tenta apt, cai para Flatpak se preciso
./tools/install_gnome_maps.sh --flatpak  # força Flatpak (org.gnome.Maps)
```

O lançamento precisa ser habilitado de propósito (por segurança), igual à energia:

```bash
export CARDASH_ALLOW_NATIVE=1
```

O serviço `cardash.service` já traz `CARDASH_ALLOW_NATIVE=1` e `DISPLAY=:0`. Ajustes em
`config.yaml`:

```yaml
native:
  enabled: true          # liga/desliga o lançamento de apps nativos
  display: ":0"          # display X onde o app abre
  maps_app: gnome-maps   # app de mapas nativo
```

Também é possível cadastrar um tile nativo em **Aplicativos → Adicionar app** escolhendo o
tipo **App nativo (GNOME Maps)**. Sem `CARDASH_ALLOW_NATIVE=1` ou com o app não instalado, o
cartão explica o que falta (nada quebra).

> **Observação**: o GNOME Maps abre no **destino/busca**, mas **não aceita uma rota pronta por
> linha de comando** — a navegação (trajeto) é iniciada dentro do próprio app.

---

## 14. Segurança elétrica (leia)

- Alimente o Orange Pi/Arduino por um **conversor DC‑DC 12 V→5 V com fusível** (2–3 A);
  não use o carregador original na tomada 12 V.
- **Nunca** ligue sinais de 12 V direto nos pinos do Arduino — use divisores/optoacopladores.
- Use o positivo **após a chave de ignição** para desligar tudo com o carro.
- Faça todas as conexões com o carro desligado e a bateria desconectada.
- Este projeto lê dados pela porta OBD‑II; **não** altere a ECU. Modificações no
  veículo são de sua responsabilidade — siga as leis locais e não use comandos que
  interfiram na direção, freios ou airbag.
