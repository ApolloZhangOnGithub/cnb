"""swarm_backend — terminal multiplexer backends (tmux, screen)."""

import os
import re
import shlex
import shutil
import subprocess
import time
from abc import ABC, abstractmethod
from pathlib import Path

from lib.tmux_utils import (
    capture_pane as tmux_capture_pane,
)
from lib.tmux_utils import (
    has_session as tmux_has_session,
)
from lib.tmux_utils import (
    is_agent_running as tmux_is_agent_running,
)
from lib.tmux_utils import (
    pane_command as tmux_pane_command,
)
from lib.tmux_utils import (
    tmux_send,
)


class SessionBackend(ABC):
    """Abstract base for terminal multiplexer backends."""

    @abstractmethod
    def is_running(self, prefix: str, name: str) -> bool: ...

    def is_agent_active(self, prefix: str, name: str) -> bool:
        return self.is_running(prefix, name)

    @abstractmethod
    def start_session(
        self,
        prefix: str,
        name: str,
        project_root: Path,
        agent_cmd: str,
    ) -> str: ...

    @abstractmethod
    def stop_session(self, prefix: str, name: str, save_cmd: str) -> None: ...

    @abstractmethod
    def status_line(self, prefix: str, name: str, agent: str) -> str: ...

    @abstractmethod
    def attach(self, prefix: str, name: str) -> None: ...

    @abstractmethod
    def inject(self, prefix: str, name: str, message: str) -> None: ...

    @abstractmethod
    def capture_pane(self, prefix: str, name: str) -> str: ...

    @abstractmethod
    def inject_initial_prompt(self, prefix: str, name: str, prompt: str, log_dir: Path) -> None: ...


class TmuxBackend(SessionBackend):
    def _sess(self, prefix: str, name: str) -> str:
        return f"{prefix}-{name}"

    def is_running(self, prefix: str, name: str) -> bool:
        return tmux_has_session(self._sess(prefix, name))

    def _pane_command(self, prefix: str, name: str) -> str:
        return tmux_pane_command(self._sess(prefix, name))

    def is_agent_active(self, prefix: str, name: str) -> bool:
        return tmux_is_agent_running(self._sess(prefix, name))

    def capture_pane(self, prefix: str, name: str) -> str:
        return tmux_capture_pane(self._sess(prefix, name))

    def wait_for_shell(self, prefix: str, name: str, timeout: int = 15) -> bool:
        waited = 0
        while waited < timeout:
            text = self.capture_pane(prefix, name)
            if "$" in text or "%" in text or "❯" in text:
                return True
            time.sleep(1)
            waited += 1
        return False

    def wait_for_prompt(self, prefix: str, name: str, timeout: int = 60) -> bool:
        waited = 0
        while waited < timeout:
            text = self.capture_pane(prefix, name)
            if "❯" in text:
                return True
            time.sleep(2)
            waited += 2
        return False

    def auto_accept_trust(self, prefix: str, name: str, timeout: int = 60) -> None:
        sess = self._sess(prefix, name)
        waited = 0
        while waited < timeout:
            r = subprocess.run(
                ["tmux", "capture-pane", "-t", sess, "-p"],
                capture_output=True,
                text=True,
                timeout=5,
            )
            text = r.stdout.lower()
            # Claude and Codex use different workspace-trust copy; both default
            # to the safe "continue" choice when Enter is pressed.
            if (
                "i trust" in text
                or "trust this folder" in text
                or "do you trust the contents" in text
                or "press enter to continue" in text
            ):
                time.sleep(0.5)
                subprocess.run(["tmux", "send-keys", "-t", sess, "Enter"], timeout=10)
                return
            time.sleep(2)
            waited += 2

    def start_session(
        self,
        prefix: str,
        name: str,
        project_root: Path,
        agent_cmd: str,
    ) -> str:
        sess = self._sess(prefix, name)
        subprocess.run(["tmux", "new-session", "-d", "-s", sess, "-x", "200", "-y", "50"], timeout=10)
        self.wait_for_shell(prefix, name, timeout=10)
        project_arg = shlex.quote(str(project_root))
        tmux_send(
            sess,
            "source ~/.zprofile 2>/dev/null; "
            "source ~/.zshrc 2>/dev/null; "
            f"cd {project_arg} && export CNB_PROJECT={project_arg}",
        )
        self.wait_for_shell(prefix, name, timeout=10)
        tmux_send(sess, agent_cmd)
        return sess

    def stop_session(self, prefix: str, name: str, save_cmd: str) -> None:
        sess = self._sess(prefix, name)
        subprocess.run(["tmux", "send-keys", "-t", sess, "C-c"], timeout=10)
        time.sleep(1)
        subprocess.run(["tmux", "send-keys", "-t", sess, f"! {save_cmd}", "Enter"], timeout=10)
        time.sleep(3)
        subprocess.run(["tmux", "send-keys", "-t", sess, "/exit", "Enter"], timeout=10)

        waited = 0
        while self.is_running(prefix, name) and waited < 15:
            time.sleep(1)
            waited += 1
        if self.is_running(prefix, name):
            subprocess.run(["tmux", "kill-session", "-t", sess], timeout=10)
            print(f"  {name}: force killed (after {waited}s)")
        else:
            print(f"  {name}: exited gracefully")

    def status_line(self, prefix: str, name: str, agent: str) -> str:
        return f"running (tmux, engine: {agent})"

    def attach(self, prefix: str, name: str) -> None:
        os.execvp("tmux", ["tmux", "attach-session", "-t", self._sess(prefix, name)])

    def inject(self, prefix: str, name: str, message: str) -> None:
        sess = self._sess(prefix, name)
        if not self.is_running(prefix, name):
            print(f"  {name}: not running")
            raise SystemExit(1)
        oneline = message.replace("\n", " ")
        if not tmux_send(sess, oneline):
            print(f"  {name}: inject failed")
            raise SystemExit(1)
        print(f"  {name}: injected")

    def inject_initial_prompt(self, prefix: str, name: str, prompt: str, log_dir: Path) -> None:
        if self.wait_for_prompt(prefix, name, timeout=60):
            sess = self._sess(prefix, name)
            time.sleep(1)
            tmux_send(sess, prompt)
        else:
            with open(log_dir / f"{name}.log", "a") as f:
                f.write(f"[WARN] {name}: prompt not detected after 60s, skipping injection\n")

    def enable_mouse(self) -> None:
        subprocess.run(["tmux", "set", "-g", "mouse", "on"], capture_output=True, timeout=10)


