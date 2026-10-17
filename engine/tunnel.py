import os
import re
import atexit
import shutil
import subprocess
import threading
import time
from pathlib import Path
from typing import Optional

_PUBLIC_URL: Optional[str] = None
_TUNNEL_PROC: Optional[subprocess.Popen] = None
_MONITOR_THREAD: Optional[threading.Thread] = None

def get_cloudflared_path() -> Optional[Path]:
    """Finds cloudflared executable in project bin or system PATH"""
    project_bin = Path(__file__).resolve().parent.parent / "bin" / "cloudflared.exe"
    if project_bin.exists():
        return project_bin
    
    which_path = shutil.which("cloudflared")
    if which_path:
        return Path(which_path)
    return None

def get_public_url() -> Optional[str]:
    """Returns the currently active public Cloudflare HTTPS URL or None"""
    global _PUBLIC_URL
    return _PUBLIC_URL

_STOP_REQUESTED = False

def _tunnel_worker(local_port: int):
    global _PUBLIC_URL, _TUNNEL_PROC, _STOP_REQUESTED
    cf_bin = get_cloudflared_path()
    if not cf_bin:
        print("[Cloudflare Tunnel] cloudflared.exe not found in bin/ or PATH.")
        return

    cmd = [
        str(cf_bin), "tunnel",
        "--url", f"http://127.0.0.1:{local_port}",
        "--edge-ip-version", "4",
        "--protocol", "http2"
    ]
    
    url_regex = re.compile(r"https://[a-zA-Z0-9-]+\.trycloudflare\.com")
    
    while not _STOP_REQUESTED:
        try:
            _TUNNEL_PROC = subprocess.Popen(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                encoding="utf-8",
                errors="replace",
                bufsize=1
            )
            
            for line in iter(_TUNNEL_PROC.stdout.readline, ''):
                if _STOP_REQUESTED or not line:
                    break
                # Search for public URL
                match = url_regex.search(line)
                if match:
                    found_url = match.group(0)
                    if found_url != _PUBLIC_URL:
                        _PUBLIC_URL = found_url
                        print("=" * 64)
                        print(f"  🌐 PUBLIC INTERNET LINK (ប្រើបានគ្រប់ទីកន្លែងលើ 4G/5G/WiFi):")
                        print(f"  👉 {_PUBLIC_URL}")
                        print("=" * 64)
                        
            _TUNNEL_PROC.wait()
        except Exception as e:
            print(f"[Cloudflare Tunnel] Error: {e}")
            
        if _STOP_REQUESTED:
            break
        print("[Cloudflare Tunnel] Connection dropped. Auto-reconnecting in 3s...")
        time.sleep(3)
        
    _PUBLIC_URL = None

def start_tunnel(local_port: int):
    """Starts the Cloudflare tunnel in a background thread"""
    global _MONITOR_THREAD, _STOP_REQUESTED
    _STOP_REQUESTED = False
    if _MONITOR_THREAD and _MONITOR_THREAD.is_alive():
        return
    
    _MONITOR_THREAD = threading.Thread(target=_tunnel_worker, args=(local_port,), daemon=True)
    _MONITOR_THREAD.start()

def stop_tunnel():
    """Stops the Cloudflare tunnel process if running"""
    global _TUNNEL_PROC, _PUBLIC_URL, _STOP_REQUESTED
    _STOP_REQUESTED = True
    if _TUNNEL_PROC:
        try:
            _TUNNEL_PROC.terminate()
            _TUNNEL_PROC.kill()
        except Exception:
            pass
        _TUNNEL_PROC = None
    _PUBLIC_URL = None

atexit.register(stop_tunnel)
