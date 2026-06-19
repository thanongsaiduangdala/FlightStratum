
import tkinter as tk
from tkinter import messagebox
import threading
import webbrowser
import socket
import json
import os
import sys
import time
import urllib.request
import queue

class StreamToQueue:
    """Redirect writes (from print, logging, uvicorn) into a thread-safe queue
    so the GUI can display them in a scrollable text widget on demand."""
    def __init__(self, q):
        self.q = q
    def write(self, text):
        if text and text.strip():
            self.q.put(text)
    def flush(self):
        pass
    def isatty(self):
        return False
    @property
    def encoding(self):
        return "utf-8"

LOG_QUEUE = queue.Queue()
sys.stdout = StreamToQueue(LOG_QUEUE)
sys.stderr = StreamToQueue(LOG_QUEUE)

CONFIG_FILE = "launcher_config.json"

def get_base_dir():
    if getattr(sys, 'frozen', False):
        return os.path.dirname(sys.executable)
    return os.path.dirname(os.path.abspath(__file__))

BASE_DIR = get_base_dir()
CONFIG_PATH = os.path.join(BASE_DIR, CONFIG_FILE)

def load_port():
    try:
        with open(CONFIG_PATH, "r") as f:
            return json.load(f).get("port", 8050)
    except Exception:
        return 8050

def save_port(port):
    with open(CONFIG_PATH, "w") as f:
        json.dump({"port": port}, f)

def get_lan_ip():
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        s.connect(("8.8.8.8", 80))
        return s.getsockname()[0]
    except Exception:
        return "127.0.0.1"
    finally:
        s.close()

BG_DARK      = "#1a1a1a"   
PANEL_BG     = "#0f0f0f"   
BORDER       = "#333333"
TEXT_MAIN    = "#cccccc"
TEXT_DIM     = "#aaaaaa"
TEXT_FAINT   = "#555555"
ACCENT_CYAN  = "#4fc3f7"
ACCENT_CYAN_BG = "#111e25"
ACCENT_ORANGE  = "#FF9A00"
ACCENT_GREEN   = "#4caf50"
ACCENT_GREEN_BG = "#0f1f10"
ACCENT_RED     = "#c44444"
ENTRY_BG     = "#161616"
ENTRY_BORDER = "#2a2a2a"
BTN_IDLE_BG  = "#1a1a1a"

