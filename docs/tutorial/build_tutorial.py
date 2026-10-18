#!/usr/bin/env python3
"""Gera o video tutorial do OpenDash.

Slides com narracao neural (edge-tts), imagens reais da interface e uma cena final
com animacao do sistema rodando em modo simulacao. Musica de fundo sintetizada.

Requer: ffmpeg, ffprobe e edge-tts (voz neural, precisa de internet).
Use: /car-dash/.venv/bin/python docs/tutorial/build_tutorial.py
Saida: opendash-tutorial.mp4 (mesma pasta)
"""
import asyncio
import os
import shutil
import subprocess
import sys

from edge_tts import Communicate

W, H = 1280, 720
FPS = 30
BG = "0x0d1117"
WHITE = "0xf0f6fc"
GREY = "0xc9d1d9"
DIM = "0x8b949e"

VOICE = "pt-BR-ThalitaMultilingualNeural"
RATE = "+0%"
PITCH = "+0Hz"
MUSIC_LEVEL = 0.16

HERE = os.path.dirname(os.path.abspath(__file__))
ASSETS = os.path.join(HERE, "assets")
BUILD = os.path.join(HERE, "build")
FONT_BOLD = "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"
FONT = "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"
OUT = os.path.join(HERE, "opendash-tutorial.mp4")

# tela da UI: 1024x600 centralizada em 1280x720
SCR_W, SCR_H = 1024, 600
SCR_X, SCR_Y = (W - SCR_W) // 2, (H - SCR_H) // 2
BAR_T, BAR_B = 56, 664
ANIM = os.path.join(ASSETS, "ui-anim.mp4")
BOOT = os.path.join(ASSETS, "ui-boot.mp4")

SECTION_COLORS = {
    "INTRODUÇÃO": "0xe82127",
    "VISÃO GERAL": "0x2f81f7",
    "HARDWARE": "0xd29922",
    "MONTAGEM": "0xdb6d28",
    "PLATAFORMA": "0xdb6d28",
    "ARDUINO": "0x1f9e82",
    "INSTALAÇÃO": "0x2f81f7",
    "CONFIGURAÇÃO": "0x8957e5",
    "KIOSK": "0x2ea043",
    "INTERFACE": "0x2ea043",
    "GPS": "0x2f81f7",
    "APPS": "0x8957e5",
    "TELA E ESCALA": "0x2f81f7",
    "CÂMERA DE RÉ": "0x1f9e82",
    "DEMONSTRAÇÃO": "0xe82127",
    "SUPORTE": "0xd29922",
    "FIM": "0xe82127",
}

