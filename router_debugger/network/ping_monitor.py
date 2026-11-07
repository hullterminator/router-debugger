"""
Ping Monitor & Bootloader TTL Detection.
Monitors a target router IP during power-cycle to identify when recovery mode engages.
TTL heuristic:
  TTL=100: CFE / U-Boot bootloader recovery
  TTL=64: Linux kernel / OpenWrt
  TTL=128: Windows / Realtek embedded RTOS
  TTL=255: Cisco IOS / VxWorks
"""

import re
import time
import subprocess
import threading
from typing import Callable, Optional, Dict, Any

class PingMonitor:
    def __init__(self, target_ip: str, interval: float = 0.5):
        self.target_ip = target_ip
        self.interval = interval
        self.running = False
        self._thread: Optional[threading.Thread] = None
        self.alive = False
        self.last_ttl: Optional[int] = None
        self.last_latency: Optional[float] = None
        self.history = []

    def _ping_once(self) -> Dict[str, Any]:
        """Runs a single quick ICMP ping on Windows or Linux."""
        # Windows ping: -n 1 -w 500 (1 ping, 500ms timeout)
        cmd = ["ping", "-n", "1", "-w", "500", self.target_ip]
        try:
            res = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, timeout=1.5)
            output = res.stdout
            if "TTL=" in output.upper():
                ttl_match = re.search(r"TTL=(\d+)", output, re.IGNORECASE)
                time_match = re.search(r"time[<=](\d+)ms", output, re.IGNORECASE)
                ttl = int(ttl_match.group(1)) if ttl_match else None
                latency = float(time_match.group(1)) if time_match else 0.0

                stage = "Unknown"
                if ttl:
                    if ttl == 100:
                        stage = "Bootloader / Recovery (CFE / U-Boot)"
                    elif ttl <= 64:
                        stage = "Linux OS / OpenWrt Normal Boot"
                    elif ttl <= 128:
                        stage = "Embedded RTOS"
                    elif ttl >= 254:
                        stage = "VxWorks / Cisco"

                return {
                    "alive": True,
                    "ttl": ttl,
                    "latency_ms": latency,
                    "stage": stage,
                    "raw": output.strip().splitlines()[0] if output else ""
                }
            return {"alive": False, "ttl": None, "latency_ms": None, "stage": "No response"}
        except Exception as e:
            return {"alive": False, "error": str(e), "stage": "Error"}

    def watch(
        self,
        duration_seconds: float = 30.0,
        on_status: Optional[Callable[[Dict[str, Any]], None]] = None
    ):
        """Monitors the IP synchronously for a set duration."""
        self.running = True
        start = time.time()
        was_alive = False

        while self.running and (time.time() - start < duration_seconds):
            result = self._ping_once()
            self.alive = result["alive"]
            self.last_ttl = result.get("ttl")
            self.last_latency = result.get("latency_ms")

            if result["alive"] and not was_alive:
                result["event"] = "DEVICE_CAME_ONLINE"
            elif not result["alive"] and was_alive:
                result["event"] = "DEVICE_WENT_OFFLINE"
            else:
                result["event"] = "STABLE"

            was_alive = result["alive"]
            self.history.append(result)

            if on_status:
                on_status(result)

            time.sleep(self.interval)

    def stop(self):
        self.running = False
