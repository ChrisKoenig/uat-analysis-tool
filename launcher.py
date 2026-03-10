"""
GCS Launcher
=============
Desktop launcher for starting and managing GCS services.
Checks Key Vault access, then provides one-click launch for:
  - Input Process (Flask app on port 5003)
  - Admin Process (Admin service on port 8008)
  - Triage Process (FastAPI + React on ports 8009/3000)
  - Field Portal (FastAPI + React on ports 8010/3001)
"""

import os
import sys
import subprocess
import threading
import webbrowser
import time
import tkinter as tk
from tkinter import ttk, messagebox
import socket
import signal

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------
PROJECT_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(PROJECT_DIR, 'apps'))

# Load environment-aware config (APP_ENV selects dev / preprod / prod).
try:
    from shared.config import get_app_config
    _cfg = get_app_config()
    _COSMOS_ENDPOINT = _cfg.cosmos_endpoint
    _COSMOS_TENANT_ID = _cfg.tenant_id
    _TRIAGE_API_PORT = _cfg.triage_api_port
    _TRIAGE_UI_PORT = _cfg.triage_ui_port
    _FIELD_API_PORT = _cfg.field_api_port
    _FIELD_UI_PORT = _cfg.field_ui_port
    _MAIN_APP_PORT = _cfg.main_app_port
    _ADMIN_PORT = _cfg.admin_service_port
except Exception as _e:
    print(f"[launcher] Warning: could not load app config ({_e}); using built-in defaults")
    _COSMOS_ENDPOINT = "https://cosmos-gcs-dev.documents.azure.com:443/"
    _COSMOS_TENANT_ID = "16b3c013-d300-468d-ac64-7eda0820b6d3"
    _TRIAGE_API_PORT = 8009
    _TRIAGE_UI_PORT = 3000
    _FIELD_API_PORT = 8010
    _FIELD_UI_PORT = 3001
    _MAIN_APP_PORT = 5003
    _ADMIN_PORT = 8008

SERVICES = {
    "input": {
        "label": "Input Process",
        "description": "Flask app — Issue Tracker Web UI",
        "url": f"http://localhost:{_MAIN_APP_PORT}",
        "port": _MAIN_APP_PORT,
        "main_py": "app.py",
        "cwd": PROJECT_DIR,
        "needs_kv_env": True,
    },
    "admin": {
        "label": "Admin Process",
        "description": "Admin Service — Evaluations, Stats, Config",
        "url": f"http://localhost:{_ADMIN_PORT}",
        "port": _ADMIN_PORT,
        "main_py": "admin_service.py",
        "cwd": PROJECT_DIR,
    },
    "triage": {
        "label": "Triage Process",
        "description": "Triage API + React UI (Rules, Triggers, Queue)",
        "url": f"http://localhost:{_TRIAGE_UI_PORT}",
        "ports": [_TRIAGE_API_PORT, _TRIAGE_UI_PORT],
        "commands": [
            {
                "label": "Triage API",
                "cmd": [
                    sys.executable, "-m", "uvicorn",
                    "triage.api.routes:app",
                    "--host", "0.0.0.0", "--port", str(_TRIAGE_API_PORT), "--reload"
                ],
                "cwd": PROJECT_DIR,
                "env_extra": {
                    "COSMOS_ENDPOINT": _COSMOS_ENDPOINT,
                    "COSMOS_USE_AAD": "true",
                    "COSMOS_TENANT_ID": _COSMOS_TENANT_ID,
                },
            },
            {
                "label": "Triage UI",
                "cmd": ["npm.cmd", "run", "dev"],
                "cwd": os.path.join(PROJECT_DIR, "apps", "triage", "ui"),
                "env_extra": {},
            },
        ],
    },
    "field": {
        "label": "Field Portal",
        "description": "Field Issue Submission — React SPA + FastAPI Orchestrator",
        "url": f"http://localhost:{_FIELD_UI_PORT}",
        "ports": [_FIELD_API_PORT, _FIELD_UI_PORT],
        "commands": [
            {
                "label": "Field API",
                "cmd": [
                    sys.executable, "-m", "uvicorn",
                    "field-portal.api.main:app",
                    "--host", "0.0.0.0", "--port", str(_FIELD_API_PORT), "--reload"
                ],
                "cwd": PROJECT_DIR,
                "env_extra": {},
            },
            {
                "label": "Field UI",
                "cmd": ["npm.cmd", "run", "dev"],
                "cwd": os.path.join(PROJECT_DIR, "field-portal", "ui"),
                "env_extra": {},
            },
        ],
    },
}


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
def is_port_open(port: int, host: str = "127.0.0.1", timeout: float = 1.0) -> bool:
    """Check if a port is accepting connections."""
    try:
        with socket.create_connection((host, port), timeout=timeout):
            return True
    except (ConnectionRefusedError, socket.timeout, OSError):
        return False