SCENES = [
    {
        "kicker": "INTRODUÇÃO", "title": "OpenDash",
        "body": ["Painel automotivo estilo Tesla",
                 "para Orange Pi + Arduino"],
        "narration": (
            "Olá! Bem-vindo ao guia de instalação do OpenDash, um painel automotivo "
            "digital que roda no Orange Pi e lê os dados do seu carro com um Arduino. "
            "Neste vídeo vamos ver o que você precisa, como montar, como instalar e como "
            "usar o painel. Vamos começar."),
    },
    {
        "kind": "anim", "clip": BOOT, "kicker": "INTRODUÇÃO",
        "title": "Ligando o sistema",
        "caption": ["A animação de inicialização do OpenDash"],
        "narration": (
            "Ao ligar, o OpenDash mostra a animação de inicialização enquanto verifica "
            "os sensores e conecta ao Arduino. Em poucos segundos o painel está pronto."),
    },
    {
        "kicker": "VISÃO GERAL", "title": "Como funciona",
        "body": ["Arduino lê OBD-II (CAN) e sensores",
                 "Orange Pi roda servidor e interface web",
                 "Os dados atualizam 10 vezes por segundo",
                 "Tela touch mostra o painel em kiosk"],
        "narration": (
            "O sistema tem quatro partes. O Arduino lê o barramento CAN OBD dois, "
            "os sensores analógicos e as entradas digitais, e envia tudo pela porta USB. "
            "O Orange Pi roda o servidor e a interface web, que atualiza dez vezes por segundo. "
            "E a tela touch exibe o painel em tela cheia."),
    },
    {
        "kicker": "HARDWARE", "title": "O que você precisa",
        "body": ["Orange Pi 3, 5 ou Zero 3 com Armbian",
                 "Tela HDMI touch, 1024 por 600",
                 "ESP32",
                 "Módulo MCP2515 para CAN bus",
                 "Conversor 12V para 5V, com fusível"],
        "narration": (
            "Para o hardware você vai precisar de um Orange Pi com Armbian, uma tela HDMI touch, "
            "um ESP32, um módulo MCP vinte e cinco quinze para o CAN bus e um conversor "
            "de doze para cinco volts com fusível. Muito importante: alimente tudo pelo conversor, "
            "com fusível, e nunca ligue direto na tomada do carro."),
    },
    {
        "kicker": "PLATAFORMA", "title": "Raspberry Pi também",
        "body": ["Roda em Orange Pi ou Raspberry Pi",
                 "Armbian, Raspberry Pi OS ou Debian",
                 "Instalação detecta a placa sozinha",
                 "Habilita UART e câmera no boot"],
        "narration": (
            "Uma novidade: além do Orange Pi, o OpenDash também roda na Raspberry Pi. "
            "Na instalação, ele detecta a placa automaticamente, habilita a porta serial e a câmera "
            "no boot e configura tudo do jeito certo, tanto no Armbian quanto no Raspberry Pi OS ou Debian."),
    },
    {
        "kicker": "MONTAGEM", "title": "Ligação do CAN",
        "body": ["MCP2515: CS no 10, SCK no 52",
                 "SI no 51, SO no 50, VCC em 5V",
                 "CAN-H no pino 6 do OBD-II",
                 "CAN-L no pino 14 do OBD-II"],
        "narration": (
            "Vamos à montagem. Esta é a ligação do CAN. O módulo MCP vinte e cinco quinze usa os "
            "pinos de SPI: CS no dez, clock no cinquenta e dois, e dados nos pinos cinquenta e um "
            "e cinquenta. O CAN H vai no pino seis da tomada OBD dois, e o CAN L no pino quatorze. "
            "Alimente o módulo em cinco volts."),
    },
    {
        "kicker": "MONTAGEM", "title": "Sensores e entradas",
        "body": ["Ignição pós-chave no pino D22",
                 "Chaves para GND nos pinos D2 a D9",
                 "Analógicos: A0 óleo, A1 combustível",
                 "A2 temperatura de óleo, A3 bateria",
                 "Bateria via divisor de 30k e 10k"],
        "narration": (
            "Depois vêm os sensores. A ignição, depois da chave, vai no pino vinte e dois. "
            "As chaves de seta, farol, cinto e freio de mão ligam no GND, usando os pinos de dois a nove. "
            "Os sensores analógicos vão nas entradas A zero a A três. E para medir a bateria, "
            "use um divisor de tensão com resistores de trinta e dez quilo ohms."),
    },
    {
        "kicker": "ARDUINO", "title": "Gravar o Arduino",
        "body": ["1. Instale a biblioteca mcp_can",
                 "2. Abra o arquivo car_dash.ino",
                 "3. Selecione a placa ESP32",
                 "4. Grave — sem CAN entra em modo demo"],
        "narration": (
            "Para gravar o Arduino: na IDE, instale a biblioteca mcp_can, abra o arquivo car dash ponto ino, "
            "selecione a placa ESP32 e grave. Se o CAN ainda não estiver conectado, "
            "o firmware entra em modo demonstração, então você pode testar na bancada pelo monitor serial."),
    },
    {
        "kicker": "INSTALAÇÃO", "title": "Requisitos de software",
        "body": ["Armbian ou Debian atualizado",
                 "Python 3 com venv e pip",
                 "Acesso à internet",
                 "Usuário com sudo",
                 "Grupo dialout libera a serial"],
        "narration": (
            "Antes de instalar, confira os requisitos: um Armbian ou Debian atualizado, "
            "Python três com ambiente virtual e pip, acesso à internet e um usuário com sudo. "
            "O acesso à porta serial é liberado pelo grupo dialout, que o instalador configura para você."),
    },
    {
        "kicker": "INSTALAÇÃO", "title": "Instalar no Orange Pi",
        "body": ["git clone ... car-dash",
                 "cd car-dash",
                 "chmod +x install.sh",
                 "sudo ./install.sh",
                 "Opcional: ./install.sh --kiosk"],
        "narration": (
            "No terminal do Orange Pi, copie o projeto com git clone, entre na pasta, "
            "dê permissão de execução ao instalador e rode com sudo. O instalador instala as dependências, "
            "cria o ambiente Python, adiciona você ao grupo dialout e registra o serviço que inicia junto "
            "com o sistema. Se quiser o navegador em tela cheia, use a opção kiosk."),
    },
    {
        "kicker": "INSTALAÇÃO", "title": "Instalação manual",
        "body": ["python3 -m venv .venv",
                 ".venv/bin/pip install -r requirements.txt",
                 ".venv/bin/python run.py",
                 "Serviço: systemctl status cardash",
                 "Após o dialout, faça login novamente"],
        "narration": (
            "Se preferir o passo a passo manual: crie o ambiente virtual, instale as dependências do arquivo "
            "requirements e rode o arquivo run ponto py. Depois disso, o serviço é controlado com systemctl. "
            "Lembre-se: após entrar no grupo dialout, é preciso fazer logout e login de novo para o acesso "
            "à serial funcionar."),
    },
    {
        "kicker": "CONFIGURAÇÃO", "title": "Primeira configuração",
        "body": ["Abra http://IP-do-Pi:8080",
                 "Sem Arduino? Ative Modo simulação",
                 "Ajuste tanque, consumo e odômetro",
                 "Escolha unidades: km/h, Celsius, litros"],
        "narration": (
            "No navegador, abra o endereço do Orange Pi na porta oitenta e oitenta. "
            "Se ainda não tem o Arduino, ative o modo simulação nos ajustes para ver tudo funcionando. "
            "Depois configure a capacidade do tanque, o consumo nominal, o odômetro e as unidades de medida."),
    },
    {
        "kicker": "KIOSK", "title": "Kiosk na tela do carro",
        "body": ["./kiosk/kiosk.sh abre em tela cheia",
                 "Espera o servidor e desliga a tela",
                 "Esconde o cursor automaticamente",
                 "Autostart com install.sh --kiosk"],
        "narration": (
            "Para usar na tela do carro, rode o script do kiosk. Ele espera o servidor ficar pronto, "
            "desliga a proteção de tela, esconde o cursor e abre o navegador em tela cheia. "
            "Se você instalou com a opção kiosk, isso já acontece automaticamente quando o sistema liga."),
    },
    # ---- interface: imagens reais ----
    {
        "kind": "ui", "kicker": "INTERFACE", "title": "Página Drive",
        "image": "page_drive.png",
        "caption": ["Painel principal: velocímetro, marcha, conta-giros e combustível"],
        "narration": (
            "Agora veja como o sistema realmente é. Esta é a página Drive, o painel principal. "
            "No centro, o velocímetro com o arco animado e a marcha. Ao redor ficam o conta-giros, "
            "o nível de combustível, a autonomia, o odômetro e a temperatura. "
            "E nos ícones do topo: setas, farol, cinto e portas abertas."),
    },
    {
        "kind": "ui", "kicker": "INTERFACE", "title": "Página Energia",
        "image": "page_energy.png",
        "caption": ["Combustível, autonomia, consumo médio e gráfico histórico"],
        "narration": (
            "Na página Energia você acompanha o tanque em litros, a autonomia calculada, o consumo "
            "instantâneo e médio, além de um gráfico com as últimas leituras e o resumo das viagens."),
    },
    {
        "kind": "ui", "kicker": "INTERFACE", "title": "Página Mídia",
        "image": "page_media.png",
        "caption": ["Fonte, faixa em reprodução e controle de volume"],
        "narration": (
            "A página Mídia mostra a fonte atual, a faixa em reprodução e o controle de volume, "
            "pronta para integrar com o seu reprodutor de áudio."),
    },
    {
        "kind": "ui", "kicker": "GPS", "title": "Página Navegação",
        "image": "page_nav.png",
        "caption": ["Mapa OpenStreetMap com posição, rastro, rota e busca de destino"],
        "callouts": [
            {"x": 12, "y": 400, "w": 250, "h": 78, "label": "posição e sinal GPS", "color": "0x2f81f7"},
            {"x": 640, "y": 60, "w": 360, "h": 210, "label": "velocidade, rumo e satélites", "color": "0x2f81f7"},
            {"x": 640, "y": 318, "w": 360, "h": 150, "label": "busca e rota", "color": "0x2f81f7"},
        ],
        "narration": (
            "Esta é a página Navegação. O mapa usa OpenStreetMap, com a posição do carro em tempo real, "
            "o rastro percorrido e o rumo. Na lateral você vê a velocidade do GPS, os satélites e a altitude. "
            "Você também pode buscar um endereço e traçar a rota até o destino. "
            "O GPS pode vir do Arduino ou de um módulo USB ligado ao Orange Pi."),
    },
    {
        "kind": "ui", "kicker": "APPS", "title": "Lançador de aplicativos",
        "image": "page_apps.png",
        "caption": ["YouTube, Spotube, Mapas e Navegador — e você cadastra os seus"],
        "callouts": [
            {"x": 846, "y": 58, "w": 170, "h": 42, "label": "cadastre seu app", "color": "0x8957e5"},
            {"x": 16, "y": 105, "w": 828, "h": 156, "label": "aplicativos", "color": "0x8957e5"},
        ],
        "narration": (
            "Na página Apps fica o lançador de aplicativos. YouTube e Spotube são aplicativos "
            "nativos do sistema; Mapas e o Navegador são páginas incorporadas. Você cadastra "
            "qualquer outro serviço pelo botão Adicionar app. "
            "Ao tocar em um app, ele abre em tela cheia, com botão para recarregar e abrir em outra aba."),
    },
    {
        "kind": "ui", "kicker": "INTERFACE", "title": "Página Clima",
        "image": "page_climate.png",
        "caption": ["Ventilador e ar-condicionado acionam relés reais"],
        "narration": (
            "Na página Clima, os comandos de ventilador e ar-condicionado não são só visuais: "
            "ao tocar, eles acionam os relés ligados ao Arduino."),
    },
    {
        "kind": "ui", "kicker": "INTERFACE", "title": "Página Diagnóstico",
        "image": "page_diag.png",
        "caption": ["Leitura e limpeza de códigos DTC e sensores ao vivo"],
        "narration": (
            "A página Diagnóstico lê e apaga códigos de falha, mostra a descrição em português "
            "e exibe os sensores ao vivo, em tempo real."),
    },
    {
        "kind": "ui", "kicker": "INTERFACE", "title": "Página Ajustes",
        "image": "page_settings.png",
        "caption": ["Unidades, tema, brilho, modo simulação e porta serial"],
        "narration": (
            "E em Ajustes você define as unidades, o tema claro ou escuro, o brilho da tela, "
            "o modo simulação e a porta serial do Arduino."),
    },
    {
        "kind": "ui", "kicker": "TELA E ESCALA", "title": "Qualquer tela",
        "image": "page_settings_display.png",
        "caption": ["Detecta a resolução e ajusta a escala da interface sozinho"],
        "callouts": [
            {"x": 512, "y": 128, "w": 500, "h": 382, "label": "escala e resolução", "color": "0x2f81f7"},
        ],
        "narration": (
            "E o OpenDash se adapta a qualquer tela. Em Ajustes, o cartão Tela e escala detecta a "
            "resolução do monitor e calcula a escala ideal da interface automaticamente. "
            "Você pode informar as polegadas da tela, a orientação e, se quiser, ajustar a escala na mão. "
            "Assim o painel fica do tamanho certo em telas pequenas ou grandes."),
    },
    {
        "kind": "ui", "kicker": "CÂMERA DE RÉ", "title": "Câmera de ré",
        "image": "page_reverse.png",
        "caption": ["Ao engatar a ré, a câmera aparece em tela cheia com linhas guia"],
        "callouts": [
            {"x": 110, "y": 215, "w": 380, "h": 120, "label": "linhas guia", "color": "0x1f9e82"},
            {"x": 545, "y": 215, "w": 380, "h": 120, "label": "câmera ao vivo", "color": "0x1f9bd1"},
        ],
        "narration": (
            "Outra novidade é a câmera de ré. Quando você engata a marcha à ré, o OpenDash mostra a "
            "câmera em tela cheia, com linhas guia para ajudar na manobra. "
            "Como o Arduino informa a marcha, a troca é automática. "
            "Nas configurações você escolhe o disparo, o dispositivo e o tamanho da imagem."),
    },
    # ---- animacao final ----
    {
        "kind": "anim", "kicker": "DEMONSTRAÇÃO", "title": "OpenDash ao vivo",
        "caption": ["O sistema rodando em modo simulação, em tempo real"],
        "narration": (
            "E aqui está o OpenDash rodando em modo simulação. Repare no velocímetro e no conta-giros "
            "se movendo em tempo real, no gráfico se atualizando e na troca de páginas pelo toque. "
            "É exatamente assim que fica na tela do seu carro."),
    },
    {
        "kicker": "SUPORTE", "title": "Verificação rápida",
        "body": ["Sem sinal: cabo, porta, dialout",
                 "OBD zerado: CAN-H, CAN-L, cristal, 120Ω",
                 "Tela branca: curl localhost:8080/health",
                 "Sensores: calibre no arquivo config.h"],
        "narration": (
            "Para resolver problemas: se aparecer sem sinal, verifique o cabo, a porta serial e o grupo dialout. "
            "Se o OBD ficar zerado, confira o CAN H e o CAN L, o cristal do módulo e a terminação de "
            "cento e vinte ohms. Se a tela ficar branca, teste o endereço de saúde do servidor com curl. "
            "E se algum sensor estiver errado, calibre os valores no arquivo config ponto h."),
    },
    {
        "kicker": "SUPORTE", "title": "Serviço e manutenção",
        "body": ["systemctl status cardash",
                 "journalctl -u cardash -f",
                 "Dados ficam em data/cardash.db",
                 "Backup: basta copiar o arquivo .db"],
        "narration": (
            "No dia a dia, use systemctl para ver o status do serviço e journalctl para acompanhar os logs "
            "em tempo real. Todos os dados, como ajustes, viagens e códigos de falha, ficam no arquivo "
            "cardash ponto db. Para fazer backup, é só copiar esse arquivo."),
    },
    {
        "kicker": "FIM", "title": "Pronto!",
        "body": ["Painel instalado e funcionando",
                 "Documentação completa no README",
                 "Bom passeio!"],
        "narration": (
            "E pronto! O painel está instalado e funcionando. A documentação completa está no arquivo README "
            "do projeto. Obrigado por assistir e bom passeio!"),
    },
]


