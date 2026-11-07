# Router Hardware Debugging & Hacking Toolkit

A specialized Python toolkit and interactive console designed for **hardware hacking, reverse engineering, and unbricking/fixing embedded routers and IoT devices**.

---

## ⚡ Features

1. **Hardware Pinout & Safety Guide**
   - Step-by-step digital multimeter (DMM) procedures to safely identify `GND`, `VCC`, `TX`, and `RX` pins on unpopulated UART headers.
   - Prevents SoC burnout (VCC safety warning and 3.3V logic verification).
   - Standard SPI Flash 8-pin (SOIC-8 / SOIC-16) pinout guide for CH341A external flasher recovery.

2. **UART Console & Bootloader Interrupter**
   - COM port enumeration.
   - **Auto-Baud Detection**: Samples serial traffic and evaluates ASCII printability and bootloader signatures across `115200`, `57600`, `38400`, `19200`, `9600`, etc.
   - **Autoboot Interrupter**: Continuously streams break sequences (Space, Enter, `ctrl+c`, `tpl`) during power-on to break into U-Boot/CFE interactive prompts (`=>` or `CFE>`).
   - Live serial terminal with timestamped logging.

3. **Embedded RFC 1350 TFTP Server**
   - Zero-dependency pure Python TFTP server for unbricking and restoring firmware.
   - Serves recovery binaries (e.g. `firmware.bin`, `openwrt.bin`, `tp_recovery.bin`) to router bootloaders on port 69.

4. **Network Recon & Bootloader Recovery Monitor**
   - Default gateway auto-detection.
   - Concurrent port scanner for router debug and administration ports (Telnet 23/2323, SSH 22, HTTP 80/8080, TR-069 7547, ADB 5555, etc.).
   - **TTL Recovery Monitor**: Pings target IP during reboot to detect U-Boot recovery mode (`TTL=100`) vs. Linux kernel (`TTL=64`).

5. **Firmware Analyzer & Partition Scanner**
   - Identifies Broadcom `TRX` headers (`HDR0`), U-Boot legacy `uImage` headers, `SquashFS`, `JFFS2`, `CramFS`, `LZMA`, and Device Tree Blobs.
   - Extracts embedded U-Boot environment variables (`bootargs=`, `bootcmd=`, `ipaddr=`).
   - Calculates MD5, SHA-256, and CRC32 checksums.

6. **Interactive Unbricking Playbooks**
   - Step-by-step diagnostic trees for:
     - Boot loops & continuous kernel panics
     - Soft bricks (no DHCP / unreachable web GUI / OpenWrt failsafe)
     - Hard bricks (dead bootloader / CH341A SPI flashrom restore)
     - Scrambled serial garbage (baud mismatch, floating ground)
     - Root console password bypass via `init=/bin/sh`

7. **Web Dashboard (FastAPI)**
   - Local web dashboard accessible via browser (`http://127.0.0.1:8000`).

---

## 🛠️ Project Structure

```
router-debugger/
├── pyproject.toml              # Project dependencies and script entrypoint
├── requirements.txt            # Python requirements (pyserial, rich, fastapi, uvicorn, pytest)
├── README.md                   # Complete documentation and tutorials
├── run.py                      # Main entrypoint script
├── router_debugger/
│   ├── __init__.py
│   ├── cli.py                  # Rich interactive terminal interface
│   ├── hardware/
│   │   ├── __init__.py
│   │   ├── pinout_guide.py     # Multimeter & pinout identification logic
│   │   └── uart.py             # Serial terminal, auto-baud & bootloader interrupter
│   ├── network/
│   │   ├── __init__.py
│   │   ├── scanner.py          # Port scanner & gateway auto-detector
│   │   ├── ping_monitor.py     # Ping & TTL recovery mode monitor
│   │   └── tftp_server.py      # RFC 1350 TFTP recovery server
│   ├── firmware/
│   │   ├── __init__.py
│   │   └── analyzer.py         # Firmware header & partition magic byte scanner
│   ├── troubleshooting/
│   │   ├── __init__.py
│   │   └── playbooks.py        # Repair decision trees & step-by-step guides
│   └── web/
│       ├── __init__.py
│       └── app.py              # FastAPI web dashboard
└── tests/
    ├── test_firmware.py
    ├── test_playbooks.py
    └── test_tftp.py
```

---

## 🚀 Quickstart

### 1. Activate Environment

```powershell
cd C:\Users\ramakant\.gemini\antigravity\scratch\router-debugger
.\.venv\Scripts\Activate.ps1
```

### 2. Launch the Interactive CLI Menu

```bash
python run.py
```

### 3. Run Dedicated Tools

#### Hardware Pinout & Safety Guide
```bash
python run.py pinout
```

#### Scan for Connected USB-UART Adapters & COM Ports
```bash
python run.py uart
```

#### Auto-Detect Serial Baud Rate
```bash
python run.py uart --port COM3 --detect-baud
```

#### Interrupt Bootloader on Power-Up (Drop into U-Boot / CFE Shell)
```bash
python run.py uart --port COM3 --interrupt --trigger space
```

#### Launch TFTP Unbricking Server
```bash
python run.py tftp --dir ./firmware_recovery --port 69
```

#### Scan Router Management & Debug Ports
```bash
python run.py scan --ip 192.168.1.1
```

#### Monitor Power-Cycle & Detect Recovery Mode (TTL=100)
```bash
python run.py ping --ip 192.168.1.1 --duration 30
```

#### Inspect Firmware Binary Headers & Partitions
```bash
python run.py firmware --file path/to/firmware.bin
```

#### Interactive Issue Troubleshooting Playbooks
```bash
python run.py troubleshoot
```

#### Launch Web Dashboard
```bash
python run.py web --port 8000
```
Open [http://127.0.0.1:8000](http://127.0.0.1:8000) in your browser.

---

## 🧪 Running Tests

```bash
pytest tests
```
