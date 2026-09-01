"""
AI Predictive Maintenance System - Local Development Runner.

Launches both the FastAPI backend (port 8000) and the Frontend web server (port 3000)
concurrently and opens your browser.

Usage:
    python run_local.py
"""
import os
import sys
import time
import socket
import webbrowser
import subprocess
from http.server import HTTPServer, SimpleHTTPRequestHandler
import threading

ROOT_DIR = os.path.dirname(os.path.abspath(__file__))
BACKEND_DIR = os.path.join(ROOT_DIR, "backend")
FRONTEND_DIR = os.path.join(ROOT_DIR, "frontend")

BACKEND_PORT = 8000
FRONTEND_PORT = 3000


def get_python_executable():
    """Find the best python executable, prioritizing the project's .venv."""
    venv_py_win = os.path.join(ROOT_DIR, ".venv", "Scripts", "python.exe")
    venv_py_nix = os.path.join(ROOT_DIR, ".venv", "bin", "python")
    
    if os.path.exists(venv_py_win):
        return venv_py_win
    if os.path.exists(venv_py_nix):
        return venv_py_nix
    return sys.executable


def is_port_listening(port):
    """Test if a port is actively responding to TCP connections."""
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.settimeout(0.5)
        return s.connect_ex(('127.0.0.1', port)) == 0


class FrontendHandler(SimpleHTTPRequestHandler):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=FRONTEND_DIR, **kwargs)

    def end_headers(self):
        self.send_header('Access-Control-Allow-Origin', '*')
        self.send_header('Cache-Control', 'no-cache, no-store, must-revalidate')
        super().end_headers()

    def log_message(self, format, *args):
        pass


def run_frontend_server():
    server = HTTPServer(('0.0.0.0', FRONTEND_PORT), FrontendHandler)
    print(f"🌐 [Frontend] Running at: http://localhost:{FRONTEND_PORT}", flush=True)
    server.serve_forever()


def main():
    print("=" * 65, flush=True)
    print("  🚀 AI Predictive Maintenance System - Local Runner", flush=True)
    print("=" * 65, flush=True)

    python_exe = get_python_executable()
    print(f"🐍 Python Executable: {python_exe}", flush=True)
    print(f"📁 Backend Directory:  {BACKEND_DIR}", flush=True)
    print(f"📁 Frontend Directory: {FRONTEND_DIR}", flush=True)
    print("-" * 65, flush=True)

    backend_proc = None

    if is_port_listening(BACKEND_PORT):
        print(f"ℹ️  Port {BACKEND_PORT} is already listening. Backend already running.", flush=True)
    else:
        print(f"⚙️  [Backend] Starting FastAPI on http://localhost:{BACKEND_PORT} ...", flush=True)
        cmd = [
            python_exe, "-m", "uvicorn", "app.main:app",
            "--host", "0.0.0.0",
            "--port", str(BACKEND_PORT),
            "--reload"
        ]
        # Inherit stdio so logs and errors are visible in console
        backend_proc = subprocess.Popen(cmd, cwd=BACKEND_DIR)

    # Start frontend server in a background daemon thread
    if not is_port_listening(FRONTEND_PORT):
        frontend_thread = threading.Thread(target=run_frontend_server, daemon=True)
        frontend_thread.start()
    else:
        print(f"🌐 [Frontend] Already running at: http://localhost:{FRONTEND_PORT}", flush=True)

    # Wait for backend to be ready
    for _ in range(15):
        if is_port_listening(BACKEND_PORT):
            break
        time.sleep(0.5)

    frontend_url = f"http://localhost:{FRONTEND_PORT}"
    print(f"\n✅ System is Ready!", flush=True)
    print(f"👉 Open Dashboard:  {frontend_url}", flush=True)
    print(f"👉 API Docs:        http://localhost:{BACKEND_PORT}/docs", flush=True)
    print("\nPress Ctrl+C to stop all services.\n" + "-" * 65, flush=True)

    try:
        webbrowser.open(frontend_url)
    except Exception:
        pass

    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        print("\n🛑 Shutting down services...", flush=True)
        if backend_proc:
            backend_proc.terminate()
            backend_proc.wait()
        print("Done. Goodbye!", flush=True)


if __name__ == "__main__":
    main()