class LauncherApp:
    def __init__(self, root):
        self.root = root
        self.root.title("Flight Stratum Server")
        self.root.resizable(False, False)
        self.root.configure(bg=BG_DARK)

        self.menubar = DarkMenuBar(root, menus=[
            ("File", [
                ("Exit", lambda: self.on_close()),
            ]),
            ("Extras", [
                ("WASM Module (MobiFlight)", lambda: webbrowser.open("https://www.mobiflight.com/en/download.html")),
            ]),
        ])

        self.server_thread = None
        self.server_obj = None
        self.lan_ip = get_lan_ip()
        self.port = load_port()
        self.running = False

        title = tk.Label(root, text="Flight Stratum Server", bg=BG_DARK, fg=ACCENT_CYAN,
                          font=("Segoe UI", 10, "bold"))
        title.pack(pady=(16, 4))

        card = tk.Frame(root, bg=PANEL_BG, highlightbackground=BORDER, highlightthickness=1)
        card.pack(padx=20, pady=10, fill="both", expand=True)

        tk.Label(card, text="PORT", bg=PANEL_BG, fg=TEXT_FAINT,
                 font=("Segoe UI", 8)).pack(pady=(14, 2))
        self.port_var = tk.StringVar(value=str(self.port))
        self.port_entry = tk.Entry(card, textvariable=self.port_var, width=10, justify="center",
                                    bg=ENTRY_BG, fg="white", insertbackground="white",
                                    relief="flat", highlightthickness=1,
                                    highlightbackground=ENTRY_BORDER, highlightcolor=ACCENT_CYAN)
        self.port_entry.pack(pady=(0, 10))

        self.url_var = tk.StringVar(value="Server not running")
        tk.Label(card, textvariable=self.url_var, bg=PANEL_BG, fg=ACCENT_CYAN,
                 font=("Consolas", 10)).pack(pady=(0, 12))

        def make_btn(parent, text, command, accent=ACCENT_CYAN, accent_bg=ACCENT_CYAN_BG):
            btn = tk.Button(parent, text=text, command=command, width=15,
                             bg=BTN_IDLE_BG, fg=TEXT_DIM, activebackground=accent_bg,
                             activeforeground=accent, relief="flat",
                             highlightthickness=1, highlightbackground=BORDER,
                             font=("Segoe UI", 9), cursor="hand2", bd=0)

            def on_enter(e):
                if btn["state"] != "disabled":
                    btn.configure(bg=accent_bg, fg=accent)

            def on_leave(e):
                if btn["state"] != "disabled":
                    btn.configure(bg=BTN_IDLE_BG, fg=TEXT_DIM)

            btn.bind("<Enter>", on_enter)
            btn.bind("<Leave>", on_leave)
            return btn

        btn_frame = tk.Frame(card, bg=PANEL_BG)
        btn_frame.pack(pady=4)
        self.start_btn = make_btn(btn_frame, "Start Server", self.start_server, ACCENT_CYAN, ACCENT_CYAN_BG)
        self.start_btn.grid(row=0, column=0, padx=4)
        self.restart_btn = make_btn(btn_frame, "Restart", self.restart_server, ACCENT_ORANGE, "#1e1500")
        self.restart_btn.grid(row=0, column=1, padx=4)
        self.restart_btn.config(state="disabled")

        btn_frame2 = tk.Frame(card, bg=PANEL_BG)
        btn_frame2.pack(pady=8)
        self.open_btn = make_btn(btn_frame2, "Open in Browser", self.open_browser, ACCENT_GREEN, ACCENT_GREEN_BG)
        self.open_btn.grid(row=0, column=0, padx=4)
        self.open_btn.config(state="disabled")
        self.copy_btn = make_btn(btn_frame2, "Copy URL", self.copy_url, ACCENT_CYAN, ACCENT_CYAN_BG)
        self.copy_btn.grid(row=0, column=1, padx=4)
        self.copy_btn.config(state="disabled")
        self.status_var = tk.StringVar(value="MSFS: unknown   |   Server: stopped")
        tk.Label(root, textvariable=self.status_var, bg=BG_DARK, fg=TEXT_FAINT,
                 font=("Segoe UI", 8)).pack(pady=(8, 6))

        console_row = tk.Frame(root, bg=BG_DARK)
        console_row.pack(pady=(0, 6))

        self.show_console_var = tk.BooleanVar(value=False)
        console_check = tk.Checkbutton(
            console_row, text="Show backend console", variable=self.show_console_var,
            command=self.toggle_console, bg=BG_DARK, fg=TEXT_DIM,
            selectcolor=PANEL_BG, activebackground=BG_DARK, activeforeground=ACCENT_CYAN,
            font=("Segoe UI", 8), bd=0, highlightthickness=0
        )
        console_check.pack(side="left")

        self.clear_btn = tk.Label(
            console_row, text="Clear", fg=TEXT_FAINT, bg=BG_DARK,
            font=("Segoe UI", 8, "underline"), cursor="hand2"
        )
        self.clear_btn.pack(side="left", padx=(10, 0))
        self.clear_btn.bind("<Button-1>", lambda e: self.clear_console())
        self.clear_btn.bind("<Enter>", lambda e: self.clear_btn.configure(fg=ACCENT_CYAN))
        self.clear_btn.bind("<Leave>", lambda e: self.clear_btn.configure(fg=TEXT_FAINT))

        self.console_frame = tk.Frame(root, bg=PANEL_BG, highlightbackground=BORDER, highlightthickness=1)

        self.console_text = tk.Text(
            self.console_frame, bg=PANEL_BG, fg=TEXT_MAIN, insertbackground="white",
            relief="flat", font=("Consolas", 8), height=10, width=58, wrap="word"
        )
        scrollbar = tk.Scrollbar(self.console_frame, command=self.console_text.yview,
                                  bg=PANEL_BG, troughcolor=BG_DARK)
        self.console_text.configure(yscrollcommand=scrollbar.set, state="disabled")
        self.console_text.pack(side="left", fill="both", expand=True, padx=(6, 0), pady=6)
        scrollbar.pack(side="right", fill="y", pady=6)

        self.root.protocol("WM_DELETE_WINDOW", self.on_close)
        self.poll_status()
        self.poll_log_queue()

        self.root.update_idletasks()
        self.root.geometry("") 

    def toggle_console(self):
        if self.show_console_var.get():
            self.console_frame.pack(padx=20, pady=(0, 14), fill="both", expand=True)
        else:
            self.console_frame.pack_forget()
        self.root.update_idletasks()
        self.root.geometry("")

    MAX_CONSOLE_LINES = 1000 

    def poll_log_queue(self):
        try:
            had_new = False
            while True:
                line = LOG_QUEUE.get_nowait()
                self.console_text.configure(state="normal")
                self.console_text.insert("end", "prompt > " + line.rstrip("\n") + "\n")
                had_new = True
        except queue.Empty:
            pass
        if had_new:
            line_count = int(self.console_text.index("end-1c").split(".")[0])
            if line_count > self.MAX_CONSOLE_LINES:
                excess = line_count - self.MAX_CONSOLE_LINES
                self.console_text.delete("1.0", f"{excess + 1}.0")
            self.console_text.see("end")
            self.console_text.configure(state="disabled")
        self.root.after(200, self.poll_log_queue)

    def clear_console(self):
        self.console_text.configure(state="normal")
        self.console_text.delete("1.0", "end")
        self.console_text.configure(state="disabled")

    def current_url(self):
        return f"http://{self.lan_ip}:{self.port}"

    def start_server(self):
        try:
            port = int(self.port_var.get())
        except ValueError:
            messagebox.showerror("Invalid port", "Port must be a number.")
            return
        self.port = port
        save_port(port)

        import test as server_module 
        import uvicorn

        config = uvicorn.Config(server_module.app, host="0.0.0.0", port=port, log_level="warning", use_colors=False)
        self.server_obj = uvicorn.Server(config)
        server_module.CURRENT_PORT = port

        def run():
            self.server_obj.run()

        self.server_thread = threading.Thread(target=run, daemon=True)
        self.server_thread.start()
        self.running = True

        self.url_var.set(self.current_url())
        self.start_btn.config(state="disabled")
        self.port_entry.config(state="disabled")
        self.restart_btn.config(state="normal")
        self.open_btn.config(state="normal")
        self.copy_btn.config(state="normal")

        threading.Timer(1.2, self.open_browser).start()

    def restart_server(self):
        if self.server_obj:
            self.server_obj.should_exit = True
            time.sleep(0.5)
        self.start_btn.config(state="normal")
        self.port_entry.config(state="normal")
        self.running = False
        self.start_server()

    def open_browser(self):
        webbrowser.open(self.current_url())

    def copy_url(self):
        self.root.clipboard_clear()
        self.root.clipboard_append(self.current_url())

    def poll_status(self):
        msfs_ok = False
        if self.running:
            try:
                with urllib.request.urlopen(f"{self.current_url()}/config", timeout=1) as r:
                    msfs_ok = r.status == 200
            except Exception:
                msfs_ok = False
        server_state = "running" if self.running else "stopped"
        msfs_state = "connected" if msfs_ok else ("checking..." if self.running else "n/a")
        self.status_var.set(f"MSFS: {msfs_state}   |   Server: {server_state}")
        self.root.after(3000, self.poll_status)

    def on_close(self):
        if self.server_obj:
            self.server_obj.should_exit = True
        self.root.destroy()

