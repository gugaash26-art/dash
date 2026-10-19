#!/usr/bin/env python3
"""Gera o VIDEO-TUTORIAL passo a passo de INSTALACAO do OpenDash.

Cobre a instalacao completa em Debian 12 ou Armbian numa Orange Pi Zero 3:
preparar o cartao SD, primeiro boot, SSH, atualizar o sistema, instalar o
OpenDash, testar no navegador, kiosk em tela cheia e os extras (ESP32, GPS,
assistente de voz e GNOME Maps nativo). Mostra os comandos num painel de
terminal, com a mesma narracao neural e o mesmo avatar dos outros tutoriais.

Requer: ffmpeg, ffprobe e edge-tts (precisa de internet).
Antes, garanta o avatar (uma vez):
  python3 docs/tutorial/capture_avatar.py
Depois:
  /car-dash/.venv/bin/python docs/tutorial/build_tutorial_install.py
Saida: opendash-tutorial-instalacao.mp4 (mesma pasta)

Atalhos uteis:
  TUT_ONLY=2 python3 ...      # gera so as 2 primeiras cenas (teste rapido)
"""
import asyncio
import os
import subprocess
import sys
import time

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
BUILD = os.path.join(HERE, "build_install")
FONT_BOLD = "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"
FONT = "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"
FONT_MONO = "/usr/share/fonts/truetype/dejavu/DejaVuSansMono.ttf"
FONT_MONO_BOLD = "/usr/share/fonts/truetype/dejavu/DejaVuSansMono-Bold.ttf"
OUT = os.path.join(HERE, "opendash-tutorial-instalacao.mp4")

# avatar
AV_IDLE = os.path.join(ASSETS, "avatar_idle.png")
AV_TALK = os.path.join(ASSETS, "avatar_talk.png")
AV_BLINK = os.path.join(ASSETS, "avatar_blink.png")
AV_WAVE = os.path.join(ASSETS, "avatar_wave.png")
PIP_H = 360
PIP_X = W - 328
PIP_Y = H - PIP_H

# tela da UI: 1024x600 centralizada em 1280x720
SCR_W, SCR_H = 1024, 600
SCR_X, SCR_Y = (W - SCR_W) // 2, (H - SCR_H) // 2
BAR_T, BAR_B = 56, 664
ANIM = os.path.join(ASSETS, "ui-anim.mp4")

SECTION_COLORS = {
    "ABERTURA": "0xe82127",
    "AGENDA": "0x2f81f7",
    "PREPARO": "0xd29922",
    "INSTALAÇÃO": "0x2ea043",
    "TESTE": "0x2f81f7",
    "KIOSK": "0x8957e5",
    "EXTRAS": "0xd29922",
    "PLATAFORMA": "0xdb6d28",
    "DICAS": "0xe82127",
    "DEMONSTRAÇÃO": "0x2ea043",
    "ENCERRAMENTO": "0xe82127",
}