class ScreenBackend(SessionBackend):
    def _sess(self, prefix: str, name: str) -> str:
        return f"{prefix}-{name}"

    def is_running(self, prefix: str, name: str) -> bool:
        sess_tag = f".{self._sess(prefix, name)}"
        r = subprocess.run(["screen", "-list"], capture_output=True, text=True, timeout=5)
        output = r.stdout + r.stderr
        return bool(re.search(rf"{re.escape(sess_tag)}\s", output))

    def capture_pane(self, prefix: str, name: str) -> str:
        return ""

    def start_session(
        self,
        prefix: str,
        name: str,
        project_root: Path,
        agent_cmd: str,
    ) -> str:
        sess = self._sess(prefix, name)
        subprocess.run(["screen", "-dmS", sess], timeout=10)
        time.sleep(1)
        subprocess.run(
            [
                "screen",
                "-S",
                sess,
                "-p",
                "0",
                "-X",
                "stuff",
                f"cd '{project_root}' && export CNB_PROJECT='{project_root}'",
            ],
            timeout=10,
        )
        subprocess.run(["screen", "-S", sess, "-p", "0", "-X", "stuff", "\r"], timeout=10)
        time.sleep(0.5)
        subprocess.run(["screen", "-S", sess, "-p", "0", "-X", "stuff", agent_cmd], timeout=10)
        subprocess.run(["screen", "-S", sess, "-p", "0", "-X", "stuff", "\r"], timeout=10)
        return sess

    def stop_session(self, prefix: str, name: str, save_cmd: str) -> None:
        sess = self._sess(prefix, name)
        subprocess.run(["screen", "-S", sess, "-p", "0", "-X", "stuff", "\x03"], timeout=10)
        time.sleep(1)
        subprocess.run(["screen", "-S", sess, "-p", "0", "-X", "stuff", f"! {save_cmd}\r"], timeout=10)
        time.sleep(3)
        subprocess.run(["screen", "-S", sess, "-p", "0", "-X", "stuff", "/exit\r"], timeout=10)

        waited = 0
        while self.is_running(prefix, name) and waited < 15:
            time.sleep(1)
            waited += 1
        if self.is_running(prefix, name):
            subprocess.run(["screen", "-S", sess, "-X", "quit"], timeout=10)
            print(f"  {name}: force killed (after {waited}s)")
        else:
            print(f"  {name}: exited gracefully")

    def status_line(self, prefix: str, name: str, agent: str) -> str:
        r = subprocess.run(["screen", "-list"], capture_output=True, text=True, timeout=5)
        output = r.stdout + r.stderr
        state = ""
        for line in output.splitlines():
            if f".{self._sess(prefix, name)}" in line:
                parts = line.strip().split()
                if parts:
                    state = parts[-1]
                break
        return f"running (screen, engine: {agent}) {state}"

    def attach(self, prefix: str, name: str) -> None:
        os.execvp("screen", ["screen", "-r", self._sess(prefix, name)])

    def inject(self, prefix: str, name: str, message: str) -> None:
        sess = self._sess(prefix, name)
        if not self.is_running(prefix, name):
            print(f"  {name}: not running")
            raise SystemExit(1)
        oneline = message.replace("\n", " ")
        subprocess.run(["screen", "-S", sess, "-p", "0", "-X", "stuff", oneline], timeout=10)
        time.sleep(0.3)
        subprocess.run(["screen", "-S", sess, "-p", "0", "-X", "stuff", "\r"], timeout=10)
        print(f"  {name}: injected")

    def inject_initial_prompt(self, prefix: str, name: str, prompt: str, log_dir: Path) -> None:
        time.sleep(3)
        sess = self._sess(prefix, name)
        subprocess.run(["screen", "-S", sess, "-p", "0", "-X", "stuff", prompt], timeout=10)
        time.sleep(0.3)
        subprocess.run(["screen", "-S", sess, "-p", "0", "-X", "stuff", "\r"], timeout=10)


def detect_backend() -> SessionBackend:
    override = os.environ.get("SWARM_MODE", "")
    if override == "tmux":
        return TmuxBackend()
    if override == "screen":
        return ScreenBackend()
    if shutil.which("tmux"):
        return TmuxBackend()
    if shutil.which("screen"):
        return ScreenBackend()
    print("ERROR: neither tmux nor screen found. Install one: brew install tmux")
    raise SystemExit(1)