def run(cmd):
    r = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
    if r.returncode != 0:
        sys.stderr.write(r.stdout.decode("utf-8", "ignore"))
        raise SystemExit(f"falhou: {' '.join(cmd)}")


def write(path, text):
    with open(path, "w", encoding="utf-8") as fh:
        fh.write(text)


def duration(path):
    r = subprocess.run(
        ["ffprobe", "-v", "error", "-show_entries", "format=duration",
         "-of", "default=nw=1:nk=1", path],
        stdout=subprocess.PIPE, stderr=subprocess.DEVNULL)
    return float(r.stdout.decode().strip())


def textfile(idx, tag, text):
    path = os.path.join(BUILD, f"txt_{idx}_{tag}.txt")
    write(path, text)
    return path


def bars(idx, total, scene, color):
    """Filtros das faixas superior/inferior (título, kicker, legenda, índice)."""
    title = textfile(idx, "title", scene["title"])
    kicker = textfile(idx, "kicker", scene["kicker"])
    cap = textfile(idx, "cap", "\n".join(scene.get("caption", [])))
    return [
        f"drawbox=x=0:y=0:w={W}:h={BAR_T}:color={BG}@0.78:t=fill",
        f"drawbox=x=0:y={BAR_T - 4}:w={W}:h=4:color={color}:t=fill",
        f"drawbox=x=0:y={BAR_B}:w={W}:h={H - BAR_B}:color={BG}@0.82:t=fill",
        f"drawbox=x=0:y={BAR_B}:w={W}:h=4:color={color}:t=fill",
        f"drawtext=fontfile={FONT_BOLD}:textfile={title}:fontcolor={WHITE}:"
        f"fontsize=34:x=48:y=12",
        f"drawtext=fontfile={FONT_BOLD}:textfile={kicker}:fontcolor=white:"
        f"fontsize=18:x=w-tw-48:y=16:box=1:boxcolor={color}:boxborderw=10",
        f"drawtext=fontfile={FONT}:textfile={cap}:fontcolor={GREY}:"
        f"fontsize=22:x=48:y={BAR_B + 10}:line_spacing=4",
        f"drawtext=fontfile={FONT}:text='{idx} / {total}':fontcolor={DIM}:"
        f"fontsize=20:x=w-tw-48:y={BAR_B + 12}",
    ]