SCENES = [
    # ---------------------------------------------------------------- abertura
    {
        "kind": "presenter", "avatar": "wave", "kicker": "ABERTURA",
        "title": "Instalar o OpenDash",
        "sub": "Debian 12 · Armbian · Orange Pi ou Raspberry Pi",
        "body": ["Do zero ao painel funcionando",
                 "todos os comandos, passo a passo"],
        "narration": (
            "Olá! Neste vídeo eu vou te mostrar, do zero, como instalar o OpenDash numa Orange Pi "
            "Zero 3 com Debian ou Armbian. A gente vai preparar o cartão de memória, ligar a "
            "placa, instalar o sistema com todos os comandos e deixar o painel rodando em tela "
            "cheia. Vamos passo a passo."),
    },
    {
        "kicker": "AGENDA", "title": "O roteiro",
        "body": ["Preparar o cartão SD e a placa",
                 "Instalar o OpenDash (comandos)",
                 "Testar no navegador",
                 "Kiosk em tela cheia",
                 "Extras: ESP32, GPS, voz e mapas"],
        "narration": (
            "O caminho é este: primeiro preparamos o cartão de memória e o sistema; depois "
            "instalamos o OpenDash com os comandos, um por um; em seguida testamos no navegador e "
            "deixamos em tela cheia. No fim, os extras: ESP32, GPS, assistente de voz e o "
            "GNOME Maps."),
    },
    {
        "kicker": "PREPARO", "title": "O que você precisa",
        "body": ["Orange Pi Zero 3 (1.5 GB de RAM ou mais)",
                 "Cartão microSD de 16 GB ou maior",
                 "Fonte USB-C 5 V / 3 A",
                 "Rede (cabo ou Wi-Fi) e um computador",
                 "Imagem Debian 12 ou Armbian"],
        "narration": (
            "Você vai precisar da Orange Pi Zero 3, de preferência com um vírgula cinco giga ou "
            "mais de memória; de um cartão micro SD de dezesseis giga ou maior; de uma fonte USB C "
            "de cinco volts e três amperes; da placa conectada à rede; e de um computador para "
            "gravar o cartão."),
    },
    # ------------------------------------------------------- PASSO 1
    {
        "kind": "term", "kicker": "PREPARO", "title": "1. Baixar a imagem",
        "term_title": "PC — baixar a imagem",
        "caption": ["Passo 1 de 12 · Debian 12 ou Armbian"],
        "lines": [
            "# Debian 12 (Bookworm) para Orange Pi Zero 3",
            "# baixe em orangepi.org > Download",
            "# ou Armbian (armbian.com/orange-pi-zero-3)",
            "xz -d orangepi-zero3_bookworm.img.xz",
        ],
        "narration": (
            "Passo um: baixar a imagem do sistema. No site da Orange Pi, baixe o Debian doze para "
            "a Zero 3. Se preferir o Armbian, baixe no site do Armbian. Os arquivos vêm "
            "comprimidos, então descompacte com o comando xz, como mostra a tela."),
    },
    # ------------------------------------------------------- PASSO 2
    {
        "kind": "term", "kicker": "PREPARO", "title": "2. Gravar no cartão SD",
        "term_title": "PC — gravar o cartão",
        "caption": ["Passo 2 de 12 · atenção ao nome do dispositivo"],
        "lines": [
            "lsblk            # descubra o cartão SD",
            "sudo dd if=orangepi-zero3_bookworm.img \\",
            "        of=/dev/sdX bs=4M status=progress",
            "sync",
            "# ou use o Balena Etcher (gráfico)",
        ],
        "narration": (
            "Passo dois: gravar a imagem no cartão. Use o comando lsblk para descobrir qual é o "
            "cartão de memória — muito cuidado para não errar o disco. Depois use o dd, trocando o "
            "sdX pelo seu cartão. Se preferir, use o Balena Etcher, que é gráfico e mais seguro."),
    },
    # ------------------------------------------------------- PASSO 3
    {
        "kind": "term", "kicker": "PREPARO", "title": "3. Primeiro boot e SSH",
        "term_title": "orange pi zero 3 — ssh",
        "caption": ["Passo 3 de 12 · conhecer o IP da placa"],
        "lines": [
            "# insira o microSD, ligue e aguarde ~1 min",
            "ip a             # descubra o IP da placa",
            "ssh orangepi@192.168.1.50",
            "# senha padrão: orangepi (Debian)",
            "# Armbian define usuário/senha no 1º boot",
        ],
        "narration": (
            "Passo três: o primeiro boot. Insira o cartão, ligue a placa e espere um minuto. "
            "Descubra o endereço IP e conecte por SSH. No Debian da Orange Pi, o usuário e a senha "
            "padrão são orangepi. No Armbian, você define usuário e senha no primeiro boot."),
    },
    # ------------------------------------------------------- PASSO 4
    {
        "kind": "term", "kicker": "INSTALAÇÃO", "title": "4. Atualizar o sistema",
        "term_title": "orange pi zero 3 — terminal",
        "caption": ["Passo 4 de 12 · manter o sistema em dia"],
        "lines": [
            "sudo apt update",
            "sudo apt full-upgrade -y",
            "sudo reboot",
        ],
        "narration": (
            "Passo quatro: atualizar o sistema. Rode o apt update, depois o full upgrade para "
            "baixar as atualizações e, em seguida, reinicie. Isso garante uma base limpa antes de "
            "instalar o painel."),
    },
    # ------------------------------------------------------- PASSO 5
    {
        "kind": "term", "kicker": "INSTALAÇÃO", "title": "5. Instalar a base",
        "term_title": "orange pi zero 3 — terminal",
        "caption": ["Passo 5 de 12 · git e Python"],
        "lines": [
            "sudo apt install -y git python3-venv \\",
            "    python3-pip curl",
        ],
        "narration": (
            "Passo cinco: instalar o que o OpenDash precisa. É só o git, o Python com o venv e o "
            "pacote pip. Um único comando e está pronto."),
    },
    # ------------------------------------------------------- PASSO 6
    {
        "kind": "term", "kicker": "INSTALAÇÃO", "title": "6. Baixar o OpenDash",
        "term_title": "orange pi zero 3 — terminal",
        "caption": ["Passo 6 de 12 · baixar pelo git"],
        "lines": [
            "git clone https://github.com/SEU_USUARIO/dash.git",
            "cd dash",
            "# repositório privado? use token ou chave SSH",
        ],
        "narration": (
            "Passo seis: baixar o OpenDash. Use o git clone com o endereço do repositório e entre "
            "na pasta. Se o seu repositório for privado, use um token no endereço ou configure uma "
            "chave SSH."),
    },
    # ------------------------------------------------------- PASSO 7
    {
        "kind": "term", "kicker": "INSTALAÇÃO", "title": "7. Instalar",
        "term_title": "orange pi zero 3 — terminal",
        "caption": ["Passo 7 de 12 · o instalador faz tudo"],
        "lines": [
            "./install.sh",
            "# cria o ambiente Python (.venv)",
            "# instala dependências e o serviço cardash",
        ],
        "narration": (
            "Passo sete: rodar o instalador. Um único script, o install ponto sh, já cria o "
            "ambiente Python, instala as dependências, registra o serviço do painel e coloca o seu "
            "usuário no grupo certo para acessar a porta serial."),
    },
    {
        "kicker": "INSTALAÇÃO", "title": "O que o install.sh faz",
        "body": ["Cria o ambiente Python (.venv)",
                 "Instala pyserial e PyYAML",
                 "Instala o navegador Chromium",
                 "Registra e habilita o serviço cardash",
                 "Adiciona você ao grupo dialout"],
        "narration": (
            "Só para você entender o que aconteceu: o instalador criou o ambiente Python, instalou "
            "as bibliotecas pyserial e PyYAML, baixou o navegador Chromium para o modo tela cheia, "
            "registrou o serviço cardash para iniciar junto com o sistema e te adicionou ao grupo "
            "dialout, que dá acesso à porta serial."),
    },
    # ------------------------------------------------------- PASSO 8
    {
        "kind": "term", "kicker": "TESTE", "title": "8. Testar no navegador",
        "term_title": "orange pi zero 3 — terminal",
        "caption": ["Passo 8 de 12 · abra no PC e ligue a simulação"],
        "lines": [
            "./.venv/bin/python run.py",
            "# no computador, abra no navegador:",
            "#   http://IP_DA_PLACA:8080",
        ],
        "narration": (
            "Passo oito: testar. Inicie o servidor com o run ponto pi e, no computador, abra o "
            "navegador no endereço da placa na porta oito mil e oitenta. Na tela de Ajustes, ligue "
            "o Modo Simulação para ver o painel funcionando sem o carro."),
    },
    {
        "kind": "ui", "kicker": "TESTE", "title": "Resultado: o painel",
        "image": "page_drive.png",
        "caption": ["Página Painel: velocímetro, conta-giros e indicadores"],
        "narration": (
            "E este é o resultado. A página Painel mostra o velocímetro, a marcha, o conta-giros "
            "em barra, o nível de combustível e os indicadores de seta, farol e cinto. Tudo "
            "atualizando em tempo real."),
    },
    # ------------------------------------------------------- PASSO 9
    {
        "kind": "term", "kicker": "KIOSK", "title": "9. Kiosk em tela cheia",
        "term_title": "orange pi zero 3 — terminal",
        "caption": ["Passo 9 de 12 · navegador automático no boot"],
        "lines": [
            "sudo apt install -y chromium \\",
            "    x11-xserver-utils",
            "./install.sh --kiosk",
            "./kiosk/kiosk.sh",
        ],
        "narration": (
            "Passo nove, opcional mas recomendado: o modo quiosque, em tela cheia. Instale o "
            "Chromium e o pacote de utilitários do X, rode o instalador com a opção kiosk e o "
            "sistema abre o painel sozinho, em tela cheia, toda vez que liga."),
    },
    # ------------------------------------------------------- PASSO 10
    {
        "kind": "term", "kicker": "EXTRAS", "title": "10. ESP32 e GPS (opcional)",
        "term_title": "orange pi zero 3 — terminal",
        "caption": ["Passo 10 de 12 · dados reais do carro"],
        "lines": [
            "ls /dev/ttyUSB* /dev/ttyACM*",
            "sudo usermod -aG dialout $USER",
            "# grave arduino/car_dash/car_dash.ino",
            "# GPS USB é detectado sozinho",
        ],
        "narration": (
            "Passo dez, opcional: ligar o ESP32 e o GPS. Conecte o ESP32 pela USB, grave o "
            "sketch que está na pasta arduino, e confira se a porta apareceu. O GPS por USB é "
            "detectado automaticamente. Se você não tem o hardware, o Modo Simulação já cobre os "
            "testes."),
    },
    # ------------------------------------------------------- PASSO 11
    {
        "kind": "term", "kicker": "EXTRAS", "title": "11. Assistente de voz (opcional)",
        "term_title": "orange pi zero 3 — terminal",
        "caption": ["Passo 11 de 12 · grátis e de código aberto"],
        "lines": [
            "./tools/setup_assistant.sh",
            "export GROQ_API_KEY=\"gsk_...\"",
            "# chave grátis em console.groq.com",
        ],
        "narration": (
            "Passo onze, opcional: o assistente de voz. Rode o script setup assistant, que instala "
            "o reconhecimento de fala e a voz. Depois, pegue uma chave gratuita no site da Groq e "
            "exporte a variável, ou cole a chave nos Ajustes do painel."),
    },
    # ------------------------------------------------------- PASSO 12
    {
        "kind": "term", "kicker": "EXTRAS", "title": "12. GNOME Maps nativo (opcional)",
        "term_title": "orange pi zero 3 — terminal",
        "caption": ["Passo 12 de 12 · mapas do sistema no painel"],
        "lines": [
            "./tools/install_gnome_maps.sh",
            "export CARDASH_ALLOW_NATIVE=1",
            "# abra o destino/busca no GNOME Maps",
        ],
        "narration": (
            "Passo doze, para terminar: o GNOME Maps nativo. O script install gnome maps instala o "
            "aplicativo de mapas do sistema e habilita o lançamento no painel. Assim, a página "
            "Navegação abre o destino direto no GNOME Maps."),
    },
    {
        "kicker": "DICAS", "title": "Dicas para 1.5 GB de RAM",
        "body": ["Use zram/swap: sudo apt install zram-tools",
                 "Chromium pesado? acrescente --disable-gpu",
                 "Rode só o kiosk, sem desktop completo",
                 "Zero 3 tem 1 HDMI — sem duas telas",
                 "Sem microfone: use fone/mic USB"],
        "narration": (
            "Algumas dicas para a versão de um vírgula cinco giga de memória. Ative o zram como "
            "memória de troca; se o Chromium travar, acrescente a opção disable gpu; rode somente o "
            "quiosque, sem um desktop completo. Lembre que a Zero 3 tem apenas uma saída HDMI, "
            "então não dá para usar duas telas; e como ela não tem microfone, use um fone ou "
            "microfone USB para o assistente."),
    },
    # -------------------------------------------------- extra: plataforma/recursos
    {
        "kicker": "PLATAFORMA", "title": "Raspberry Pi também",
        "body": ["Roda em Orange Pi ou Raspberry Pi",
                 "Armbian, Raspberry Pi OS ou Debian",
                 "A instalação detecta a placa sozinha",
                 "Habilita UART e câmera no boot"],
        "narration": (
            "Antes de fechar, uma novidade: além do Orange Pi, o OpenDash também roda na Raspberry Pi. "
            "A instalação detecta a placa automaticamente, habilita a porta serial e a câmera no boot "
            "e configura tudo tanto no Armbian quanto no Raspberry Pi OS ou Debian. "
            "Se quiser, dá para pular esse ajuste com a opção no r p i."),
    },
    {
        "kind": "term", "kicker": "EXTRAS", "title": "Extra · câmera, escala e placa",
        "term_title": "orange pi zero 3 — terminal",
        "caption": ["Extras · uma linha de comando para cada recurso"],
        "lines": [
            "./install.sh --camera",
            "./install.sh --screen=1280x720",
            "# Raspberry Pi: ./install.sh  (detecta a placa)",
            "# pule os ajustes de RPi: --no-rpi",
        ],
        "narration": (
            "Três recursos novos em uma linha de comando. Para a câmera de ré, rode install ponto sh "
            "com a opção camera, que instala o que falta e configura o dispositivo. Para fixar uma "
            "resolução, use a opção screen. E, na Raspberry Pi, é só rodar install ponto sh que a "
            "placa é detectada sozinha; com a opção no r p i você pula esses ajustes."),
    },
    # ---------------------------------------------------------- demonstração
    {
        "kind": "anim", "kicker": "DEMONSTRAÇÃO", "title": "OpenDash ao vivo",
        "clip": ANIM,
        "caption": ["O sistema rodando, em modo simulação"],
        "narration": (
            "E aqui está o OpenDash rodando ao vivo no modo simulação. Repare no velocímetro e no "
            "conta-giros se movendo e na troca de páginas pelo toque. É exatamente assim que fica na "
            "tela do seu carro."),
    },
    # ------------------------------------------------------------- encerramento
    {
        "kind": "presenter", "avatar": "wave", "kicker": "ENCERRAMENTO",
        "title": "Pronto!",
        "sub": "seu painel rodando no Orange Pi",
        "body": ["Documentação completa no README",
                 "Dúvidas: abra uma issue no repositório",
                 "Bom passeio!"],
        "narration": (
            "E pronto! Com esses passos o OpenDash está rodando na sua Orange Pi ou Raspberry Pi, com "
            "Debian, Armbian ou Raspberry Pi OS. Tudo está documentado no README do projeto. "
            "Obrigado por assistir e bom passeio!"),
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
    ]


def make_slide(idx, total, scene):
    color = SECTION_COLORS.get(scene["kicker"], "0xe82127")
    title_file = textfile(idx, "title", scene["title"])
    lines = scene["body"]
    n = len(lines)
    line_h = 54
    body_y = 325 if n <= 3 else (300 if n <= 4 else 275)
    parts = [
        f"drawbox=x=0:y=0:w={W}:h=8:color={color}:t=fill",
        f"drawbox=x=0:y={H-8}:w={W}:h=8:color={color}:t=fill",
        f"drawbox=x=60:y=150:w=90:h=6:color={color}:t=fill",
        f"drawtext=fontfile={FONT_BOLD}:text=OpenDash:fontcolor={color}:fontsize=26:x=60:y=44",
        f"drawtext=fontfile={FONT}:text=instalação passo a passo:fontcolor={DIM}:fontsize=20:x=214:y=50",
        f"drawtext=fontfile={FONT_BOLD}:text='{scene['kicker']}':fontcolor=white:"
        f"fontsize=20:x=w-tw-60:y=44:box=1:boxcolor={color}:boxborderw=14",
        f"drawtext=fontfile={FONT_BOLD}:textfile={title_file}:fontcolor={WHITE}:fontsize=58:x=60:y=180",
    ]
    for i, line in enumerate(lines):
        lf = textfile(idx, f"line{i}", line)
        y = body_y + i * line_h
        parts.append(f"drawbox=x=64:y={y + 9}:w=14:h=14:color={color}:t=fill")
        parts.append(f"drawtext=fontfile={FONT}:textfile={lf}:fontcolor={GREY}:fontsize=30:x=96:y={y}")
    png = os.path.join(BUILD, f"slide_{idx}.png")
    run(["ffmpeg", "-y", "-f", "lavfi", "-i", f"color=c={BG}:s={W}x{H}",
         "-vf", ",".join(parts), "-frames:v", "1", png])
    return png


def make_presenter(idx, total, scene):
    color = SECTION_COLORS.get(scene["kicker"], "0xe82127")
    title_file = textfile(idx, "title", scene["title"])
    sub_file = textfile(idx, "sub", scene.get("sub", ""))
    lines = scene["body"]
    parts = [
        f"drawbox=x=0:y=0:w={W}:h=8:color={color}:t=fill",
        f"drawbox=x=0:y={H-8}:w={W}:h=8:color={color}:t=fill",
        f"drawbox=x=0:y=0:w=560:h={H}:color={color}@0.10:t=fill",
        f"drawtext=fontfile={FONT_BOLD}:text=OpenDash:fontcolor={color}:fontsize=28:x=48:y=44",
        f"drawtext=fontfile={FONT_BOLD}:text='{scene['kicker']}':fontcolor=white:"
        f"fontsize=20:x=w-tw-60:y=44:box=1:boxcolor={color}:boxborderw=14",
        f"drawtext=fontfile={FONT_BOLD}:textfile={title_file}:fontcolor={WHITE}:fontsize=72:x=610:y=190",
        f"drawtext=fontfile={FONT}:textfile={sub_file}:fontcolor={color}:fontsize=28:x=614:y=290",
        f"drawbox=x=614:y=346:w=90:h=6:color={color}:t=fill",
    ]
    for i, line in enumerate(lines):
        lf = textfile(idx, f"pl{i}", line)
        y = 392 + i * 52
        parts.append(f"drawbox=x=618:y={y + 9}:w=14:h=14:color={color}:t=fill")
        parts.append(f"drawtext=fontfile={FONT}:textfile={lf}:fontcolor={GREY}:fontsize=28:x=650:y={y}")
    png = os.path.join(BUILD, f"slide_{idx}.png")
    run(["ffmpeg", "-y", "-f", "lavfi", "-i", f"color=c={BG}:s={W}x{H}",
         "-vf", ",".join(parts), "-frames:v", "1", png])
    return png


def make_term(idx, total, scene):
    """Painel de terminal com os comandos do passo."""
    color = SECTION_COLORS.get(scene["kicker"], "0xe82127")
    tx, ty, tw, th = 140, 96, 1000, 528
    parts = [
        f"drawbox=x={tx}:y={ty}:w={tw}:h={th}:color=0x010409:t=fill",
        f"drawbox=x={tx}:y={ty}:w={tw}:h=44:color=0x161b22:t=fill",
        f"drawbox=x={tx}:y={ty}:w={tw}:h={th}:color=0x30363d:t=2",
    ]
    for k, c in enumerate(("0xf85149", "0xd29922", "0x3fb950")):
        cx = tx + 22 + k * 26
        parts.append(f"drawbox=x={cx}:y={ty+15}:w=12:h=12:color={c}:t=fill")
    ttf = textfile(idx, "termtitle", scene.get("term_title", "terminal"))
    parts.append(f"drawtext=fontfile={FONT_MONO_BOLD}:textfile={ttf}:fontcolor={DIM}:"
                 f"fontsize=20:x={tx+120}:y={ty+12}")
    y0 = ty + 74
    lh = 42
    for i, ln in enumerate(scene["lines"]):
        y = y0 + i * lh
        if ln.strip().startswith("#"):
            lf = textfile(idx, f"tl{i}", ln)
            parts.append(f"drawtext=fontfile={FONT_MONO}:textfile={lf}:fontcolor={DIM}:"
                         f"fontsize=23:x={tx+40}:y={y}")
        else:
            pf = textfile(idx, f"tp{i}", "$")
            cf = textfile(idx, f"tl{i}", ln)
            parts.append(f"drawtext=fontfile={FONT_MONO_BOLD}:textfile={pf}:fontcolor={color}:"
                         f"fontsize=23:x={tx+40}:y={y}")
            parts.append(f"drawtext=fontfile={FONT_MONO}:textfile={cf}:fontcolor={WHITE}:"
                         f"fontsize=23:x={tx+72}:y={y}")
    parts += bars(idx, total, scene, color)
    png = os.path.join(BUILD, f"slide_{idx}.png")
    run(["ffmpeg", "-y", "-f", "lavfi", "-i", f"color=c={BG}:s={W}x{H}",
         "-vf", ",".join(parts), "-frames:v", "1", png])
    return png


def make_ui_frame(idx, total, scene):
    color = SECTION_COLORS.get(scene["kicker"], "0xe82127")
    img = os.path.join(ASSETS, scene["image"])
    wide = scene.get("wide")
    if wide:
        sw, sh, sx, sy = 1120, 280, (W - 1120) // 2, 150
        src_w = 1920
        parts = [f"scale={sw}:{sh}", f"pad={W}:{H}:{sx}:{sy}:color={BG}"]
        kx, ky = sw / src_w, sh / 480.0
    else:
        sw, sh, sx, sy = SCR_W, SCR_H, SCR_X, SCR_Y
        parts = [f"pad={W}:{H}:{sx}:{sy}:color={BG}"]
        kx = ky = 1.0
    parts.append(f"drawbox=x={sx - 1}:y={sy - 1}:w={sw + 2}:h={sh + 2}:color=0x30363d:t=2")
    for j, c in enumerate(scene.get("callouts", [])):
        cx, cy = sx + int(c["x"] * kx), sy + int(c["y"] * ky)
        cw, ch = int(c["w"] * kx), int(c["h"] * ky)
        cc = c.get("color", color)
        parts.append(f"drawbox=x={cx}:y={cy}:w={cw}:h={ch}:color={cc}@0.95:t=3")
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
    if os.path.exists(wav) and os.path.getsize(wav) > 2000:
        return wav

    async def synth():
        await Communicate(scene["narration"], VOICE, rate=RATE, pitch=PITCH).save(mp3)

    last = None
    for attempt in range(12):
        try:
            asyncio.run(synth())
            break
        except Exception as exc:  # noqa: BLE001 - rede/edge-tts pode oscilar
            last = exc
            print(f"  edge-tts cena {idx} tentativa {attempt + 1} falhou: {exc}", flush=True)
            time.sleep(min(20.0, 2.0 * (attempt + 1)))
    else:
        raise SystemExit(f"edge-tts falhou na cena {idx}: {last}")
    run(["ffmpeg", "-y", "-i", mp3, "-ar", "44100", "-ac", "2", wav])
    return wav


def seg_ready(seg):
    return os.path.exists(seg) and os.path.getsize(seg) > 2000


def pip_inputs():
    return ["-loop", "1", "-i", AV_IDLE, "-loop", "1", "-i", AV_TALK,
            "-loop", "1", "-i", AV_BLINK]


def pip_chain(first_label, out_label):
    talk = f"[{first_label}][at]overlay={PIP_X}:{PIP_Y}:enable='lt(mod(t,0.26),0.13)'[v1]"
    blink = f"[v1][ab]overlay={PIP_X}:{PIP_Y}:enable='lt(mod(t+1.0,3.4),0.13)',format=yuv420p[{out_label}]"
    pre = (f"[2:v]scale=-1:{PIP_H}[ai];[3:v]scale=-1:{PIP_H}[at];[4:v]scale=-1:{PIP_H}[ab];")
    base = f"[0:v][ai]overlay={PIP_X}:{PIP_Y}[v0]"
    return pre + base + ";" + talk + ";" + blink


def make_segment_still(idx, png, wav, presenter=False):
    seg = os.path.join(BUILD, f"seg_{idx}.mp4")
    if seg_ready(seg):
        return seg
    dur = duration(wav) + 1.1
    if presenter:
        ax, ay, ah = 70, 150, 560
        fc = (f"[2:v]scale=-1:{ah}[ai];[0:v][ai]overlay="
              f"{ax}:'{ay}+8*sin(2*PI*t/2.4)',format=yuv420p[v]")
        inputs = ["-loop", "1", "-i", AV_WAVE]
        run(["ffmpeg", "-y", "-loop", "1", "-framerate", str(FPS), "-i", png,
             "-i", wav, *inputs,
             "-filter_complex", fc, "-map", "[v]", "-map", "1:a",
             "-t", f"{dur:.3f}", "-af", "apad",
             "-c:v", "libx264", "-preset", "veryfast", "-r", str(FPS),
             "-c:a", "aac", "-b:a", "128k", "-ar", "44100", "-ac", "2",
             "-shortest", seg])
        return seg
    fc = pip_chain("v0", "v")
    run(["ffmpeg", "-y", "-loop", "1", "-framerate", str(FPS), "-i", png,
         "-i", wav, *pip_inputs(),
         "-filter_complex", fc, "-map", "[v]", "-map", "1:a",
         "-t", f"{dur:.3f}", "-af", "apad",
         "-c:v", "libx264", "-preset", "veryfast", "-r", str(FPS),
         "-c:a", "aac", "-b:a", "128k", "-ar", "44100", "-ac", "2",
         "-shortest", seg])
    return seg


def make_segment_anim(idx, total, scene, wav):
    seg = os.path.join(BUILD, f"seg_{idx}.mp4")
    if seg_ready(seg):
        return seg
    dur = duration(wav) + 1.1
    color = SECTION_COLORS.get(scene["kicker"], "0xe82127")
    overlays = bars(idx, total, scene, color)
    brand = textfile(idx, "brand", "OpenDash")
    overlays.append(
        f"drawtext=fontfile={FONT_BOLD}:textfile={brand}:fontcolor={color}:"
        f"fontsize=30:x={SCR_X + 16}:y={SCR_Y + 12}:"
        "box=1:boxcolor=0x0d1117@0.55:boxborderw=10")
    clip = scene.get("clip", ANIM)
    pre = (f"[0:v]pad={W}:{H}:{SCR_X}:{SCR_Y}:color={BG},fps={FPS},"
           + ",".join(overlays) + "[bg]")
    av = (";[2:v]scale=-1:%d[ai];[3:v]scale=-1:%d[at];[4:v]scale=-1:%d[ab];"
          "[bg][ai]overlay=%d:%d[v0];"
          "[v0][at]overlay=%d:%d:enable='lt(mod(t,0.26),0.13)'[v1];"
          "[v1][ab]overlay=%d:%d:enable='lt(mod(t+1.0,3.4),0.13)',format=yuv420p[v]"
          % (PIP_H, PIP_H, PIP_H, PIP_X, PIP_Y, PIP_X, PIP_Y, PIP_X, PIP_Y))
    run(["ffmpeg", "-y", "-stream_loop", "-1", "-i", clip, "-i", wav, *pip_inputs(),
         "-filter_complex", pre + av, "-map", "[v]", "-map", "1:a",
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
    for need in (AV_IDLE, AV_TALK, AV_BLINK, AV_WAVE):
        if not os.path.exists(need):
            raise SystemExit(f"falta {need} — rode capture_avatar.py primeiro")
    os.makedirs(BUILD, exist_ok=True)
    scenes = SCENES
    only = int(os.environ.get("TUT_ONLY", "0") or 0)
    if only > 0:
        scenes = scenes[:only]
    total = len(scenes)
    segments = []
    for i, scene in enumerate(scenes, 1):
        kind = scene.get("kind", "slide")
        print(f"[{i}/{total}] {scene['kicker']} - {scene['title']} ({kind})", flush=True)
        wav = make_voice(i, scene)
        time.sleep(0.8)
        if kind == "ui":
            png = make_ui_frame(i, total, scene)
            seg = make_segment_still(i, png, wav)
        elif kind == "term":
            png = make_term(i, total, scene)
            seg = make_segment_still(i, png, wav)
        elif kind == "presenter":
            png = make_presenter(i, total, scene)
            seg = make_segment_still(i, png, wav, presenter=True)
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

    print("[mix] gerando musica de fundo e mixando", flush=True)
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