def wait_for_http(url: str, timeout_secs: int = 60) -> bool:
    """Wait until a URL returns an HTTP response (any status code)."""
    import urllib.request
    import urllib.error
    deadline = time.time() + timeout_secs
    while time.time() < deadline:
        try:
            urllib.request.urlopen(url, timeout=3)
            return True
        except urllib.error.URLError:
            pass
        except Exception:
            pass
        time.sleep(2)
    return False


def check_keyvault_access() -> tuple[bool, str]:
    """
    Quick check: can we reach Key Vault and read a known secret?
    Returns (ok, message).
    """
    try:
        from shared.keyvault_config import get_keyvault_config
        kv = get_keyvault_config()
        client = kv._get_client()
        # Try listing a known secret to verify access
        client.get_secret("AZURE-OPENAI-ENDPOINT")
        return True, "Key Vault is accessible"
    except Exception as e:
        msg = str(e)
        if "ForbiddenByPolicy" in msg or "Forbidden" in msg or "403" in msg:
            return False, "Key Vault access is BLOCKED by policy — enable it in the Azure Portal"
        elif "SecretNotFound" in msg:
            # We connected fine, just that secret doesn't exist
            return True, "Key Vault is accessible"
        elif "EnvironmentCredential" in msg or "DefaultAzureCredential" in msg:
            return False, "Azure credential issue — run 'az login' or check VPN"
        else:
            return False, f"Key Vault error: {msg[:120]}"


