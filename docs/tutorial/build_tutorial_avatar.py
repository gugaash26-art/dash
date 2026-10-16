#!/usr/bin/env python3
"""Gera o video tutorial do OpenDash COM AVATAR apresentador.

Diferente de build_tutorial.py, este roteiro coloca um avatar (SVG renderizado por
capture_avatar.py) no canto inferior direito, "falando" durante a narracao, e uma
cena de abertura/encerramento em que ele aparece grande e acena. O conteudo apresenta
o sistema e, principalmente, as NOVAS funcoes: assistente de voz, Wi-Fi, Bluetooth,
atualizacao pelo GitHub e o cluster em barra.

Requer: ffmpeg, ffprobe e edge-tts (voz neural, precisa de internet).
Antes, gere o avatar e as telas novas:
  python3 docs/tutorial/capture_avatar.py
  python3 docs/tutorial/capture_new_ui.py
Depois:
Use: /car-dash/.venv/bin/python docs/tutorial/build_tutorial_avatar.py
Saida: opendash-tutorial-avatar.mp4 (mesma pasta)
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
BUILD = os.path.join(HERE, "build_avatar")
FONT_BOLD = "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"
FONT = "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"
OUT = os.path.join(HERE, "opendash-tutorial-avatar.mp4")

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
BOOT = os.path.join(ASSETS, "ui-boot.mp4")

SECTION_COLORS = {
    "ABERTURA": "0xe82127",
    "AGENDA": "0x2f81f7",
    "SISTEMA": "0x1f9e82",
    "INTERFACE": "0x2ea043",
    "GPS": "0x2f81f7",
    "APPS": "0x8957e5",
    "ASSISTENTE": "0xe82127",
    "CONECTIVIDADE": "0x2ea043",
    "ATUALIZAÇÕES": "0x8957e5",
    "CLUSTER": "0xd29922",
    "DEMONSTRAÇÃO": "0xe82127",
    "ENCERRAMENTO": "0xe82127",
}

SCENES = [
    # ---------------------------------------------------------------- abertura
    {
        "kind": "presenter", "avatar": "wave", "kicker": "ABERTURA",
        "title": "OpenDash", "sub": "o painel do seu carro, agora com voz",
        "body": ["Olá! Eu sou o assistente do OpenDash",
                 "e vou te mostrar as novidades do sistema."],
        "narration": (
            "Olá! Eu sou o assistente do OpenDash. Neste vídeo eu vou te apresentar o painel "
            "automotivo e, principalmente, as novas funções que acabaram de chegar: "
            "o assistente de voz com inteligência artificial, o Wi-Fi, o Bluetooth, a "
            "atualização pelo GitHub com um toque e o novo cluster em barra. Vamos lá!"),
    },
    {
        "kicker": "AGENDA", "title": "O que você vai ver",
        "body": ["O painel e suas páginas",
                 "Assistente de voz com IA (novo)",
                 "Wi-Fi e Bluetooth na tela (novo)",
                 "Atualização pelo GitHub (novo)",
                 "Cluster em barra para segunda tela (novo)"],
        "narration": (
            "O roteiro é simples: primeiro um passeio rápido pelo painel e suas páginas; "
            "depois, com calma, as quatro novidades deste sistema, mostrando telas reais. "
            "No fim, uma demonstração ao vivo."),
    },
    {
        "kind": "anim", "clip": BOOT, "kicker": "SISTEMA",
        "title": "Ligando o sistema",
        "caption": ["A animação de inicialização do OpenDash"],
        "narration": (
            "Ao ligar, o OpenDash mostra a animação de inicialização enquanto se conecta ao "
            "Arduino e aos sensores. Em poucos segundos, o painel está pronto para usar."),
    },
    {
        "kicker": "SISTEMA", "title": "Como funciona",
        "body": ["Arduino Mega lê OBD-II (CAN) e sensores",
                 "Orange Pi roda o servidor e a interface web",
                 "Os dados atualizam 10 vezes por segundo",
                 "Tela touch mostra o painel em tela cheia"],
        "narration": (
            "O sistema tem duas partes. O Arduino lê o barramento CAN OBD dois, os sensores "
            "analógicos e as entradas digitais, e envia tudo pela porta USB. O Orange Pi roda "
            "o servidor e a interface web, que atualiza dez vezes por segundo numa tela touch."),
    },
    # ------------------------------------------------------------- interface
    {
        "kind": "ui", "kicker": "INTERFACE", "title": "Página Painel",
        "image": "page_drive.png",
        "caption": ["Velocímetro, marcha, conta-giros, combustível e indicadores"],
        "narration": (
            "Esta é a página Painel, a principal. No centro, o velocímetro com arco animado e a "
            "marcha. Ao redor, conta-giros, nível de combustível, autonomia, odômetro e "
            "temperatura. No topo, os indicadores de seta, farol, cinto e portas."),
    },
    {
        "kind": "ui", "kicker": "INTERFACE", "title": "Página Energia",
        "image": "page_energy.png",
        "caption": ["Tanque, autonomia, consumo e histórico"],
        "narration": (
            "Na página Energia você acompanha o tanque em litros, a autonomia calculada e o "
            "consumo instantâneo e médio, com um gráfico das últimas leituras."),
    },
    {
        "kind": "ui", "kicker": "GPS", "title": "Página Navegação",
        "image": "page_nav.png",
        "caption": ["Mapa OpenStreetMap com posição, rastro, rota e busca"],
        "narration": (
            "A página Navegação usa o mapa do OpenStreetMap, com a posição em tempo real, o "
            "rastro percorrido e o rumo. Na lateral ficam a velocidade do GPS, os satélites e "
            "a busca de destino com traçado de rota."),
    },
    {
        "kind": "ui", "kicker": "APPS", "title": "Lançador de aplicativos",
        "image": "page_apps.png",
        "caption": ["YouTube, Spotify, Mapas e Navegador — e você cadastra os seus"],
        "narration": (
            "Na página Apps ficam os aplicativos, que são páginas web incorporadas: YouTube, "
            "Spotify, Mapas e um navegador. Com o botão Adicionar app, você cadastra qualquer "
            "serviço pelo endereço da web."),
    },
    {
        "kind": "ui", "kicker": "INTERFACE", "title": "Página Clima",
        "image": "page_climate.png",
        "caption": ["Ventilador e ar-condicionado acionam relés reais"],
        "narration": (
            "Na página Clima, os comandos de ventilador e ar-condicionado não são só visuais: "
            "eles acionam relés ligados ao Arduino."),
    },
    {
        "kind": "ui", "kicker": "INTERFACE", "title": "Página Diagnóstico",
        "image": "page_diag.png",
        "caption": ["Códigos de falha (DTC) e sensores ao vivo"],
        "narration": (
            "E a página Diagnóstico lê e apaga códigos de falha, com a descrição em português, "
            "e mostra os sensores ao vivo."),
    },
    # ------------------------------------------------------- NOVO: assistente
    {
        "kind": "ui", "kicker": "ASSISTENTE", "title": "Novidade: assistente de voz",
        "image": "page_media_agent.png",
        "caption": ["Segure para falar na página Mídia — o painel entende e executa"],
        "callouts": [
            {"x": 632, "y": 138, "w": 372, "h": 434, "label": "assistente de IA", "color": "0xe82127"},
            {"x": 648, "y": 172, "w": 340, "h": 70, "label": "segure para falar", "color": "0xe82127"},
            {"x": 648, "y": 308, "w": 340, "h": 74, "label": "o que você falou e a resposta", "color": "0x8957e5"},
        ],
        "narration": (
            "Chegamos na primeira novidade: o assistente de voz. Na página Mídia, você segura o "
            "botão para falar, solta, e o painel entende o pedido e executa. Aqui no exemplo, "
            "pedimos para abrir o YouTube. Ele reconhece a fala, decide a ação e ainda responde "
            "em voz alta. Dá para pedir para tocar uma música, traçar uma rota, abrir um app ou "
            "consultar as condições do carro."),
    },
    {
        "kicker": "ASSISTENTE", "title": "Como o assistente funciona",
        "body": ["Push-to-talk: segure, fale e solte",
                 "Voz para texto com whisper.cpp (grátis)",
                 "IA OpenAI-compatível — Groq por padrão (grátis)",
                 "A fala usa edge-tts, em português",
                 "Ações: abrir app, tocar música, traçar rota, clima"],
        "narration": (
            "Ele é todo de código aberto. A voz vira texto com o whisper ponto C P P; a IA é "
            "compatível com o formato da OpenAI e vem configurada com o Groq, que é gratuito; e "
            "a resposta é falada com o edge-tts, em português. Ele também entende comandos como "
            "abrir app, tocar música, traçar rota e mexer no clima."),
    },
    {
        "kind": "ui", "kicker": "ASSISTENTE", "title": "Onde configurar",
        "image": "page_settings_agent.png",
        "caption": ["Em Ajustes: microfone, idioma, IA, chave e voz"],
        "narration": (
            "Em Ajustes você configura tudo do assistente: o microfone, o idioma, o endereço e "
            "o modelo da IA, a chave de acesso e a voz. Também dá para desligar a fala ou o "
            "áudio local, se preferir."),
    },
    # ----------------------------------------------- NOVO: Wi-Fi e Bluetooth
    {
        "kind": "ui", "kicker": "CONECTIVIDADE", "title": "Novidade: Wi-Fi na tela",
        "image": "page_settings_net.png",
        "caption": ["Ligue o rádio, escaneie, conecte com senha e desconecte"],
        "callouts": [
            {"x": 16, "y": 128, "w": 992, "h": 292, "label": "redes Wi-Fi", "color": "0x2ea043"},
            {"x": 16, "y": 452, "w": 992, "h": 138, "label": "Bluetooth", "color": "0x2f81f7"},
        ],
        "narration": (
            "A segunda novidade é a conectividade. Na tela de Ajustes agora tem um cartão de "
            "Wi-Fi: você liga ou desliga o rádio, toca em Escanear e aparecem as redes com o "
            "sinal e o cadeado. Ao tocar em Conectar, ele pede a senha da rede. Logo abaixo, o "
            "cartão de Bluetooth faz o mesmo com os aparelhos."),
    },
    {
        "kind": "ui", "kicker": "CONECTIVIDADE", "title": "Bluetooth",
        "image": "page_settings_net.png",
        "caption": ["Escanear, parear, conectar fone ou celular"],
        "callouts": [
            {"x": 16, "y": 452, "w": 992, "h": 138, "label": "aparelhos e ação", "color": "0x2f81f7"},
        ],
        "narration": (
            "No Bluetooth, o fluxo é parecido: toque em Escanear para procurar aparelhos, como "
            "um fone ou o seu celular, e depois em Parear e Conectar. O aparelho ativo fica em "
            "destaque com o selo conectado. Se as ferramentas do sistema não estiverem "
            "instaladas, o cartão avisa o que falta — sem quebrar nada."),
    },
    # --------------------------------------------- NOVO: atualização GitHub
    {
        "kind": "ui", "kicker": "ATUALIZAÇÕES", "title": "Novidade: atualizar pelo GitHub",
        "image": "page_settings_update.png",
        "caption": ["Verificar versão e instalar uma nova com um toque"],
        "callouts": [
            {"x": 16, "y": 128, "w": 992, "h": 212, "label": "versão e botões", "color": "0x8957e5"},
            {"x": 812, "y": 165, "w": 184, "h": 52, "label": "instalar nova versão", "color": "0xe82127"},
        ],
        "narration": (
            "Terceira novidade: a atualização pelo GitHub. No cartão Atualizações do sistema, "
            "você vê a versão atual e toca em Verificar. Quando existe uma versão nova, o botão "
            "Atualizar agora fica disponível e faz tudo sozinho no Orange Pi."),
    },
    {
        "kicker": "ATUALIZAÇÕES", "title": "Atualização sem esforço",
        "body": ["Verifica sozinho ao ligar e de tempo em tempo",
                 "Baixa com git pull e instala as dependências",
                 "Guarda suas alterações locais com git stash",
                 "Reinicia o painel automaticamente",
                 "Funciona com repositório privado (token ou SSH)"],
        "narration": (
            "O melhor: ele verifica sozinho ao ligar e de tempos em tempos, e avisa no painel. "
            "Ao atualizar, ele baixa as novidades, instala as dependências, guarda as suas "
            "alterações locais e reinicia o painel. E funciona com repositório privado, usando "
            "um token ou uma chave SSH."),
    },
    # -------------------------------------------------- NOVO: cluster em barra
    {
        "kind": "ui", "kicker": "CLUSTER", "title": "Novidade: cluster em barra",
        "image": "page_bar.png", "wide": True,
        "caption": ["Segunda tela em formato longo (ex.: 1920×480)"],
        "narration": (
            "Quarta novidade: o cluster em barra para uma segunda tela, num monitor longo tipo "
            "mil novecentos e vinte por quatrocentos e oitenta. Tudo lado a lado: setas e "
            "indicadores, velocímetro com a marcha, conta-giros em barra, acelerador, autonomia, "
            "consumo e as temperaturas. É só conectar a segunda tela e escolher esse modo."),
    },
    # ---------------------------------------------------------- demonstração
    {
        "kind": "anim", "kicker": "DEMONSTRAÇÃO", "title": "OpenDash ao vivo",
        "caption": ["O sistema rodando em modo simulação, em tempo real"],
        "narration": (
            "E aqui está o OpenDash rodando ao vivo. Repare no velocímetro e no conta-giros se "
            "movendo, no gráfico se atualizando e na troca de páginas pelo toque. É exatamente "
            "assim que fica na tela do seu carro."),
    },
    # ------------------------------------------------------------- encerramento
    {
        "kind": "presenter", "avatar": "wave", "kicker": "ENCERRAMENTO",
        "title": "Pronto!", "sub": "mais conforto, mais segurança ao dirigir",
        "body": ["Documentação completa no README",
                 "Instalação e novidades no repositório",
                 "Bom passeio!"],
        "narration": (
            "E é isso! Agora o painel tem assistente de voz, Wi-Fi, Bluetooth, atualização pelo "
            "GitHub e o cluster em barra. Tudo está documentado no arquivo README do projeto. "
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
        f"drawtext=fontfile={FONT}:text=novidades do sistema:fontcolor={DIM}:fontsize=20:x=214:y=50",
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
    """Slide com o avatar grande a esquerda e o texto a direita."""
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
        sx, sy = SCR_X, SCR_Y
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
    """Sobrepõe o avatar no canto inferior direito, 'falando' e piscando."""
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
    total = len(SCENES)
    segments = []
    for i, scene in enumerate(SCENES, 1):
        kind = scene.get("kind", "slide")
        print(f"[{i}/{total}] {scene['kicker']} - {scene['title']} ({kind})", flush=True)
        wav = make_voice(i, scene)
        time.sleep(0.8)
        if kind == "ui":
            png = make_ui_frame(i, total, scene)
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