def make_slide(idx, total, scene):
    color = SECTION_COLORS.get(scene["kicker"], "0xe82127")
    title_file = textfile(idx, "title", scene["title"])
    colorfor = color
    lines = scene["body"]
    n = len(lines)
    line_h = 54
    body_y = 325 if n <= 3 else (300 if n <= 4 else 275)
    parts = [
        f"drawbox=x=0:y=0:w={W}:h=8:color={colorfor}:t=fill",
        f"drawbox=x=0:y={H-8}:w={W}:h=8:color={colorfor}:t=fill",
        f"drawbox=x=60:y=150:w=90:h=6:color={colorfor}:t=fill",
        f"drawtext=fontfile={FONT_BOLD}:text=OpenDash:fontcolor={colorfor}:fontsize=26:x=60:y=44",
        f"drawtext=fontfile={FONT}:text=guia de instalação:fontcolor={DIM}:fontsize=20:x=214:y=50",
        f"drawtext=fontfile={FONT_BOLD}:text='{scene['kicker']}':fontcolor=white:"
        f"fontsize=20:x=w-tw-60:y=44:box=1:boxcolor={colorfor}:boxborderw=14",
        f"drawtext=fontfile={FONT_BOLD}:textfile={title_file}:fontcolor={WHITE}:fontsize=58:x=60:y=180",
        f"drawtext=fontfile={FONT}:text='{idx} / {total}':fontcolor={DIM}:fontsize=22:x=w-tw-60:y={H-60}",
    ]
    for i, line in enumerate(lines):
        lf = textfile(idx, f"line{i}", line)
        y = body_y + i * line_h
        parts.append(f"drawbox=x=64:y={y + 9}:w=14:h=14:color={colorfor}:t=fill")
        parts.append(f"drawtext=fontfile={FONT}:textfile={lf}:fontcolor={GREY}:fontsize=30:x=96:y={y}")
    png = os.path.join(BUILD, f"slide_{idx}.png")
    run(["ffmpeg", "-y", "-f", "lavfi", "-i", f"color=c={BG}:s={W}x{H}",
         "-vf", ",".join(parts), "-frames:v", "1", png])
    return png


