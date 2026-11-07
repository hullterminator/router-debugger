"""
Network Gateway Discovery, Port Scanner, and Service Banner Grabber.
"""

import re
import socket
import subprocess
from concurrent.futures import ThreadPoolExecutor
from typing import Dict, List, Optional, Any

COMMON_ROUTER_PORTS = {
    21: "FTP (File Transfer)",
    22: "SSH (Secure Shell / Dropbear)",
    23: "Telnet (Unencrypted Debug Console)",
    53: "DNS (Dnsmasq)",
    80: "HTTP (Web Management / LuCI / RouterOS)",
    443: "HTTPS (Secure Web UI)",
    1900: "UPnP SSDP (Universal Plug and Play)",
    2323: "Telnet Alternate (Embedded Debug Port)",
    5555: "ADB / Realtek Debug Port",
    7547: "TR-069 (CWMP Remote Management)",
    8080: "HTTP-Alt (Proxy / Secondary Web UI)",
    8443: "HTTPS-Alt",
    9999: "Proprietary Debug Daemon / TP-Link Discovery"
}

def detect_default_gateway() -> Optional[str]:
    """Detects default router gateway IP using system route table."""
    # Method 1: Socket UDP route query (cross-platform, fast)
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))
        local_ip = s.getsockname()[0]
        s.close()
        # Guess gateway prefix (typically .1)
        prefix = ".".join(local_ip.split(".")[:3])
        default_guess = f"{prefix}.1"
    except Exception:
        local_ip = None
        default_guess = "192.168.1.1"

    # Method 2: ipconfig / route print parsing on Windows
    try:
        res = subprocess.run(["ipconfig"], stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, timeout=2)
        matches = re.findall(r"Default Gateway[ .]*:\s*([0-9]+\.[0-9]+\.[0-9]+\.[0-9]+)", res.stdout)
        if matches:
            # Filter out 0.0.0.0
            valid = [m for m in matches if m != "0.0.0.0"]
            if valid:
                return valid[0]
    except Exception:
        pass

    return default_guess

def check_port(ip: str, port: int, timeout: float = 0.8) -> Optional[Dict[str, Any]]:
    """Tests if a single TCP port is open and attempts a quick banner grab."""
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.settimeout(timeout)
    try:
        sock.connect((ip, port))
        banner = ""
        # Try grab banner if port is Telnet, SSH, or HTTP
        try:
            sock.settimeout(0.5)
            if port in (21, 22, 23, 2323):
                # Wait for greeting
                data = sock.recv(256)
                if data:
                    banner = data.decode("latin-1", errors="replace").strip()
            elif port in (80, 8080):
                sock.sendall(b"HEAD / HTTP/1.0\r\n\r\n")
                data = sock.recv(256)
                if data:
                    banner = data.decode("latin-1", errors="replace").splitlines()[0]
        except Exception:
            pass

        return {
            "port": port,
            "status": "OPEN",
            "service": COMMON_ROUTER_PORTS.get(port, "Unknown"),
            "banner": banner
        }
    except (socket.timeout, ConnectionRefusedError, OSError):
        return None
    finally:
        sock.close()

def scan_router_ports(
    ip: str,
    ports: Optional[List[int]] = None,
    timeout: float = 0.8,
    max_workers: int = 15
) -> List[Dict[str, Any]]:
    """Scans common router management and debug ports concurrently."""
    target_ports = ports or list(COMMON_ROUTER_PORTS.keys())
    open_ports = []

    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        futures = {executor.submit(check_port, ip, p, timeout): p for p in target_ports}
        for future in futures:
            result = future.result()
            if result:
                open_ports.append(result)

    open_ports.sort(key=lambda x: x["port"])
    return open_ports
