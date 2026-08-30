"""Tiny Steward Web IDE & Control Center Launcher.

Launches FastAPI + Uvicorn server for the Web IDE at http://127.0.0.1:<port>/
"""

import socket
import sys
import threading
import time
import webbrowser
import uvicorn


def find_free_port(start_port=8000, max_port=8100):
    for port in range(start_port, max_port):
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            try:
                s.bind(('127.0.0.1', port))
                return port
            except socket.error:
                continue
    raise RuntimeError("No free ports found in range 8000-8100")


def main():
    try:
        port = find_free_port()
    except Exception as e:
        print(f"Error: {e}")
        sys.exit(1)

    url = f"http://127.0.0.1:{port}/"
    print(f"\n=============================================================")
    print(f"   ⚡ Tiny Steward Web IDE & Control Center Platform ⚡")
    print(f"=============================================================")
    print(f"  URL: {url}")
    print(f"=============================================================\n")

    def launch_browser():
        time.sleep(1.2)
        print(f"Opening browser to {url} ...")
        webbrowser.open(url)

    threading.Thread(target=launch_browser, daemon=True).start()

    # Run Uvicorn server serving FastAPI app from core.web_server
    uvicorn.run("core.web_server:app", host="127.0.0.1", port=port, log_level="info")


if __name__ == "__main__":
    main()