def make_ui_frame(idx, total, scene):
    color = SECTION_COLORS.get(scene["kicker"], "0xe82127")
    img = os.path.join(ASSETS, scene["image"])
    parts = [
        f"pad={W}:{H}:{SCR_X}:{SCR_Y}:color={BG}",
        f"drawbox=x={SCR_X - 1}:y={SCR_Y - 1}:w={SCR_W + 2}:h={SCR_H + 2}:"
        f"color=0x30363d:t=2",
    ]
    for j, c in enumerate(scene.get("callouts", [])):
        cx, cy = SCR_X + c["x"], SCR_Y + c["y"]
        cc = c.get("color", color)
        parts.append(f"drawbox=x={cx}:y={cy}:w={c['w']}:h={c['h']}:color={cc}@0.95:t=3")
        if c.get("label"):
            lf = textfile(idx, f"co{j}", c["label"])
            parts.append(
                f"drawtext=fontfile={FONT_BOLD}:textfile={lf}:fontcolor=white:fontsize=22:"
                f"x={cx}:y={cy - 34}:box=1:boxcolor={cc}@0.95:boxborderw=9")
    parts += bars(idx, total, scene, color)
    png = os.path.join(BUILD, f"slide_{idx}.png")
    run(["ffmpeg", "-y", "-i", img,
         "-vf", ",".join(parts), "-frames:v", "1", png])
    return png


