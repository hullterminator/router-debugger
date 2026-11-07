"""
UART Serial Console, Auto-Baud Detection, and Bootloader Interrupter.
"""

import sys
import time
import string
import threading
from typing import List, Dict, Optional, Tuple, Callable
from pathlib import Path

try:
    import serial
    import serial.tools.list_ports
except ImportError:
    serial = None

COMMON_BAUDRATES = [115200, 57600, 38400, 19200, 9600, 230400]
BOOTLOADER_KEYWORDS = [
    b"u-boot", b"uboot", b"cfe", b"redboot", b"linux", b"kernel",
    b"bootloader", b"mips", b"arm", b"ram", b"dram", b"soc", b"flash",
    b"hit any key", b"autoboot", b"press any key", b"tpl", b"console"
]

def list_serial_ports() -> List[Dict[str, str]]:
    """Scan and list all detected serial/COM ports."""
    if serial is None:
        return [{"device": "N/A", "description": "pyserial not installed", "hwid": ""}]
    
    ports = serial.tools.list_ports.comports()
    results = []
    for port in ports:
        results.append({
            "device": port.device,
            "description": port.description or "Unknown",
            "hwid": port.hwid or ""
        })
    return results

def detect_baud_rate(
    port_name: str,
    candidate_bauds: Optional[List[int]] = None,
    sample_duration: float = 1.5
) -> Dict[str, Any]:
    """
    Test candidate baud rates by reading sample bytes and analyzing
    ASCII ratio and bootloader signature keywords.
    """
    if serial is None:
        return {"error": "pyserial is not installed"}

    candidates = candidate_bauds or COMMON_BAUDRATES
    scores = []

    for baud in candidates:
        try:
            with serial.Serial(port_name, baudrate=baud, timeout=0.2) as ser:
                ser.reset_input_buffer()
                start_time = time.time()
                collected = bytearray()
                while time.time() - start_time < sample_duration:
                    data = ser.read(128)
                    if data:
                        collected.extend(data)
                        if len(collected) > 1024:
                            break
                    time.sleep(0.05)

                if not collected:
                    scores.append({
                        "baud": baud,
                        "printable_ratio": 0.0,
                        "byte_count": 0,
                        "keywords_found": [],
                        "confidence": 0.0,
                        "sample": ""
                    })
                    continue

                # Analyze ASCII printability
                printable_count = sum(1 for b in collected if chr(b) in string.printable and b >= 32 or b in (10, 13, 9))
                ratio = printable_count / len(collected)

                # Check for keywords
                lower_data = bytes(collected).lower()
                found_kws = [kw.decode("ascii") for kw in BOOTLOADER_KEYWORDS if kw in lower_data]

                # Confidence calculation
                confidence = ratio * 100
                if found_kws:
                    confidence = min(100.0, confidence + (len(found_kws) * 20))

                scores.append({
                    "baud": baud,
                    "printable_ratio": round(ratio, 3),
                    "byte_count": len(collected),
                    "keywords_found": found_kws,
                    "confidence": round(confidence, 1),
                    "sample": bytes(collected[:80]).decode("ascii", errors="replace")
                })
        except Exception as e:
            scores.append({
                "baud": baud,
                "error": str(e),
                "confidence": 0.0
            })

    # Find highest confidence baud
    best = max(scores, key=lambda x: x.get("confidence", 0.0))
    return {
        "port": port_name,
        "best_baud": best.get("baud") if best.get("confidence", 0.0) > 40 else None,
        "results": scores
    }

def interrupt_bootloader(
    port_name: str,
    baudrate: int = 115200,
    trigger_sequence: str = "space",
    duration_seconds: float = 12.0,
    callback: Optional[Callable[[str], None]] = None
) -> Dict[str, Any]:
    """
    Rapidly sends interrupt payloads to break the bootloader into interactive shell.
    Supports: 'space', 'enter', 'ctrl_c', 'tpl' (TP-Link), or custom sequences.
    """
    if serial is None:
        return {"success": False, "error": "pyserial not installed"}

    seq_map = {
        "space": b" ",
        "enter": b"\r\n",
        "ctrl_c": b"\x03",
        "tpl": b"tpl\r\n",
        "esc": b"\x1b",
        "all": [b" ", b"\r\n", b"\x03", b"tpl\r\n"]
    }

    payloads = seq_map.get(trigger_sequence, [b" "])
    if not isinstance(payloads, list):
        payloads = [payloads]

    log_buffer = []
    stopped = False

    try:
        with serial.Serial(port_name, baudrate=baudrate, timeout=0.1) as ser:
            ser.reset_input_buffer()
            ser.reset_output_buffer()
            start_time = time.time()
            idx = 0

            while time.time() - start_time < duration_seconds:
                # Send interrupt payload
                payload = payloads[idx % len(payloads)]
                ser.write(payload)
                idx += 1

                # Read response
                incoming = ser.read(256)
                if incoming:
                    text = incoming.decode("latin-1", errors="replace")
                    log_buffer.append(text)
                    if callback:
                        callback(text)

                    # Check for prompt
                    lower = text.lower()
                    if any(p in lower for p in ["=>", "u-boot>", "cfe>", "ar7240>", "ath>", "bootloader>", "shell>", "#"]):
                        stopped = True
                        break

                time.sleep(0.04)

        return {
            "success": stopped,
            "port": port_name,
            "baudrate": baudrate,
            "prompt_detected": stopped,
            "log": "".join(log_buffer)
        }
    except Exception as e:
        return {"success": False, "error": str(e), "log": "".join(log_buffer)}

class SerialLogger:
    """Live Serial Terminal monitor with capture to log file."""
    def __init__(self, port: str, baud: int, log_file: Optional[str] = None):
        self.port = port
        self.baud = baud
        self.log_file = log_file
        self.running = False
        self.ser: Optional[serial.Serial] = None
        self._thread: Optional[threading.Thread] = None

    def start(self, on_data: Optional[Callable[[str], None]] = None):
        if serial is None:
            raise RuntimeError("pyserial is required")
        self.ser = serial.Serial(self.port, self.baud, timeout=0.1)
        self.running = True

        log_handle = open(self.log_file, "a", encoding="utf-8") if self.log_file else None

        def worker():
            try:
                while self.running:
                    chunk = self.ser.read(128)
                    if chunk:
                        text = chunk.decode("utf-8", errors="replace")
                        if log_handle:
                            timestamp = time.strftime("[%Y-%m-%d %H:%M:%S] ")
                            log_handle.write(f"{timestamp}{text}")
                            log_handle.flush()
                        if on_data:
                            on_data(text)
            finally:
                if log_handle:
                    log_handle.close()

        self._thread = threading.Thread(target=worker, daemon=True)
        self._thread.start()

    def write(self, data: str):
        if self.ser and self.ser.is_open:
            self.ser.write(data.encode("utf-8"))

    def stop(self):
        self.running = False
        if self._thread:
            self._thread.join(timeout=1.0)
        if self.ser and self.ser.is_open:
            self.ser.close()
