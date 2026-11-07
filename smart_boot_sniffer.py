"""
Smart Adaptive Baud Sniffer & Live Boot Logger for COM11.
"""

import sys
import time
import string
from pathlib import Path

try:
    import serial
except ImportError:
    print("pyserial is required")
    sys.exit(1)

from router_debugger.hardware.uart import extract_technical_specs

PORT = "COM11"
CANDIDATE_BAUDS = [115200, 57600, 38400, 19200, 9600, 230400]
LOG_FILE = Path("boot_log_com11.txt").resolve()

def safe_print(text: str):
    try:
        sys.stdout.write(text)
        sys.stdout.flush()
    except Exception:
        sys.stdout.buffer.write(text.encode("utf-8", errors="replace"))
        sys.stdout.buffer.flush()

def is_printable_ascii(data: bytes, min_ratio: float = 0.65) -> bool:
    if not data:
        return False
    printable = sum(1 for b in data if (32 <= b <= 126) or b in (10, 13, 9))
    return (printable / len(data)) >= min_ratio

def main():
    # Set UTF-8 encoding with error replacement on stdout
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")

    print("=" * 65)
    print(f"[*] INITIALIZING SMART BOOT SNIFFER ON {PORT}...")
    print("=" * 65)

    current_baud = 115200
    try:
        ser = serial.Serial(PORT, current_baud, timeout=0.1)
        ser.reset_input_buffer()
    except Exception as e:
        print(f"[ERROR] Could not open {PORT}: {e}")
        return

    print(f"\n[READY] Port {PORT} is ACTIVE and LISTENING at {current_baud} baud.")
    print(">>> FLICK THE POWER SWITCH NOW! <<<\n")
    sys.stdout.flush()

    captured_chunks = []
    first_data_time = None
    last_data_time = None
    locked_baud = False

    # Truncate and open log file immediately
    with open(LOG_FILE, "w", encoding="utf-8") as f:
        f.write("=== UNIWAY UW-311VPW SERIAL BOOT LOG (COM11, 115200) ===\n\n")

    def append_log(txt: str):
        with open(LOG_FILE, "a", encoding="utf-8", errors="replace") as f:
            f.write(txt)
            f.flush()

    # Wait for first transmission (up to 45 seconds)
    wait_start = time.time()
    while time.time() - wait_start < 45:
        chunk = ser.read(128)
        if chunk:
            first_data_time = time.time()
            last_data_time = first_data_time
            # Test first chunk for baud correctness
            if is_printable_ascii(chunk):
                locked_baud = True
                print(f"[+] Clean ASCII stream confirmed at {current_baud} baud!")
                text = chunk.decode("latin-1", errors="replace")
                safe_print(text)
                append_log(text)
                captured_chunks.append(text)
                break
            else:
                print(f"[-] Data received at {current_baud} appears to be framing errors / garbage.")
                # Try candidate bauds
                found_match = False
                for b in CANDIDATE_BAUDS:
                    if b == current_baud:
                        continue
                    print(f"[*] Trying alternative baud rate: {b}...")
                    ser.baudrate = b
                    ser.reset_input_buffer()
                    time.sleep(0.3)
                    test_sample = ser.read(128)
                    if is_printable_ascii(test_sample):
                        current_baud = b
                        locked_baud = True
                        found_match = True
                        print(f"[+] SUCCESS: Locked into correct baud rate: {current_baud}!")
                        text = test_sample.decode("latin-1", errors="replace")
                        safe_print(text)
                        append_log(text)
                        captured_chunks.append(text)
                        break

                if found_match:
                    break
                else:
                    # Revert to 115200 and record raw
                    ser.baudrate = 115200
                    current_baud = 115200
                    text = chunk.decode("latin-1", errors="replace")
                    safe_print(text)
                    append_log(text)
                    captured_chunks.append(text)
                    break
        time.sleep(0.05)

    if not captured_chunks:
        print("[!] No serial activity detected after 45 seconds. Verify TX/RX wiring and router power.")
        ser.close()
        return

    # Continue capturing the boot stream until silent for 4.0 seconds (or max 60 seconds)
    print("\n[+] Streaming bootloader and kernel messages...")
    stream_start = time.time()
    while time.time() - stream_start < 60:
        chunk = ser.read(256)
        if chunk:
            last_data_time = time.time()
            text = chunk.decode("latin-1", errors="replace")
            safe_print(text)
            append_log(text)
            captured_chunks.append(text)
            sys.stdout.flush()
        else:
            # Check idle duration
            if last_data_time and (time.time() - last_data_time > 4.0):
                print("\n[i] Serial line became quiet for 4 seconds. Boot sequence complete or paused.")
                break
        time.sleep(0.02)

    ser.close()

    full_log = "".join(captured_chunks)
    with open(LOG_FILE, "w", encoding="utf-8") as f:
        f.write(full_log)

    print("\n" + "=" * 65)
    print(f"[*] CAPTURE COMPLETE! Raw log saved to: {LOG_FILE}")
    print("=" * 65)

    # Extract technical specs
    specs = extract_technical_specs(full_log)
    print("\n" + "─" * 50)
    print("       DETECTED ROUTER SPECIFICATIONS")
    print("─" * 50)
    print(f"  • Confirmed Baud Rate: {current_baud}")
    print(f"  • Bootloader:          {specs.get('bootloader') or 'Unknown'}")
    print(f"  • SoC / CPU Model:     {specs.get('soc_cpu') or 'Unknown'}")
    print(f"  • CPU Clock Speed:     {specs.get('cpu_clock') or 'Unknown'}")
    print(f"  • RAM / DRAM Memory:   {specs.get('ram_memory') or 'Unknown'}")
    print(f"  • Flash Storage IC:    {specs.get('flash_chip') or 'Unknown'}")
    print(f"  • Linux Kernel:        {specs.get('linux_kernel') or 'Unknown'}")
    print(f"  • MAC Address(es):     {', '.join(specs.get('mac_addresses', [])) or 'None'}")
    print(f"  • Boot Arguments:      {specs.get('bootargs') or 'Default'}")

    if specs.get("mtd_partitions"):
        print("\n  MTD Flash Partitions:")
        for m in specs["mtd_partitions"]:
            print(f"    - [{m['range']}] {m['name']} ({m['size']})")
    print("─" * 50)

if __name__ == "__main__":
    main()
