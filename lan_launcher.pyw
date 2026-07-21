from __future__ import annotations

import os
from pathlib import Path
import socket
import subprocess
import sys
import tkinter as tk
from tkinter import ttk
from tkinter import messagebox

from app_settings import DIFFICULTY_LABELS, load_settings, save_settings
from rules import RULE_INFOS, RuleSettings


APP_DIR = Path(__file__).resolve().parent
DEFAULT_PORT = "50000"
SETTINGS_PATH = APP_DIR / "settings.json"
SERVER_OUT_LOG = APP_DIR / "lan_server.out.log"
SERVER_ERR_LOG = APP_DIR / "lan_server.err.log"
DIFFICULTY_BY_LABEL = {label: key for key, label in DIFFICULTY_LABELS.items()}


def python_executable(gui: bool = False) -> str:
    name = "pythonw.exe" if gui else "python.exe"
    venv_python = APP_DIR / ".venv" / "Scripts" / name
    if venv_python.exists():
        return str(venv_python)

    if gui and sys.executable.lower().endswith("python.exe"):
        pythonw = Path(sys.executable).with_name("pythonw.exe")
        if pythonw.exists():
            return str(pythonw)

    return sys.executable


def local_ipv4_addresses() -> list[str]:
    addresses: set[str] = set()
    try:
        hostname = socket.gethostname()
        for info in socket.getaddrinfo(hostname, None, socket.AF_INET):
            address = info[4][0]
            if not address.startswith("127."):
                addresses.add(address)
    except OSError:
        pass
    return sorted(addresses)


def port_available(port: int) -> bool:
    test_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    try:
        test_socket.bind(("0.0.0.0", port))
    except OSError:
        return False
    finally:
        test_socket.close()
    return True


def start_process(
    args: list[str],
    gui: bool = True,
    log_stdout: Path | None = None,
    log_stderr: Path | None = None,
) -> subprocess.Popen[bytes]:
    creationflags = 0
    if os.name == "nt":
        creationflags = subprocess.CREATE_NEW_PROCESS_GROUP
        if not gui:
            creationflags |= subprocess.CREATE_NO_WINDOW
    stdout = open(log_stdout, "a", encoding="utf-8") if log_stdout is not None else None
    stderr = open(log_stderr, "a", encoding="utf-8") if log_stderr is not None else None
    return subprocess.Popen(
        [python_executable(gui=gui), *args],
        cwd=APP_DIR,
        creationflags=creationflags,
        stdout=stdout,
        stderr=stderr,
    )


