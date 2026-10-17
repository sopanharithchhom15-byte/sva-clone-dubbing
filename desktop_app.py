import os
import sys
import time
import socket
import threading
from pathlib import Path

# Fix Windows console encoding
if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding='utf-8', errors='replace')
        sys.stderr.reconfigure(encoding='utf-8', errors='replace')
    except Exception:
        pass

import webview

def is_port_in_use(port: int) -> bool:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        return s.connect_ex(('127.0.0.1', port)) == 0

def start_server_thread(port: int):
    import uvicorn
    from server import app
    uvicorn.run(app, host="0.0.0.0", port=port, log_level="warning")

def wait_for_server(port: int, timeout: float = 15.0) -> bool:
    import urllib.request
    start = time.time()
    url = f"http://127.0.0.1:{port}/api/network_info"
    while time.time() - start < timeout:
        try:
            with urllib.request.urlopen(url, timeout=1.0) as res:
                if res.status == 200:
                    return True
        except Exception:
            time.sleep(0.3)
    return False

def main():
    port = 8000
    
    # Check if server is already running
    if not is_port_in_use(port):
        t = threading.Thread(target=start_server_thread, args=(port,), daemon=True)
        t.start()
        print("⏳ កំពុងចាប់ផ្តើម SVA Engine...")
        if not wait_for_server(port):
            print("⚠️ Server took too long to start, opening window anyway...")
    else:
        print("✅ SVA Engine is active on port 8000.")

    app_url = f"http://127.0.0.1:{port}/"
    print(f"🚀 បើកផ្ទាំងកម្មវិធី Desktop: {app_url}")

    # Create native desktop software window
    window = webview.create_window(
        title="SVA Clone Dubbing - AI Studio",
        url=app_url,
        width=1340,
        height=880,
        min_size=(960, 640),
        background_color="#0f172a",
        text_select=True,
        zoomable=True
    )
    
    # Start native GUI loop
    webview.start(debug=False)

if __name__ == "__main__":
    main()
