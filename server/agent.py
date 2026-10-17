"""Assistente de voz do OpenDash.

Fluxo: push-to-talk no painel -> arecord (ALSA) -> STT (whisper.cpp) -> LLM
(OpenAI-compativel, ex.: Groq) com *function calling* -> acoes na UI + resposta.
TTS opcional via edge-tts. Tudo gratuito e de codigo aberto.
"""
import base64
import contextlib
import json
import os
import shutil
import subprocess
import tempfile
import threading
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

SYSTEM_PROMPT = (
    "Você é o assistente de voz do OpenDash, um painel automotivo. "
    "Responda em português do Brasil, curto e direto (no máximo 2 frases), "
    "porque a resposta será falada em voz alta. "
    "Quando o usuário pedir para abrir app, tocar música, traçar rota, mudar "
    "clima ou ir a uma página, use as ferramentas disponíveis. "
    "Não invente dados do veículo: use a ferramenta estado_veiculo quando precisar. "
    "Para perguntas gerais, responda normalmente sem chamar ferramentas."
)

TOOLS = [
    {"type": "function", "function": {
        "name": "abrir_app",
        "description": "Abre um aplicativo cadastrado (YouTube, Spotify, Mapas, Navegador) ou a página de navegação.",
        "parameters": {"type": "object", "properties": {
            "nome": {"type": "string", "description": "nome do app, ex.: YouTube, Spotube, Mapas"},
        }, "required": ["nome"]}}},
    {"type": "function", "function": {
        "name": "tocar_musica",
        "description": "Busca e toca uma música/vídeo. Use provider youtube (busca no painel), "
                       "spotube (abre o app Spotube) ou spotify (busca no Spotify).",
        "parameters": {"type": "object", "properties": {
            "provider": {"type": "string", "enum": ["youtube", "spotube", "spotify"]},
            "consulta": {"type": "string"},
        }, "required": ["provider", "consulta"]}}},
    {"type": "function", "function": {
        "name": "controlar_midia",
        "description": "Controles do player de mídia.",
        "parameters": {"type": "object", "properties": {
            "acao": {"type": "string", "enum": ["play", "pause", "proxima", "anterior"]},
        }, "required": ["acao"]}}},
    {"type": "function", "function": {
        "name": "navegar",
        "description": "Traça rota no mapa até um destino (endereço ou 'lat,lon').",
        "parameters": {"type": "object", "properties": {
            "destino": {"type": "string"},
        }, "required": ["destino"]}}},
    {"type": "function", "function": {
        "name": "ajustar_clima",
        "description": "Ajusta a climatização (ventilador 0-4, ar-condicionado ligado/desligado, temperatura 16-30).",
        "parameters": {"type": "object", "properties": {
            "ventilador": {"type": "integer"},
            "ar": {"type": "boolean"},
            "temperatura": {"type": "integer"},
        }}}},
    {"type": "function", "function": {
        "name": "abrir_pagina",
        "description": "Abre uma página do painel.",
        "parameters": {"type": "object", "properties": {
            "pagina": {"type": "string", "enum": [
                "drive", "energy", "nav", "media", "apps", "climate", "diag", "settings"]},
        }, "required": ["pagina"]}}},
    {"type": "function", "function": {
        "name": "estado_veiculo",
        "description": "Retorna o estado atual do veículo (velocidade, combustível, temperatura, autonomia).",
        "parameters": {"type": "object", "properties": {}}}},
    {"type": "function", "function": {
        "name": "abrir_url",
        "description": "Abre uma URL no navegador embutido.",
        "parameters": {"type": "object", "properties": {
            "url": {"type": "string"},
        }, "required": ["url"]}}},
]


