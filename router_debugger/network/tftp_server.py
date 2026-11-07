"""
Pure Python TFTP Server for Router Unbricking and Firmware Recovery.
Implements RFC 1350 standard TFTP protocol (RRQ, WRQ, DATA, ACK, ERROR).
Zero external dependencies required.
"""

import os
import socket
import struct
import threading
import time
from pathlib import Path
from typing import Optional, Callable, Dict, Any

# TFTP OpCodes
OP_RRQ = 1    # Read request
OP_WRQ = 2    # Write request
OP_DATA = 3   # Data packet
OP_ACK = 4    # Acknowledgment
OP_ERROR = 5  # Error code

BLOCK_SIZE = 512

class TFTPServer:
    """
    Lightweight TFTP Server specifically designed for router unbricking
    (e.g., serving openwrt/factory .bin to U-Boot or CFE during recovery mode).
    """
    def __init__(
        self,
        root_dir: str,
        host: str = "0.0.0.0",
        port: int = 69,
        log_callback: Optional[Callable[[str], None]] = None
    ):
        self.root_dir = Path(root_dir).resolve()
        self.host = host
        self.port = port
        self.log_callback = log_callback
        self.running = False
        self.sock: Optional[socket.socket] = None
        self._server_thread: Optional[threading.Thread] = None
        self.stats = {
            "transfers_completed": 0,
            "bytes_sent": 0,
            "bytes_received": 0,
            "errors": 0
        }

    def _log(self, msg: str):
        if self.log_callback:
            self.log_callback(f"[TFTP] {msg}")
        else:
            print(f"[TFTP] {msg}")

    def start(self):
        """Starts the TFTP listener in a background thread."""
        self.root_dir.mkdir(parents=True, exist_ok=True)
        self.sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self.sock.bind((self.host, self.port))
        self.sock.settimeout(1.0)
        self.running = True

        def run_loop():
            self._log(f"Server started on {self.host}:{self.port}, serving: {self.root_dir}")
            while self.running:
                try:
                    data, client_addr = self.sock.recvfrom(2048)
                    if not data:
                        continue
                    # Handle each connection in a new thread
                    handler = threading.Thread(
                        target=self._handle_request,
                        args=(data, client_addr),
                        daemon=True
                    )
                    handler.start()
                except socket.timeout:
                    continue
                except Exception as e:
                    if self.running:
                        self._log(f"Listener error: {e}")
                        self.stats["errors"] += 1

        self._server_thread = threading.Thread(target=run_loop, daemon=True)
        self._server_thread.start()

    def _handle_request(self, packet: bytes, client_addr: tuple):
        if len(packet) < 4:
            return

        opcode = struct.unpack("!H", packet[:2])[0]
        # Split null-terminated filename and mode
        try:
            parts = packet[2:].split(b"\x00")
            filename = parts[0].decode("ascii", errors="replace")
            mode = parts[1].decode("ascii", errors="replace").lower() if len(parts) > 1 else "octet"
        except Exception:
            return

        worker_sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        worker_sock.settimeout(3.0)

        # Sanitize filename (prevent directory traversal)
        clean_name = os.path.basename(filename)
        target_path = self.root_dir / clean_name

        try:
            if opcode == OP_RRQ:
                self._handle_rrq(worker_sock, client_addr, target_path, clean_name)
            elif opcode == OP_WRQ:
                self._handle_wrq(worker_sock, client_addr, target_path, clean_name)
        finally:
            worker_sock.close()

    def _handle_rrq(self, sock: socket.socket, client_addr: tuple, file_path: Path, filename: str):
        self._log(f"Client {client_addr[0]}:{client_addr[1]} requested download: {filename}")
        
        # If the requested file is not found, check if there's any fallback file in root_dir
        if not file_path.exists():
            # Check if any .bin or recovery file exists
            bin_files = list(self.root_dir.glob("*.bin"))
            if bin_files:
                self._log(f"File '{filename}' not found, falling back to: {bin_files[0].name}")
                file_path = bin_files[0]
            else:
                self._log(f"File not found: {filename}")
                self._send_error(sock, client_addr, 1, f"File {filename} not found")
                self.stats["errors"] += 1
                return

        file_size = file_path.stat().st_size
        block_num = 1
        bytes_transferred = 0

        with open(file_path, "rb") as f:
            while True:
                chunk = f.read(BLOCK_SIZE)
                data_packet = struct.pack("!HH", OP_DATA, block_num) + chunk

                # Send packet and wait for ACK with retries
                acked = False
                for attempt in range(5):
                    sock.sendto(data_packet, client_addr)
                    try:
                        resp, _ = sock.recvfrom(516)
                        if len(resp) >= 4:
                            resp_op, resp_block = struct.unpack("!HH", resp[:4])
                            if resp_op == OP_ACK and resp_block == block_num:
                                acked = True
                                break
                    except socket.timeout:
                        continue

                if not acked:
                    self._log(f"Transfer failed: Timeout waiting for ACK on block {block_num}")
                    self.stats["errors"] += 1
                    return

                bytes_transferred += len(chunk)
                block_num = (block_num + 1) & 0xFFFF

                if len(chunk) < BLOCK_SIZE:
                    # Final block transferred
                    break

        self.stats["transfers_completed"] += 1
        self.stats["bytes_sent"] += bytes_transferred
        self._log(f"SUCCESS: Completed transfer of {file_path.name} ({bytes_transferred} bytes) to {client_addr[0]}")

    def _handle_wrq(self, sock: socket.socket, client_addr: tuple, file_path: Path, filename: str):
        self._log(f"Client {client_addr[0]}:{client_addr[1]} uploading file: {filename}")
        # Send initial ACK for block 0
        sock.sendto(struct.pack("!HH", OP_ACK, 0), client_addr)
        expected_block = 1
        bytes_received = 0

        with open(file_path, "wb") as f:
            while True:
                try:
                    data, _ = sock.recvfrom(516)
                    if len(data) < 4:
                        continue
                    opcode, block_num = struct.unpack("!HH", data[:4])
                    if opcode == OP_DATA and block_num == expected_block:
                        payload = data[4:]
                        f.write(payload)
                        bytes_received += len(payload)
                        # Send ACK
                        sock.sendto(struct.pack("!HH", OP_ACK, block_num), client_addr)
                        expected_block = (expected_block + 1) & 0xFFFF
                        if len(payload) < BLOCK_SIZE:
                            break
                except socket.timeout:
                    self._log("Upload timed out")
                    self.stats["errors"] += 1
                    return

        self.stats["transfers_completed"] += 1
        self.stats["bytes_received"] += bytes_received
        self._log(f"Upload complete: {filename} ({bytes_received} bytes)")

    def _send_error(self, sock: socket.socket, client_addr: tuple, err_code: int, err_msg: str):
        payload = struct.pack("!HH", OP_ERROR, err_code) + err_msg.encode("ascii") + b"\x00"
        try:
            sock.sendto(payload, client_addr)
        except Exception:
            pass

    def stop(self):
        self.running = False
        if self.sock:
            try:
                self.sock.close()
            except Exception:
                pass
        self._log("Server stopped.")
