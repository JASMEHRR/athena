"""Desktop app launcher: starts Athena in the background (if needed) and opens it
in its own window (Edge or Chrome app mode, no tabs or address bar).

Used by the "Athena" desktop shortcut. No console window appears.
"""

import os
import subprocess
import sys
import time
import urllib.request
import webbrowser
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
URL = "http://127.0.0.1:8765/"
NO_WINDOW = 0x08000000 | 0x00000008  # CREATE_NO_WINDOW | DETACHED_PROCESS


def healthy() -> bool:
    try:
        with urllib.request.urlopen(URL + "api/v1/health", timeout=1) as r:
            return r.status == 200
    except Exception:
        return False


def start_server() -> None:
    pyw = ROOT / ".venv" / "Scripts" / "pythonw.exe"
    py = ROOT / ".venv" / "Scripts" / "python.exe"
    subprocess.run([str(py), "-m", "athena.backup"], cwd=ROOT, creationflags=0x08000000)
    subprocess.Popen([str(pyw), str(ROOT / "scripts" / "run_server.pyw")], cwd=ROOT, creationflags=NO_WINDOW)


def app_browser() -> str | None:
    pf = [os.environ.get(k, "") for k in ("ProgramFiles(x86)", "ProgramFiles", "LOCALAPPDATA")]
    for base in pf:
        for rel in (r"Microsoft\Edge\Application\msedge.exe", r"Google\Chrome\Application\chrome.exe"):
            p = Path(base) / rel
            if base and p.exists():
                return str(p)
    return None


if __name__ == "__main__":
    if not healthy():
        start_server()
        for _ in range(60):
            if healthy():
                break
            time.sleep(0.5)
    exe = app_browser()
    if exe:
        subprocess.Popen([exe, f"--app={URL}", "--window-size=1400,900"])
    else:
        webbrowser.open(URL)