class Agent:
    def __init__(self, cfg, hub, on_event=None):
        self.cfg = cfg
        self.hub = hub
        self.on_event = on_event or (lambda _ev: None)
        self._lock = threading.Lock()
        self._rec = None
        self._timer = None
        self._wav = None
        self.history = []
        self._sp_token = None
        self._sp_exp = 0.0
        self._tmp = Path(tempfile.gettempdir()) / "cardash-agent"
        self._tmp.mkdir(parents=True, exist_ok=True)

    @property
    def a(self):
        return self.cfg.get("agent") or {}

    def _log(self, msg):
        print(f"[agent] {msg}", flush=True)

    # ------------------------------------------------------------------ status
    def status(self):
        a = self.a
        model = a.get("whisper_model") or ""
        return {
            "enabled": bool(a.get("enabled", True)),
            "stt": a.get("stt"),
            "stt_ready": bool(shutil.which(a.get("whisper_bin") or "whisper-cli")
                              and model and Path(model).exists()),
            "arecord": shutil.which("arecord") is not None,
            "recording": self._rec is not None,
            "llm_base_url": a.get("llm_base_url"),
            "llm_model": a.get("llm_model"),
            "llm_ready": bool(os.environ.get(a.get("llm_key_env") or "") or a.get("llm_key")),
            "tts": a.get("tts"),
            "tts_voice": a.get("tts_voice"),
        }

    # -------------------------------------------------------------- gravacao
    def start_listen(self):
        a = self.a
        if not a.get("enabled", True):
            return {"ok": False, "error": "assistente desabilitado"}
        with self._lock:
            if self._rec is not None:
                return {"ok": False, "error": "ja gravando"}
            if shutil.which("arecord") is None:
                return {"ok": False, "error": "arecord ausente (instale alsa-utils)"}
            dev = a.get("mic_device") or "default"
            self._wav = str(self._tmp / "rec.wav")
            cmd = ["arecord", "-q", "-D", dev, "-f", "S16_LE", "-r", "16000",
                   "-c", "1", "-t", "wav", self._wav]
            try:
                self._rec = subprocess.Popen(cmd, stdout=subprocess.DEVNULL,
                                             stderr=subprocess.DEVNULL)
            except (OSError, ValueError) as exc:
                return {"ok": False, "error": f"falha ao abrir o microfone: {exc}"}
            max_s = max(1, min(20, int(a.get("record_seconds", 6))))
            self._timer = threading.Timer(max_s, self._auto_stop)
            self._timer.daemon = True
            self._timer.start()
        self.on_event({"type": "agent", "data": {"phase": "listening"}})
        return {"ok": True, "recording": True, "max_seconds": max_s}

    def _auto_stop(self):
        if self._rec is not None:
            self._log("limite de gravacao atingido; encerrando")
            self.listen_finish()

    def _stop_record(self):
        with self._lock:
            rec = self._rec
            self._rec = None
            if self._timer:
                self._timer.cancel()
                self._timer = None
        if rec is None:
            return None
        try:
            rec.send_signal(subprocess.signal.SIGINT)
            rec.wait(timeout=3)
        except Exception:
            with contextlib.suppress(Exception):
                rec.kill()
        return self._wav

    # ------------------------------------------------------------------- STT
    def _stt_cmd(self, wav):
        a = self.a
        tmpl = a.get("stt_command")
        if tmpl:
            import shlex
            return shlex.split(tmpl.format(
                wav=wav, model=a.get("whisper_model", ""), lang=a.get("stt_lang", "pt")))
        return [a.get("whisper_bin") or "whisper-cli",
                "-m", a.get("whisper_model") or "",
                "-f", wav, "-l", a.get("stt_lang") or "pt", "-nt"]

    def transcribe(self, wav):
        if not wav or not Path(wav).exists():
            return None, "audio ausente"
        try:
            proc = subprocess.run(self._stt_cmd(wav), capture_output=True,
                                  text=True, timeout=45)
        except FileNotFoundError:
            return None, "whisper-cli nao encontrado (rode tools/setup_assistant.sh)"
        except subprocess.TimeoutExpired:
            return None, "STT demorou demais"
        if proc.returncode != 0 and not (proc.stdout or "").strip():
            return None, (proc.stderr or "erro no STT").strip()[:160]
        text = " ".join((proc.stdout or "").split()).strip()
        return text, None

    # ------------------------------------------------------------------- LLM
    def _llm(self, messages, tools=None):
        a = self.a
        base = (a.get("llm_base_url") or "").rstrip("/")
        if not base:
            raise RuntimeError("llm_base_url nao configurada")
        key = os.environ.get(a.get("llm_key_env") or "") or a.get("llm_key") or ""
        payload = {"model": a.get("llm_model"), "messages": messages,
                   "temperature": 0.3, "max_tokens": 400}
        if tools:
            payload["tools"] = tools
            payload["tool_choice"] = "auto"
        headers = {"Content-Type": "application/json",
                   "User-Agent": "OpenDash/1.0 (+https://github.com/gugaash26-art/dash)"}
        if key:
            headers["Authorization"] = "Bearer " + key
        req = urllib.request.Request(base + "/chat/completions",
                                     data=json.dumps(payload).encode("utf-8"),
                                     headers=headers)
        with urllib.request.urlopen(req, timeout=30) as resp:
            return json.load(resp)

    # ---------------------------------------------------------------- Spotify
    def _spotify_token(self):
        a = self.a
        cid = a.get("spotify_client_id")
        secret = a.get("spotify_client_secret")
        if not cid or not secret:
            return None
        if self._sp_token and time.time() < self._sp_exp - 30:
            return self._sp_token
        basic = base64.b64encode(f"{cid}:{secret}".encode()).decode()
        req = urllib.request.Request(
            "https://accounts.spotify.com/api/token",
            data=urllib.parse.urlencode({"grant_type": "client_credentials"}).encode(),
            headers={"Authorization": "Basic " + basic,
                     "Content-Type": "application/x-www-form-urlencoded"})
        with urllib.request.urlopen(req, timeout=15) as resp:
            data = json.load(resp)
        self._sp_token = data.get("access_token")
        self._sp_exp = time.time() + float(data.get("expires_in", 3600))
        return self._sp_token

    def spotify_search(self, query):
        try:
            token = self._spotify_token()
            if not token:
                return None
            url = ("https://api.spotify.com/v1/search?type=track&limit=1&q="
                   + urllib.parse.quote(query))
            req = urllib.request.Request(url, headers={"Authorization": "Bearer " + token})
            with urllib.request.urlopen(req, timeout=15) as resp:
                items = (json.load(resp).get("tracks") or {}).get("items") or []
            if not items:
                return None
            it = items[0]
            return {"uri": it.get("uri"), "name": it.get("name"),
                    "artist": ", ".join(x["name"] for x in it.get("artists", []))}
        except Exception as exc:
            self._log(f"spotify search falhou: {exc}")
            return None

    # ------------------------------------------------------------------ TTS
    def tts_b64(self, text):
        a = self.a
        if not text or a.get("tts") != "edge":
            return None
        try:
            import asyncio
            import edge_tts
            mp3 = self._tmp / "say.mp3"
            voice = a.get("tts_voice") or "pt-BR-ThalitaMultilingualNeural"

            async def _gen():
                communicate = edge_tts.Communicate(_clean_speech(text), voice)
                await communicate.save(str(mp3))

            asyncio.run(_gen())
            return base64.b64encode(mp3.read_bytes()).decode("ascii")
        except Exception as exc:
            self._log(f"TTS falhou: {exc}")
            return None

    def _play_local(self, text):
        if not self.a.get("play_local") or not text:
            return
        try:
            out = self._tmp / "say.mp3"
            if out.exists():
                player = shutil.which("ffplay")
                if player:
                    subprocess.Popen([player, "-nodisp", "-autoexit", "-loglevel",
                                      "quiet", str(out)])
        except Exception:
            pass

    # --------------------------------------------------------------- execucao
    def _exec(self, name, args):
        actions = []
        if not isinstance(args, dict):
            args = {}
        if name == "abrir_app":
            app = str(args.get("nome") or "")
            actions.append({"type": "open_app", "name": app})
            return {"ok": True, "abrindo": app}, actions
        if name == "tocar_musica":
            provider = str(args.get("provider") or "youtube")
            q = str(args.get("consulta") or "")
            act = {"type": "media", "provider": provider, "query": q}
            if provider == "spotify":
                hit = self.spotify_search(q)
                if hit and hit.get("uri"):
                    act["uri"] = hit["uri"]
                    actions.append(act)
                    return {"ok": True, "tocando": f"{hit['name']} — {hit['artist']}"}, actions
            actions.append(act)
            return {"ok": True, "tocando": q, "provider": provider}, actions
        if name == "controlar_midia":
            act = str(args.get("acao") or "play")
            actions.append({"type": "media_control", "action": act})
            return {"ok": True, "acao": act}, actions
        if name == "navegar":
            dest = str(args.get("destino") or "")
            actions.append({"type": "navigate", "destination": dest})
            return {"ok": True, "destino": dest}, actions
        if name == "ajustar_clima":
            fan = args.get("ventilador")
            ac = args.get("ar")
            temp = args.get("temperatura")
            cmd = {"cmd": "climate"}
            if fan is not None:
                cmd["fan"] = int(fan)
            if ac is not None:
                cmd["ac"] = 1 if ac else 0
            try:
                self.hub.command(cmd)
            except Exception:
                pass
            actions.append({"type": "climate", "fan": fan, "ac": ac, "temp": temp})
            return {"ok": True}, actions
        if name == "abrir_pagina":
            page = str(args.get("pagina") or "media")
            actions.append({"type": "page", "page": page})
            return {"ok": True, "pagina": page}, actions
        if name == "estado_veiculo":
            return self._vehicle_state(), actions
        if name == "abrir_url":
            url = str(args.get("url") or "")
            actions.append({"type": "open_url", "url": url})
            return {"ok": True, "url": url}, actions
        return {"ok": False, "error": "ferramenta desconhecida"}, actions

    def _vehicle_state(self):
        try:
            st = self.hub.snapshot()
        except Exception:
            return {"erro": "sem dados"}
        trip = st.get("trip") or {}
        return {
            "velocidade_kmh": st.get("speed"),
            "rotacao_rpm": st.get("rpm"),
            "temperatura_agua_c": st.get("coolant"),
            "combustivel_pct": st.get("fuel"),
            "autonomia_km": st.get("range"),
            "marcha": st.get("gear"),
            "fonte": st.get("conn"),
            "consumo_l100": trip.get("cons"),
        }

    # ------------------------------------------------------------------- ask
    def run_ask(self, text):
        a = self.a
        if not a.get("enabled", True):
            return {"ok": False, "error": "assistente desabilitado"}
        text = (text or "").strip()
        if not text:
            return {"ok": False, "error": "texto vazio"}
        self.on_event({"type": "agent", "data": {"phase": "thinking", "transcript": text}})
        keep = max(1, int(a.get("max_turns", 8))) * 2
        messages = [{"role": "system", "content": SYSTEM_PROMPT}]
        messages += self.history[-keep:]
        messages.append({"role": "user", "content": text})

        actions = []
        reply = None
        for _ in range(5):
            try:
                resp = self._llm(messages, TOOLS)
            except urllib.error.HTTPError as exc:
                body = ""
                try:
                    body = exc.read().decode("utf-8", "ignore")[:200]
                except Exception:
                    pass
                msg = f"IA respondeu {exc.code}"
                if exc.code in (401, 403):
                    msg += " (verifique a chave de API)"
                self._log(f"LLM HTTP {exc.code}: {body}")
                return self._finish(text, msg, actions, error=True)
            except Exception as exc:
                self._log(f"LLM erro: {exc}")
                return self._finish(text, "Não consegui falar com a IA agora.", actions, error=True)

            choices = resp.get("choices") or []
            if not choices:
                break
            message = choices[0].get("message") or {}
            tool_calls = message.get("tool_calls")
            if tool_calls:
                messages.append({"role": "assistant",
                                 "content": message.get("content") or "",
                                 "tool_calls": tool_calls})
                for call in tool_calls:
                    fn = call.get("function") or {}
                    try:
                        call_args = json.loads(fn.get("arguments") or "{}")
                    except json.JSONDecodeError:
                        call_args = {}
                    result, acts = self._exec(fn.get("name"), call_args)
                    actions += acts
                    messages.append({"role": "tool", "tool_call_id": call.get("id"),
                                     "content": json.dumps(result, ensure_ascii=False)})
                continue
            reply = (message.get("content") or "").strip()
            break

        if not reply:
            reply = "Pronto." if actions else "Desculpe, não consegui responder."
        return self._finish(text, reply, actions)

    def _finish(self, transcript, reply, actions, error=False):
        if not error:
            self.history += [{"role": "user", "content": transcript},
                             {"role": "assistant", "content": reply}]
            self.history = self.history[-40:]
        audio = None
        if self.a.get("speak", True) and reply:
            audio = self.tts_b64(reply)
            self._play_local(reply)
        out = {"ok": not error, "transcript": transcript, "reply": reply,
               "actions": actions, "audio": audio, "done": True}
        self.on_event({"type": "agent", "data": out})
        return out

    # ------------------------------------------------------- push-to-talk fim
    def listen_finish(self):
        wav = self._stop_record()
        if not wav:
            return {"ok": False, "error": "nao estava gravando"}
        self.on_event({"type": "agent", "data": {"phase": "transcribing"}})
        text, err = self.transcribe(wav)
        if err:
            return self._finish("", f"Problema no reconhecimento de voz: {err}",
                                [], error=True)
        if not text:
            return self._finish("", "Não entendi. Tente falar de novo.", [])
        return self.run_ask(text)


def _clean_speech(text):
    import re
    text = re.sub(r"[`*_#>]", "", text or "")
    text = re.sub(r"https?://\S+", "link", text)
    return text.strip()
