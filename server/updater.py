"""Sistema de atualizacao via Git do OpenDash.

Um botao no painel verifica se ha commits novos no repositorio remoto e, se
houver, baixa e instala (``git pull`` + dependencias) e reinicia o servico.
"""
import os
import shutil
import subprocess
import sys
import threading
import time
from pathlib import Path


class Updater:
    def __init__(self, cfg, root):
        self.cfg = cfg
        self.root = Path(root)
        u = cfg.get("update") or {}
        self.enabled = bool(u.get("enabled", True))
        self.branch = u.get("branch") or "main"
        self.remote = u.get("remote") or "origin"
        self.install_deps = bool(u.get("install_deps", True))
        self.restart_command = (u.get("restart_command") or "").strip()
        self._lock = threading.Lock()
        self._log = []
        self.available = False
        self.behind = 0
        self._last_check = None

    # ------------------------------------------------------------------- infra
    def _log_line(self, text):
        for line in (text or "").splitlines():
            if line.strip():
                self._log.append(line.rstrip())
        self._log = self._log[-400:]

    def _env(self):
        env = dict(os.environ)
        env["GIT_TERMINAL_PROMPT"] = "0"
        env["GIT_ASKPASS"] = "/bin/true"
        env["GCM_INTERACTIVE"] = "never"
        return env

    def _git(self, args, timeout=90):
        return subprocess.run(["git", "-C", str(self.root), *args],
                              capture_output=True, text=True, timeout=timeout,
                              env=self._env())

    def _have_git(self):
        return (self.root / ".git").is_dir() and shutil.which("git") is not None

    # ------------------------------------------------------------------ status
    def status(self, with_fetch=False):
        if not self.enabled:
            return {"available": False, "enabled": False,
                    "reason": "atualizacoes desabilitadas"}
        if not self._have_git():
            return {"available": False, "enabled": True,
                    "reason": "repositorio git nao encontrado em " + str(self.root)}
        info = {"available": True, "enabled": True, "branch": self.branch,
                "remote": self.remote}
        try:
            info["current"] = self._git(["rev-parse", "--short", "HEAD"]).stdout.strip()
            info["current_full"] = self._git(["rev-parse", "HEAD"]).stdout.strip()
            info["subject"] = self._git(["log", "-1", "--pretty=%s"]).stdout.strip()
            info["date"] = self._git(["log", "-1", "--pretty=%cI"]).stdout.strip()
            info["dirty"] = bool(self._git(["status", "--porcelain"]).stdout.strip())
            info["remote_url"] = self._git(
                ["config", "--get", f"remote.{self.remote}.url"]).stdout.strip()
        except Exception as exc:
            return {"available": False, "enabled": True, "reason": str(exc)}
        if with_fetch:
            fetch = self._git(["fetch", "--prune", self.remote, self.branch], timeout=120)
            info["fetch_ok"] = fetch.returncode == 0
            if fetch.returncode != 0:
                info["fetch_error"] = (fetch.stderr or fetch.stdout).strip()[:300]
        ref = f"{self.remote}/{self.branch}"
        try:
            behind = self._git(["rev-list", "--count", f"HEAD..{ref}"]).stdout.strip()
            ahead = self._git(["rev-list", "--count", f"{ref}..HEAD"]).stdout.strip()
            info["behind"] = int(behind or 0)
            info["ahead"] = int(ahead or 0)
            info["latest"] = self._git(["log", "-1", "--pretty=%h %s", ref]).stdout.strip()
        except Exception:
            info["behind"] = 0
            info["ahead"] = 0
        info["available_update"] = info.get("behind", 0) > 0
        info["last_check"] = self._last_check
        self.available = info["available_update"]
        self.behind = info.get("behind", 0)
        return info

    def check(self):
        with self._lock:
            self._last_check = int(time.time())
            return self.status(with_fetch=True)

    # --------------------------------------------------------------- instalacao
    def install(self, restart=False):
        if not self.enabled:
            return {"ok": False, "error": "atualizacoes desabilitadas"}
        if not self._have_git():
            return {"ok": False, "error": "repositorio git nao encontrado"}
        self._log = []
        with self._lock:
            st = self.status(with_fetch=True)
            if not st.get("available"):
                return {"ok": False, "error": st.get("reason", "indisponivel"), "log": self._log}
            if not st.get("fetch_ok", True):
                return {"ok": False, "error": "falha no git fetch", "log": self._log}
            if not st.get("available_update"):
                return {"ok": True, "updated": False, "message": "ja esta atualizado",
                        "status": st, "log": self._log}
            if st.get("dirty"):
                self._log_line("alteracoes locais detectadas; tentando 'git stash'")
                self._log_line(self._git(["stash", "push", "-u", "-m",
                                          "opendash-autoupdate"]).stdout)
            pull = self._git(["pull", "--ff-only", self.remote, self.branch], timeout=180)
            self._log_line(pull.stdout)
            self._log_line(pull.stderr)
            if pull.returncode != 0:
                return {"ok": False, "error": "git pull falhou (conflito?)",
                        "log": self._log}
            if self.install_deps:
                self._install_deps()
            new_st = self.status()
            self._last_check = int(time.time())
        result = {"ok": True, "updated": True, "status": new_st, "log": self._log,
                  "restart": bool(restart)}
        if restart:
            threading.Thread(target=self._restart_later, daemon=True).start()
        return result

    def _install_deps(self):
        req = self.root / "requirements.txt"
        if not req.exists():
            return
        venv_pip = self.root / ".venv" / "bin" / "pip"
        pip = str(venv_pip) if venv_pip.exists() else (shutil.which("pip3") or shutil.which("pip"))
        if not pip:
            self._log_line("pip nao encontrado; pulando dependencias")
            return
        self._log_line("instalando dependencias (pip install -r requirements.txt)")
        try:
            proc = subprocess.run([pip, "install", "-q", "-r", str(req)],
                                  capture_output=True, text=True, timeout=300)
            self._log_line(proc.stdout)
            self._log_line(proc.stderr)
        except Exception as exc:
            self._log_line(f"falha ao instalar dependencias: {exc}")

    # ----------------------------------------------------------------- restart
    def _restart_later(self):
        time.sleep(1.2)
        try:
            self.restart()
        except Exception as exc:
            self._log_line(f"falha ao reiniciar: {exc}")

    def restart(self):
        if self.restart_command:
            subprocess.Popen(self.restart_command, shell=True)
            return {"ok": True, "how": self.restart_command}
        if shutil.which("systemctl"):
            probe = subprocess.run(["systemctl", "list-unit-files", "cardash.service"],
                                   capture_output=True, text=True)
            if "cardash.service" in (probe.stdout or ""):
                for cmd in (["systemctl", "restart", "cardash"],
                            ["sudo", "systemctl", "restart", "cardash"]):
                    proc = subprocess.run(cmd, capture_output=True, text=True)
                    if proc.returncode == 0:
                        return {"ok": True, "how": " ".join(cmd)}
        os.execv(sys.executable, [sys.executable, *sys.argv])
        return {"ok": True, "how": "re-exec"}