# ---------------------------------------------------------------------------
# Launcher GUI
# ---------------------------------------------------------------------------
class LauncherApp:
    def __init__(self, root: tk.Tk):
        self.root = root
        self.root.title("GCS Launcher")
        self.root.geometry("620x620")
        self.root.resizable(False, False)
        self.root.configure(bg="#1e1e1e")

        # Track running processes
        self._processes: dict[str, list[subprocess.Popen]] = {}
        self._starting: set[str] = set()  # Guard against double-clicks
        self._status_vars: dict[str, tk.StringVar] = {}
        self._btn_refs: dict[str, ttk.Button] = {}

        self._build_styles()
        self._build_ui()

        # Check KV on startup (non-blocking)
        self.root.after(200, self._check_keyvault)

        # Poll service status every 5s
        self._poll_status()

        # Cleanup on close
        self.root.protocol("WM_DELETE_WINDOW", self._on_close)

    # ---- Styles ----
    def _build_styles(self):
        style = ttk.Style()
        style.theme_use("clam")

        style.configure("Title.TLabel",
                        background="#1e1e1e", foreground="#569cd6",
                        font=("Segoe UI", 18, "bold"))
        style.configure("Subtitle.TLabel",
                        background="#1e1e1e", foreground="#9cdcfe",
                        font=("Segoe UI", 10))
        style.configure("Status.TLabel",
                        background="#1e1e1e", foreground="#cccccc",
                        font=("Segoe UI", 10))
        style.configure("KV.OK.TLabel",
                        background="#1e1e1e", foreground="#4ec9b0",
                        font=("Segoe UI", 10, "bold"))
        style.configure("KV.WARN.TLabel",
                        background="#1e1e1e", foreground="#f44747",
                        font=("Segoe UI", 10, "bold"))
        style.configure("KV.CHECK.TLabel",
                        background="#1e1e1e", foreground="#dcdcaa",
                        font=("Segoe UI", 10))

        style.configure("Card.TFrame", background="#252526")
        style.configure("Card.TLabel",
                        background="#252526", foreground="#cccccc",
                        font=("Segoe UI", 10))
        style.configure("CardTitle.TLabel",
                        background="#252526", foreground="#ffffff",
                        font=("Segoe UI", 13, "bold"))
        style.configure("CardDesc.TLabel",
                        background="#252526", foreground="#808080",
                        font=("Segoe UI", 9))

        style.configure("Launch.TButton",
                        font=("Segoe UI", 10, "bold"),
                        padding=(16, 8))
        style.configure("Stop.TButton",
                        font=("Segoe UI", 10),
                        padding=(12, 8))
        style.configure("Open.TButton",
                        font=("Segoe UI", 9),
                        padding=(10, 6))

        style.map("Launch.TButton",
                  background=[("active", "#0e639c"), ("!disabled", "#0078d4")],
                  foreground=[("!disabled", "white")])
        style.map("Stop.TButton",
                  background=[("active", "#a1260d"), ("!disabled", "#c72e2e")],
                  foreground=[("!disabled", "white")])

    # ---- UI ----
    def _build_ui(self):
        # Title bar
        hdr = ttk.Frame(self.root, style="Card.TFrame")
        hdr.pack(fill="x", padx=0, pady=0)
        inner = ttk.Frame(hdr, style="Card.TFrame")
        inner.pack(padx=16, pady=(12, 8))
        ttk.Label(inner, text="GCS Launcher", style="Title.TLabel",
                  background="#252526").pack(anchor="w")
        ttk.Label(inner, text="Start and manage GCS services",
                  style="Subtitle.TLabel", background="#252526").pack(anchor="w")

        # Key Vault status
        kv_frame = ttk.Frame(self.root)
        kv_frame.pack(fill="x", padx=16, pady=(10, 4))
        kv_frame.configure(style="Card.TFrame")
        self._kv_label = ttk.Label(kv_frame,
                                    text="  Checking Key Vault access...",
                                    style="KV.CHECK.TLabel",
                                    background="#252526")
        self._kv_label.pack(padx=12, pady=8, anchor="w")

        # Service cards
        for svc_id, svc in SERVICES.items():
            self._build_card(svc_id, svc)

        # Footer
        foot = ttk.Label(self.root,
                         text="Close this window to stop all launched services",
                         style="Status.TLabel")
        foot.pack(side="bottom", pady=(0, 10))

    def _build_card(self, svc_id: str, svc: dict):
        card = ttk.Frame(self.root, style="Card.TFrame", relief="flat")
        card.pack(fill="x", padx=16, pady=6)
        inner = ttk.Frame(card, style="Card.TFrame")
        inner.pack(fill="x", padx=14, pady=10)

        # Left side: title + description + status
        left = ttk.Frame(inner, style="Card.TFrame")
        left.pack(side="left", fill="x", expand=True)

        ttk.Label(left, text=svc["label"], style="CardTitle.TLabel").pack(anchor="w")
        ttk.Label(left, text=svc["description"], style="CardDesc.TLabel").pack(anchor="w")

        status_var = tk.StringVar(value="Stopped")
        self._status_vars[svc_id] = status_var
        status_lbl = ttk.Label(left, textvariable=status_var, style="Card.TLabel")
        status_lbl.pack(anchor="w", pady=(4, 0))
        # Store label ref for color updates
        status_lbl._svc_id = svc_id
        self._status_labels = getattr(self, "_status_labels", {})
        self._status_labels[svc_id] = status_lbl

        # Right side: buttons
        right = ttk.Frame(inner, style="Card.TFrame")
        right.pack(side="right")

        btn_launch = ttk.Button(right, text="Start", style="Launch.TButton",
                                command=lambda s=svc_id: self._start_service(s))
        btn_launch.pack(side="left", padx=(0, 6))
        self._btn_refs[f"{svc_id}_start"] = btn_launch

        btn_open = ttk.Button(right, text="Open", style="Open.TButton",
                              command=lambda s=svc_id: self._open_browser(s))
        btn_open.pack(side="left", padx=(0, 6))
        btn_open.state(["disabled"])
        self._btn_refs[f"{svc_id}_open"] = btn_open

        btn_stop = ttk.Button(right, text="Stop", style="Stop.TButton",
                              command=lambda s=svc_id: self._stop_service(s))
        btn_stop.pack(side="left")
        btn_stop.state(["disabled"])
        self._btn_refs[f"{svc_id}_stop"] = btn_stop

    # ---- Key Vault check ----
    def _check_keyvault(self):
        def _do_check():
            ok, msg = check_keyvault_access()
            self.root.after(0, lambda: self._update_kv_status(ok, msg))
        threading.Thread(target=_do_check, daemon=True).start()

    def _update_kv_status(self, ok: bool, msg: str):
        indicator = "\u2705" if ok else "\u26a0\ufe0f"
        style = "KV.OK.TLabel" if ok else "KV.WARN.TLabel"
        self._kv_label.configure(text=f"  {indicator}  {msg}", style=style)
        if not ok:
            messagebox.showwarning("Key Vault Access",
                f"Key Vault is not accessible.\n\n{msg}\n\n"
                "Services that depend on Key Vault secrets may fail to start.")

    # ---- Service management ----
    def _start_service(self, svc_id: str):
        if svc_id in self._processes or svc_id in self._starting:
            return  # Already running or starting

        svc = SERVICES[svc_id]

        # Check if the primary port is already in use
        ports = svc.get("ports", [svc.get("port")])
        primary_port = ports[0] if ports else None
        if primary_port and is_port_open(primary_port):
            # Service is already running externally — just open browser
            self._status_vars[svc_id].set("Running (external)")
            self._btn_refs[f"{svc_id}_start"].state(["disabled"])
            self._btn_refs[f"{svc_id}_open"].state(["!disabled"])
            webbrowser.open(svc["url"])
            return

        self._status_vars[svc_id].set("Starting...")
        self._btn_refs[f"{svc_id}_start"].state(["disabled"])
        self._starting.add(svc_id)

        def _do_start():
            procs = []
            try:
                # Load Key Vault secrets into env if needed
                env = os.environ.copy()
                env["PYTHONUNBUFFERED"] = "1"
                env["PYTHONIOENCODING"] = "utf-8"
                if svc.get("needs_kv_env"):
                    try:
                        from shared.keyvault_config import get_keyvault_config
                        kv = get_keyvault_config()
                        cfg = kv.get_config()
                        for k, v in cfg.items():
                            if v:
                                env[k] = v
                    except Exception as kv_err:
                        print(f"Warning: Could not load KV secrets: {kv_err}")

                if "commands" in svc:
                    # Triage: multiple commands to run
                    for cmd_info in svc["commands"]:
                        cmd_env = env.copy()
                        cmd_env.update(cmd_info.get("env_extra", {}))
                        p = subprocess.Popen(
                            cmd_info["cmd"],
                            cwd=cmd_info["cwd"],
                            env=cmd_env,
                            stdout=subprocess.DEVNULL,
                            stderr=subprocess.DEVNULL,
                            creationflags=subprocess.CREATE_NEW_PROCESS_GROUP,
                        )
                        procs.append(p)
                        time.sleep(2)  # Stagger startups
                else:
                    # Input / Admin: run the Python process directly
                    script_file = svc.get("main_py", "app.py")
                    p = subprocess.Popen(
                        [sys.executable, script_file],
                        cwd=svc.get("cwd", PROJECT_DIR),
                        env=env,
                        stdout=subprocess.DEVNULL,
                        stderr=subprocess.DEVNULL,
                        creationflags=subprocess.CREATE_NEW_PROCESS_GROUP,
                    )
                    procs.append(p)

                self._processes[svc_id] = procs

                # Wait for the service to respond to HTTP
                url = svc["url"]
                if svc_id == "triage":
                    # Wait for API first, then UI
                    wait_for_http("http://localhost:8009/health", timeout_secs=45)
                    wait_for_http("http://localhost:3000", timeout_secs=45)
                elif svc_id == "field":
                    wait_for_http("http://localhost:8010/api/field/health", timeout_secs=45)
                    wait_for_http("http://localhost:3001", timeout_secs=45)
                else:
                    wait_for_http(url, timeout_secs=45)

                self.root.after(0, lambda: self._on_started(svc_id))

            except Exception as e:
                self._starting.discard(svc_id)
                self.root.after(0, lambda: self._on_start_error(svc_id, str(e)))

        threading.Thread(target=_do_start, daemon=True).start()

    def _on_started(self, svc_id: str):
        self._starting.discard(svc_id)
        self._status_vars[svc_id].set("Running")
        self._btn_refs[f"{svc_id}_start"].state(["disabled"])
        self._btn_refs[f"{svc_id}_stop"].state(["!disabled"])
        self._btn_refs[f"{svc_id}_open"].state(["!disabled"])

        # Auto-open browser
        svc = SERVICES[svc_id]
        url = svc["url"]
        webbrowser.open(url)

    def _on_start_error(self, svc_id: str, error: str):
        self._status_vars[svc_id].set("Failed to start")
        self._btn_refs[f"{svc_id}_start"].state(["!disabled"])
        messagebox.showerror("Start Error",
                             f"Failed to start {SERVICES[svc_id]['label']}:\n\n{error}")

    def _stop_service(self, svc_id: str):
        procs = self._processes.pop(svc_id, [])
        for p in procs:
            try:
                # Send CTRL+BREAK to process group
                os.kill(p.pid, signal.CTRL_BREAK_EVENT)
            except (ProcessLookupError, OSError):
                pass
            try:
                p.terminate()
                p.wait(timeout=5)
            except Exception:
                try:
                    p.kill()
                except Exception:
                    pass

        # Also kill processes on the ports
        svc = SERVICES[svc_id]
        ports = svc.get("ports", [svc.get("port")])
        for port in ports:
            if port:
                self._kill_port(port)

        self._status_vars[svc_id].set("Stopped")
        self._btn_refs[f"{svc_id}_start"].state(["!disabled"])
        self._btn_refs[f"{svc_id}_stop"].state(["disabled"])
        self._btn_refs[f"{svc_id}_open"].state(["disabled"])

    def _kill_port(self, port: int):
        """Kill any process listening on the given port."""
        try:
            result = subprocess.run(
                ["powershell", "-Command",
                 f"Get-NetTCPConnection -LocalPort {port} -ErrorAction SilentlyContinue "
                 f"| Select-Object -ExpandProperty OwningProcess -Unique"],
                capture_output=True, text=True, timeout=5
            )
            for pid_str in result.stdout.strip().splitlines():
                pid_str = pid_str.strip()
                if pid_str.isdigit() and int(pid_str) > 0:
                    try:
                        os.kill(int(pid_str), signal.SIGTERM)
                    except (ProcessLookupError, OSError):
                        pass
        except Exception:
            pass

    def _open_browser(self, svc_id: str):
        url = SERVICES[svc_id]["url"]
        webbrowser.open(url)

    # ---- Status polling ----
    def _poll_status(self):
        for svc_id, svc in SERVICES.items():
            ports = svc.get("ports", [svc.get("port")])
            primary_port = ports[0] if ports else None

            if svc_id in self._processes:
                # We started it — check if still alive
                alive = any(p.poll() is None for p in self._processes[svc_id])
                port_up = is_port_open(primary_port) if primary_port else False

                if port_up:
                    self._status_vars[svc_id].set("Running")
                    self._btn_refs[f"{svc_id}_open"].state(["!disabled"])
                elif alive:
                    current = self._status_vars[svc_id].get()
                    if current not in ("Starting...",):
                        self._status_vars[svc_id].set("Running (port not ready)")
                else:
                    self._status_vars[svc_id].set("Stopped (exited)")
                    self._btn_refs[f"{svc_id}_start"].state(["!disabled"])
                    self._btn_refs[f"{svc_id}_stop"].state(["disabled"])
                    self._btn_refs[f"{svc_id}_open"].state(["disabled"])
                    self._processes.pop(svc_id, None)
            else:
                # Not started by us — check if port is open externally
                if primary_port and is_port_open(primary_port):
                    self._status_vars[svc_id].set("Running (external)")
                    self._btn_refs[f"{svc_id}_open"].state(["!disabled"])
                else:
                    if self._status_vars[svc_id].get() not in ("Starting...",):
                        self._status_vars[svc_id].set("Stopped")

        self.root.after(5000, self._poll_status)

    # ---- Cleanup ----
    def _on_close(self):
        for svc_id in list(self._processes.keys()):
            self._stop_service(svc_id)
        self.root.destroy()


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------
def main():
    try:
        root = tk.Tk()
        app = LauncherApp(root)
        root.mainloop()
    except Exception as e:
        print(f"Launcher error: {e}", file=sys.stderr)
        import traceback
        traceback.print_exc()
        input("Press Enter to exit...")
        sys.exit(1)


if __name__ == "__main__":
    main()