class DarkMenuBar:
    """A fake menu bar (Frame + Labels) since tk.Menu can't be dark-themed on Windows."""
    def __init__(self, root, menus):
        self.root = root
        self.open_popup = None
        self.bar = tk.Frame(root, bg=PANEL_BG, height=26)
        self.bar.pack(side="top", fill="x")
        tk.Frame(root, bg=BORDER, height=1).pack(side="top", fill="x")

        for label, items in menus:
            self._add_menu_label(label, items)

    def _add_menu_label(self, label, items):
        lbl = tk.Label(self.bar, text=label, bg=PANEL_BG, fg=TEXT_DIM,
                        font=("Segoe UI", 9), padx=12, pady=4, cursor="hand2")
        lbl.pack(side="left")
        lbl.bind("<Enter>", lambda e: lbl.configure(bg=ACCENT_CYAN_BG, fg=ACCENT_CYAN))
        lbl.bind("<Leave>", lambda e: lbl.configure(bg=PANEL_BG, fg=TEXT_DIM))
        lbl.bind("<Button-1>", lambda e: self._toggle_popup(lbl, items))

    def _toggle_popup(self, lbl, items):
        if self.open_popup is not None:
            self._close_popup()
            return
        x = lbl.winfo_rootx()
        y = lbl.winfo_rooty() + lbl.winfo_height()

        popup = tk.Toplevel(self.root)
        popup.overrideredirect(True)
        popup.configure(bg=PANEL_BG, highlightbackground=BORDER, highlightthickness=1)
        popup.geometry(f"+{x}+{y}")

        for item_label, command in items:
            def make_cmd(cmd=command):
                def run():
                    self._close_popup()
                    cmd()
                return run
            item = tk.Label(popup, text=item_label, bg=PANEL_BG, fg=TEXT_DIM,
                             font=("Segoe UI", 9), padx=16, pady=6, anchor="w", cursor="hand2")
            item.pack(fill="x")
            item.bind("<Enter>", lambda e, w=item: w.configure(bg=ACCENT_CYAN_BG, fg=ACCENT_CYAN))
            item.bind("<Leave>", lambda e, w=item: w.configure(bg=PANEL_BG, fg=TEXT_DIM))
            item.bind("<Button-1>", lambda e, c=make_cmd(): c())

        self.open_popup = popup
        popup.focus_set()
        popup.bind("<FocusOut>", lambda e: self._close_popup())

    def _close_popup(self):
        if self.open_popup is not None:
            self.open_popup.destroy()
            self.open_popup = None

    def _on_root_click(self, event):
        if self.open_popup is not None:
            widget_under = event.widget
            if not str(widget_under).startswith(str(self.open_popup)):
                self._close_popup()


if __name__ == "__main__":
    root = tk.Tk()
    icon_path = os.path.join(get_base_dir(), "flight_stratum_icon_only.ico")
    try:
        root.iconbitmap(icon_path)
    except Exception:
        pass
    app = LauncherApp(root)
    root.mainloop()