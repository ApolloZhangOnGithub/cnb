"""swarm — launch and manage multi-agent sessions."""

import os
import threading
import time
import tomllib
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

from lib.board_db import BoardDB
from lib.common import ClaudesEnv, _write_config_toml, is_suspended
from lib.swarm_backend import SessionBackend, TmuxBackend, detect_backend
from lib.theme_profiles import PROFILES


@dataclass
class SwarmConfig:
    env: ClaudesEnv
    agent: str
    backend: SessionBackend
    install_home: Path

    @classmethod
    def load(cls) -> "SwarmConfig":
        env = ClaudesEnv.load()
        agent = os.environ.get("SWARM_AGENT", "claude")
        backend = detect_backend()
        install_home_raw = os.environ.get("CLAUDES_HOME", "")
        install_home = Path(install_home_raw) if install_home_raw else env.install_home
        return cls(env=env, agent=agent, backend=backend, install_home=install_home)


def _lookup_profile(name: str) -> dict[str, str] | None:
    for theme_profiles in PROFILES.values():
        if name in theme_profiles:
            return theme_profiles[name]
    return None


class SwarmManager:
    def __init__(self, cfg: SwarmConfig) -> None:
        self.cfg = cfg
        self._pending_threads: list[threading.Thread] = []

    @property
    def _env(self) -> ClaudesEnv:
        return self.cfg.env

    def _board_path(self) -> str:
        return str(self.cfg.install_home / "bin" / "board")

    def build_system_prompt(self, name: str) -> str:
        board = self._board_path()
        profile = _lookup_profile(name)
        identity = f"你是 {name}"
        if profile:
            identity += f"（{profile['full_name']} — {profile['info']}）"
        identity += "，cnb 团队的一员。你在后台工作，通过消息板与组长和同学协作。\n"
        return (
            f"{identity}"
            f"协作命令：\n"
            f"  {board} --as {name} inbox          # 查看收件箱\n"
            f"  {board} --as {name} ack            # 清空收件箱\n"
            f'  {board} --as {name} send <to> "msg" # 发消息\n'
            f'  {board} --as {name} status "desc"  # 更新状态\n'
            f"  {board} --as {name} task done      # 完成当前任务\n"
            f"规则：启动时先 inbox，完成任务后再 inbox，有进展随时汇报给发任务的人。\n"
            f"你可以直接 send 给任何同学协作，不用什么都通过一个人转。"
        )

    def build_agent_cmd(self, name: str) -> str:
        prompt = self.build_system_prompt(name)
        escaped = prompt.replace("'", "'\\''")
        if self.cfg.agent == "claude":
            return f"claude --name '{name}' --dangerously-skip-permissions --append-system-prompt '{escaped}'"
        elif self.cfg.agent == "trae":
            return "trae-cli"
        elif self.cfg.agent == "qwen":
            return "qwen"
        else:
            print(f"ERROR: unknown agent: {self.cfg.agent}")
            raise SystemExit(1)

    def _needs_prompt_injection(self) -> bool:
        return self.cfg.agent in ("trae", "qwen")

    def build_initial_prompt(self, name: str) -> str:
        engine_labels = {"trae": "Trae CLI", "qwen": "Qwen Code"}
        engine_label = engine_labels.get(self.cfg.agent, self.cfg.agent)
        sd = self._env.sessions_dir
        cv = self._env.cv_dir
        board = self._board_path()
        return (
            f"你是 {name}。你正在使用 {engine_label} 引擎。"
            f"按 CLAUDE.md 的启动流程执行："
            f"1. 读取 {sd}/{name}.md，"
            f"2. 读取 {cv}/{name}.md（如果存在），"
            f"3. 用 '{board}' --as {name} inbox 检查未读消息，"
            f"4. 根据 session 文件中的下一步继续工作，"
            f"如果没有明确任务，读 ROADMAP.md 自主找活干。"
        )

    def _save_cmd(self, name: str) -> str:
        board = self._board_path()
        return (
            f"git add -A && git commit -m '[WIP][{name}] auto-save before shutdown' "
            f"--allow-empty-message 2>/dev/null; "
            f"'{board}' --as {name} status 'shutdown: state saved'"
        )

    # --- Session registration ---

    def ensure_registered(self, names: list[str]) -> None:
        db_path = self._env.board_db
        if not db_path.exists():
            return
        db = BoardDB(db_path)
        with db.conn() as c:
            for n in names:
                db.ensure_session(n, c=c)

        for n in names:
            md = self._env.sessions_dir / f"{n}.md"
            if not md.exists():
                md.write_text(f"# {n}\n\n## Current task\n(none)\n\n## @inbox\n")

        config_path = self._env.claudes_dir / "config.toml"
        if config_path.exists():
            data = tomllib.loads(config_path.read_text())
            current_sessions = list(data.get("sessions", []))
            changed = False
            for n in names:
                if n not in current_sessions:
                    current_sessions.append(n)
                    data.setdefault("session", {})[n] = {"persona": ""}
                    changed = True
            if changed:
                data["sessions"] = current_sessions
                _write_config_toml(config_path, data)
        self._env.sessions.extend([n for n in names if n not in self._env.sessions])

    # --- Attendance ---

    def clock_in(self, name: str) -> None:
        t = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        with open(self._env.attendance_log, "a") as f:
            f.write(f"{t} | {name} | clock-in\n")

    def clock_out(self, name: str) -> None:
        t = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        with open(self._env.attendance_log, "a") as f:
            f.write(f"{t} | {name} | clock-out\n")

    def attendance(self) -> None:
        log = self._env.attendance_log
        if not log.exists():
            print("No attendance records yet.")
            return
        today = datetime.now().strftime("%Y-%m-%d")
        lines = log.read_text().splitlines()
        print(f"=== 出勤记录 (今日: {today}) ===")
        print()
        for name in self._env.sessions:
            today_ins = [l for l in lines if f"| {name} | clock-in" in l and l.startswith(today)]
            today_outs = [l for l in lines if f"| {name} | clock-out" in l and l.startswith(today)]
            last_in = today_ins[-1].split("|")[0].strip() if today_ins else ""
            last_out = today_outs[-1].split("|")[0].strip() if today_outs else ""
            if last_in and not last_out:
                print(f"  {name}: 在岗 (上班 {last_in})")
            elif last_out:
                print(f"  {name}: 已下班 (最后 {last_out})")
            else:
                print(f"  {name}: 今日未上班")
        print()
        print(f"历史记录: {log}")

    # --- Logging ---

    def log_startup(self, name: str) -> None:
        t = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        msg = f"[{t}] Starting {name} with agent: {self.cfg.agent}\n"
        log_dir = self._env.log_dir
        log_dir.mkdir(parents=True, exist_ok=True)
        with open(log_dir / "swarm.log", "a") as f:
            f.write(msg)
        with open(log_dir / f"{name}.log", "a") as f:
            f.write(msg)

    # --- Role filtering ---

    def get_role(self, name: str) -> str:
        config_path = self._env.claudes_dir / "config.toml"
        if not config_path.exists():
            return "unknown"
        try:
            data = tomllib.loads(config_path.read_text())
        except (OSError, tomllib.TOMLDecodeError):
            return "unknown"
        role = data.get("session", {}).get(name, {}).get("role", "")
        return role if role else "unknown"

    def filter_sessions(self, *, role: str = "", exclude: str = "") -> list[str]:
        result: list[str] = []
        for name in self._env.sessions:
            r = self.get_role(name)
            if exclude and r == exclude:
                continue
            if role and r != role:
                continue
            result.append(name)
        return result

    # --- High-level commands ---

    def _start_one(self, name: str) -> None:
        prefix = self._env.prefix
        backend = self.cfg.backend

        if backend.is_running(prefix, name):
            if backend.is_agent_active(prefix, name):
                print(f"  {name}: already running")
                return
            backend.stop_session(prefix, name, "true")
            time.sleep(1)

        self.log_startup(name)
        agent_cmd = self.build_agent_cmd(name)
        backend.start_session(prefix, name, self._env.project_root, agent_cmd)

        if isinstance(backend, TmuxBackend):
            t_trust = threading.Thread(target=backend.auto_accept_trust, args=(prefix, name))
            t_trust.start()
            self._pending_threads.append(t_trust)

        if self._needs_prompt_injection() or isinstance(backend, TmuxBackend):
            initial = self.build_initial_prompt(name)
            t = threading.Thread(
                target=backend.inject_initial_prompt,
                args=(prefix, name, initial, self._env.log_dir),
            )
            t.start()
            self._pending_threads.append(t)

        print(
            f"  {name}: started ({type(backend).__name__.lower().replace('backend', '')}: {prefix}-{name}, agent: {self.cfg.agent})"
        )

    def start(self, names: list[str], *, dry_run: bool = False, role: str = "", exclude: str = "") -> None:
        if not names:
            if role or exclude:
                targets = self.filter_sessions(role=role, exclude=exclude)
            else:
                targets = list(self._env.sessions)
        else:
            targets = names

        if dry_run:
            print(f"=== DRY RUN: would start {len(targets)} session(s) ===")
            for name in targets:
                sf = self._env.suspended_file
                if is_suspended(name, sf):
                    print(f"  {name}: SUSPENDED (would skip)")
                elif self.cfg.backend.is_running(self._env.prefix, name):
                    print(f"  {name}: already running (would skip)")
                else:
                    backend_name = type(self.cfg.backend).__name__.lower().replace("backend", "")
                    print(f"  {name}: would start (mode: {backend_name}, agent: {self.cfg.agent})")
            return

        self.ensure_registered(targets)

        if isinstance(self.cfg.backend, TmuxBackend):
            self.cfg.backend.enable_mouse()

        started = 0
        sf = self._env.suspended_file
        for name in targets:
            if is_suspended(name, sf):
                print(f"  {name}: SUSPENDED (use 'swarm resume {name}' to reactivate)")
                continue
            self._start_one(name)
            self.clock_in(name)
            started += 1

        for t in self._pending_threads:
            t.join(timeout=90)
        self._pending_threads.clear()

        print()
        backend_name = type(self.cfg.backend).__name__.lower().replace("backend", "")
        print(f"Mode: {backend_name} | Agent: {self.cfg.agent} | Started: {started}")
        print(f"Logs: {self._env.log_dir}")
        if isinstance(self.cfg.backend, TmuxBackend):
            print(f"  tmux attach -t {self._env.prefix}-<name>   # attach (Ctrl-B D to detach)")
        else:
            print(f"  screen -r {self._env.prefix}-<name>        # attach (Ctrl-A D to detach)")
        print("  swarm status                   # who's running")

    def status(self) -> None:
        backend_name = type(self.cfg.backend).__name__.lower().replace("backend", "")
        print(f"=== Swarm Status (mode: {backend_name}, agent: {self.cfg.agent}) ===")
        prefix = self._env.prefix
        sf = self._env.suspended_file
        for name in self._env.sessions:
            if is_suspended(name, sf):
                print(f"  {name}: SUSPENDED")
            elif self.cfg.backend.is_agent_active(prefix, name):
                line = self.cfg.backend.status_line(prefix, name, self.cfg.agent)
                print(f"  {name}: {line}")
            elif self.cfg.backend.is_running(prefix, name):
                print(f"  {name}: stale (session exists, agent exited)")
            else:
                print(f"  {name}: stopped")

    def stop(self, names: list[str], *, dry_run: bool = False, force: bool = False) -> None:
        if not names:
            targets = list(self._env.sessions)
        else:
            targets = names

        if dry_run:
            print(f"=== DRY RUN: would stop {len(targets)} session(s) ===")
            for name in targets:
                if self.cfg.backend.is_running(self._env.prefix, name):
                    print(f"  {name}: would stop (running)")
                else:
                    print(f"  {name}: not running (would skip)")
            return

        if not names and not force:
            running_count = sum(1 for n in targets if self.cfg.backend.is_running(self._env.prefix, n))
            if running_count > 0:
                print(f"About to stop ALL sessions ({running_count} running).")
                try:
                    answer = input("Continue? [y/N] ").strip().lower()
                except (EOFError, KeyboardInterrupt):
                    print("\nCancelled.")
                    return
                if answer not in ("y", "yes"):
                    print("Cancelled.")
                    return

        prefix = self._env.prefix
        for name in targets:
            if not self.cfg.backend.is_running(prefix, name):
                print(f"  {name}: not running")
                continue
            self.cfg.backend.stop_session(prefix, name, self._save_cmd(name))
            self.clock_out(name)

        if not names:
            self._kill_dispatcher_pids()

    def _kill_dispatcher_pids(self) -> None:
        for pidname in ("dispatcher.pid", "dispatcher-watchdog.pid"):
            pidfile = self._env.claudes_dir / pidname
            if pidfile.exists():
                try:
                    pid = int(pidfile.read_text().strip())
                    os.kill(pid, 0)
                    os.kill(pid, 15)
                except (ValueError, ProcessLookupError, PermissionError):
                    pass
                pidfile.unlink(missing_ok=True)

    def restart(self, names: list[str]) -> None:
        sf = self._env.suspended_file
        if not names:
            targets = [n for n in self._env.sessions if not is_suspended(n, sf)]
        else:
            targets = names

        print(f"=== Restarting {len(targets)} session(s) ===")
        prefix = self._env.prefix
        for name in targets:
            if is_suspended(name, sf):
                print(f"  {name}: SUSPENDED (use 'swarm resume {name}' to reactivate)")
                continue
            if self.cfg.backend.is_running(prefix, name):
                self.cfg.backend.stop_session(prefix, name, self._save_cmd(name))
                time.sleep(1)
            self._start_one(name)
            print(f"  {name}: restarted")

    def suspend(self, names: list[str]) -> None:
        if not names:
            print("Usage: swarm suspend <name> [names...]")
            raise SystemExit(1)
        sf = self._env.suspended_file
        prefix = self._env.prefix
        for name in names:
            if name not in self._env.sessions:
                print(f"  {name}: unknown session (valid: {' '.join(self._env.sessions)})")
                continue
            if is_suspended(name, sf):
                print(f"  {name}: already suspended")
                continue
            with open(sf, "a") as f:
                f.write(name + "\n")
            if self.cfg.backend.is_running(prefix, name):
                self.cfg.backend.stop_session(prefix, name, self._save_cmd(name))
                self.clock_out(name)
            print(f"  {name}: suspended")

    def resume(self, names: list[str]) -> None:
        if not names:
            print("Usage: swarm resume <name> [names...]")
            raise SystemExit(1)
        sf = self._env.suspended_file
        prefix = self._env.prefix
        for name in names:
            if name not in self._env.sessions:
                print(f"  {name}: unknown session (valid: {' '.join(self._env.sessions)})")
                continue
            if not is_suspended(name, sf):
                print(f"  {name}: not suspended")
                continue
            if sf.exists():
                lines = [l for l in sf.read_text().splitlines() if l != name]
                sf.write_text("\n".join(lines) + "\n" if lines else "")
            self._start_one(name)
            time.sleep(1)
            if self.cfg.backend.is_running(prefix, name):
                self.clock_in(name)
                print(f"  {name}: resumed + started")
            else:
                print(f"  {name}: resumed but FAILED to start (check tmux/claude availability)")

    def attach(self, name: str) -> None:
        if not name:
            print("Usage: swarm attach <name>")
            raise SystemExit(1)
        self.cfg.backend.attach(self._env.prefix, name)

    def help(self) -> None:
        backend_name = type(self.cfg.backend).__name__.lower().replace("backend", "")
        print(f"""\
swarm — manage multi-agent session swarm

Mode: {backend_name} (override with SWARM_MODE=tmux|screen)
Agent: {self.cfg.agent} (override with SWARM_AGENT=claude|trae|qwen)

  start [names...]    Launch sessions (default: all non-suspended)
  start --role=dev    Launch only sessions with matching role
  start --exclude=intern  Launch all except matching role
  status              Who's running
  stop [names...]     Gracefully stop sessions (default: all)
  restart [names...]  Stop + start (default: all non-suspended)
  suspend <names...>  Suspend sessions (stop + skip on future starts)
  resume <names...>   Resume suspended sessions (remove from list + start)
  attach <name>       Attach to session
  attendance          Show attendance records
  help                This message

Roles (from config.toml [session.X] role key): lead, dev, intern, dispatcher

Examples:
  swarm start                           # launch all with Claude (default)
  SWARM_AGENT=trae swarm start          # launch all with Trae
  swarm start alice bob                 # launch specific sessions
  swarm attach alice                    # interactive access
  swarm stop bob                        # stop one
  SWARM_MODE=screen swarm start         # force screen mode""")