class Launcher(tk.Tk):
    def __init__(self) -> None:
        super().__init__()
        self.title("LAN大富豪ランチャー")
        self.resizable(False, False)
        self.server_process: subprocess.Popen[bytes] | None = None
        self.client_processes: list[subprocess.Popen[bytes]] = []
        self.settings = load_settings(SETTINGS_PATH)

        self.host_name = tk.StringVar(value="ホスト")
        self.join_name = tk.StringVar()
        self.host_ip = tk.StringVar()
        self.player_count = tk.IntVar(value=6)
        self.cpu_difficulty = tk.StringVar(
            value=DIFFICULTY_LABELS.get(self.settings.cpu_difficulty, "ふつう")
        )
        self.rule_vars = {
            info.key: tk.BooleanVar(value=bool(getattr(self.settings.rules, info.key)))
            for info in RULE_INFOS
        }
        self.status = tk.StringVar(value="ホストPCは「ホストとして開始」、参加者は「参加する」を押してください。")

        self.build_ui()
        self.protocol("WM_DELETE_WINDOW", self.on_close)

    def build_ui(self) -> None:
        root = tk.Frame(self, padx=18, pady=16)
        root.grid(row=0, column=0)

        tk.Label(root, text="LAN大富豪", font=("", 18, "bold")).grid(
            row=0, column=0, columnspan=3, pady=(0, 12)
        )

        ips = local_ipv4_addresses()
        ip_text = "\n".join(ips) if ips else "見つかりません。ipconfigで確認してください。"
        tk.Label(root, text="ホストPCの接続用IP:", anchor="w").grid(
            row=1, column=0, sticky="w"
        )
        tk.Label(root, text=ip_text, fg="#0b5cad", justify="left").grid(
            row=1, column=1, columnspan=2, sticky="w"
        )

        host_box = tk.LabelFrame(root, text="ホストPCで使う", padx=12, pady=10)
        host_box.grid(row=2, column=0, columnspan=3, sticky="ew", pady=(14, 8))
        tk.Label(host_box, text="名前").grid(row=0, column=0, sticky="w")
        tk.Entry(host_box, textvariable=self.host_name, width=24).grid(
            row=0, column=1, padx=8, pady=3
        )
        tk.Label(host_box, text="人数").grid(row=1, column=0, sticky="w")
        tk.Spinbox(
            host_box,
            from_=2,
            to=6,
            textvariable=self.player_count,
            width=5,
            state="readonly",
        ).grid(row=1, column=1, sticky="w", padx=8, pady=3)
        tk.Label(host_box, text="CPU").grid(row=2, column=0, sticky="w")
        ttk.Combobox(
            host_box,
            textvariable=self.cpu_difficulty,
            values=list(DIFFICULTY_LABELS.values()),
            width=10,
            state="readonly",
        ).grid(row=2, column=1, sticky="w", padx=8, pady=3)
        tk.Button(
            host_box,
            text="ホストとして開始",
            width=24,
            command=self.start_host,
        ).grid(row=0, column=2, rowspan=3, padx=(12, 0))

        rules_box = tk.LabelFrame(root, text="ホスト用ローカルルール", padx=12, pady=10)
        rules_box.grid(row=3, column=0, columnspan=3, sticky="ew", pady=8)
        for index, info in enumerate(RULE_INFOS):
            row = index // 2
            column = (index % 2) * 2
            tk.Checkbutton(
                rules_box,
                text=info.label,
                variable=self.rule_vars[info.key],
                anchor="w",
            ).grid(row=row, column=column, sticky="w", padx=(0, 18), pady=2)

        preset_row = (len(RULE_INFOS) + 1) // 2
        tk.Button(
            rules_box,
            text="シンプル",
            command=lambda: self.apply_rule_preset("simple"),
        ).grid(row=preset_row, column=0, sticky="w", pady=(8, 0))
        tk.Button(
            rules_box,
            text="標準",
            command=lambda: self.apply_rule_preset("standard"),
        ).grid(row=preset_row, column=1, sticky="w", pady=(8, 0))
        tk.Button(
            rules_box,
            text="全部ON",
            command=lambda: self.apply_rule_preset("party"),
        ).grid(row=preset_row, column=2, sticky="w", pady=(8, 0))
        tk.Button(
            rules_box,
            text="ルール保存",
            command=self.save_host_settings,
        ).grid(row=preset_row, column=3, sticky="e", pady=(8, 0))

        join_box = tk.LabelFrame(root, text="参加者PCで使う", padx=12, pady=10)
        join_box.grid(row=4, column=0, columnspan=3, sticky="ew", pady=8)
        tk.Label(join_box, text="ホストIP").grid(row=0, column=0, sticky="w")
        tk.Entry(join_box, textvariable=self.host_ip, width=24).grid(
            row=0, column=1, padx=8, pady=3
        )
        tk.Label(join_box, text="名前").grid(row=1, column=0, sticky="w")
        tk.Entry(join_box, textvariable=self.join_name, width=24).grid(
            row=1, column=1, padx=8, pady=3
        )
        tk.Button(
            join_box,
            text="参加する",
            width=24,
            command=self.join_game,
        ).grid(row=0, column=2, rowspan=2, padx=(12, 0))

        tk.Button(root, text="サーバー停止", command=self.stop_server).grid(
            row=5, column=0, sticky="w", pady=(8, 0)
        )
        tk.Label(root, textvariable=self.status, fg="#7a4a00", wraplength=560).grid(
            row=5, column=1, columnspan=2, sticky="w", padx=(12, 0), pady=(8, 0)
        )

    def selected_rules(self) -> RuleSettings:
        return RuleSettings(
            **{key: bool(var.get()) for key, var in self.rule_vars.items()}
        )

    def apply_rule_preset(self, preset: str) -> None:
        rules = RuleSettings.from_preset(preset)
        for info in RULE_INFOS:
            self.rule_vars[info.key].set(bool(getattr(rules, info.key)))

    def save_host_settings(self) -> None:
        difficulty = DIFFICULTY_BY_LABEL.get(self.cpu_difficulty.get(), "normal")
        self.settings.rules = self.selected_rules()
        self.settings.cpu_difficulty = difficulty
        self.settings.demo_mode = False
        save_settings(SETTINGS_PATH, self.settings)
        self.status.set("ホスト用ローカルルールを保存しました。次に開始するLAN対戦で使われます。")

    def ensure_server(self) -> None:
        if self.server_process is not None and self.server_process.poll() is None:
            return
        if not port_available(int(DEFAULT_PORT)):
            self.status.set("サーバーは既に起動しているようです。そのまま参加できます。")
            return
        try:
            SERVER_OUT_LOG.write_text("", encoding="utf-8")
            SERVER_ERR_LOG.write_text("", encoding="utf-8")
        except OSError:
            pass
        players = str(max(2, min(6, int(self.player_count.get()))))
        self.server_process = start_process(
            ["lan_server.py", "--players", players],
            gui=False,
            log_stdout=SERVER_OUT_LOG,
            log_stderr=SERVER_ERR_LOG,
        )
        self.after(800, self.check_server_started)

    def check_server_started(self) -> None:
        if self.server_process is None:
            return
        if self.server_process.poll() is None:
            self.status.set("サーバーを起動しました。参加者に接続用IPを伝えてください。")
            return
        message = "サーバー起動に失敗しました。"
        try:
            error_text = SERVER_ERR_LOG.read_text(encoding="utf-8").strip()
        except OSError:
            error_text = ""
        if error_text:
            message += f" {error_text.splitlines()[-1]}"
        self.status.set(message)
        messagebox.showerror("サーバー起動失敗", message)

    def start_host(self) -> None:
        name = self.host_name.get().strip()
        if not name:
            messagebox.showerror("入力不足", "ホストの名前を入力してください。")
            return
        self.save_host_settings()
        self.ensure_server()
        self.client_processes.append(
            start_process(
                ["lan_client.py", "--host", "127.0.0.1", "--name", name],
                gui=True,
            )
        )
        self.status.set("サーバーとホスト用ゲーム画面を起動しました。このランチャーは閉じずに置いてください。")

    def join_game(self) -> None:
        host = self.host_ip.get().strip()
        name = self.join_name.get().strip()
        if not host or not name:
            messagebox.showerror("入力不足", "ホストIPと名前を入力してください。")
            return
        self.client_processes.append(
            start_process(
                ["lan_client.py", "--host", host, "--name", name],
                gui=True,
            )
        )
        self.status.set("参加用ゲーム画面を起動しました。")

    def stop_server(self) -> None:
        if self.server_process is None or self.server_process.poll() is not None:
            self.status.set("起動中のサーバーはありません。")
            return
        self.server_process.terminate()
        self.server_process = None
        self.status.set("サーバーを停止しました。")

    def on_close(self) -> None:
        if self.server_process is not None and self.server_process.poll() is None:
            answer = messagebox.askyesnocancel(
                "終了確認",
                "サーバーが起動中です。サーバーも停止して閉じますか？",
            )
            if answer is None:
                return
            if answer:
                self.stop_server()
        self.destroy()


if __name__ == "__main__":
    Launcher().mainloop()