def make_voice(idx, scene):
    mp3 = os.path.join(BUILD, f"voice_{idx}.mp3")
    wav = os.path.join(BUILD, f"voice_{idx}.wav")

    async def synth():
        await Communicate(scene["narration"], VOICE, rate=RATE, pitch=PITCH).save(mp3)

    asyncio.run(synth())
    run(["ffmpeg", "-y", "-i", mp3, "-ar", "44100", "-ac", "2", wav])
    return wav


def make_segment_still(idx, png, wav):
    seg = os.path.join(BUILD, f"seg_{idx}.mp4")
    dur = duration(wav) + 1.1
    run(["ffmpeg", "-y", "-loop", "1", "-framerate", str(FPS), "-i", png,
         "-i", wav, "-t", f"{dur:.3f}",
         "-vf", "fade=t=in:st=0:d=0.4,format=yuv420p", "-af", "apad",
         "-c:v", "libx264", "-preset", "veryfast", "-r", str(FPS),
         "-c:a", "aac", "-b:a", "128k", "-ar", "44100", "-ac", "2",
         "-shortest", seg])
    return seg


def make_segment_anim(idx, total, scene, wav):
    seg = os.path.join(BUILD, f"seg_{idx}.mp4")
    dur = duration(wav) + 1.1
    color = SECTION_COLORS.get(scene["kicker"], "0xe82127")
    overlays = bars(idx, total, scene, color)
    brand = textfile(idx, "brand", "OpenDash")
    overlays.append(
        f"drawtext=fontfile={FONT_BOLD}:textfile={brand}:fontcolor={color}:"
        f"fontsize=30:x={SCR_X + 16}:y={SCR_Y + 12}:"
        "box=1:boxcolor=0x0d1117@0.55:boxborderw=10")
    vf = (f"[0:v]pad={W}:{H}:{SCR_X}:{SCR_Y}:color={BG},fps={FPS}[bg];"
          f"[bg]" + ",".join(overlays) + "[v]")
    clip = scene.get("clip", ANIM)
    run(["ffmpeg", "-y", "-stream_loop", "-1", "-i", clip, "-i", wav,
         "-filter_complex", vf, "-map", "[v]", "-map", "1:a",
         "-t", f"{dur:.3f}",
         "-c:v", "libx264", "-preset", "veryfast", "-pix_fmt", "yuv420p",
         "-r", str(FPS), "-c:a", "aac", "-b:a", "128k", "-ar", "44100",
         "-ac", "2", "-shortest", seg])
    return seg


def make_music(total):
    music = os.path.join(BUILD, "music.wav")
    fade_out = max(0.0, total - 5)
    run(["ffmpeg", "-y",
         "-f", "lavfi", "-i", f"sine=f=110:d={total:.2f}",
         "-f", "lavfi", "-i", f"sine=f=164.8:d={total:.2f}",
         "-f", "lavfi", "-i", f"sine=f=220:d={total:.2f}",
         "-f", "lavfi", "-i", f"sine=f=277.2:d={total:.2f}",
         "-filter_complex",
         "[0][1][2][3]amix=inputs=4:normalize=1,"
         "lowpass=f=650,tremolo=f=0.15:d=0.35,volume=0.32,"
         f"afade=t=in:st=0:d=3,afade=t=out:st={fade_out:.2f}:d=5",
         "-ar", "44100", "-ac", "2", music])
    return music


def main():
    if os.path.isdir(BUILD):
        shutil.rmtree(BUILD)
    os.makedirs(BUILD, exist_ok=True)
    total = len(SCENES)
    segments = []
    for i, scene in enumerate(SCENES, 1):
        kind = scene.get("kind", "slide")
        print(f"[{i}/{total}] {scene['kicker']} - {scene['title']} ({kind})")
        wav = make_voice(i, scene)
        if kind == "ui":
            png = make_ui_frame(i, total, scene)
            seg = make_segment_still(i, png, wav)
        elif kind == "anim":
            seg = make_segment_anim(i, total, scene, wav)
        else:
            png = make_slide(i, total, scene)
            seg = make_segment_still(i, png, wav)
        segments.append(seg)

    listfile = os.path.join(BUILD, "list.txt")
    write(listfile, "".join(f"file '{s}'\n" for s in segments))
    narration = os.path.join(BUILD, "narration.mp4")
    run(["ffmpeg", "-y", "-f", "concat", "-safe", "0", "-i", listfile,
         "-c", "copy", narration])

    print("[mix] gerando musica de fundo e mixando")
    total_dur = duration(narration)
    music = make_music(total_dur)
    run(["ffmpeg", "-y", "-i", narration, "-i", music,
         "-filter_complex",
         f"[1:a]volume={MUSIC_LEVEL}[m];"
         "[0:a][m]amix=inputs=2:duration=first:normalize=0,"
         "loudnorm=I=-16:TP=-1.5:LRA=11[a]",
         "-map", "0:v", "-map", "[a]",
         "-c:v", "copy", "-c:a", "aac", "-b:a", "160k",
         "-movflags", "+faststart", OUT])

    d = duration(OUT)
    size = os.path.getsize(OUT) / 1e6
    print(f"\nOK -> {OUT}")
    print(f"duracao: {int(d // 60)}m{int(d % 60):02d}s  |  tamanho: {size:.1f} MB  "
          f"|  cenas: {total}")


if __name__ == "__main__":
    main()
