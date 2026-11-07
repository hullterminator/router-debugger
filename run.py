"""
Main entry point for running Router Debugger.
Usage:
  python run.py                   # Launches interactive CLI menu
  python run.py pinout            # Shows hardware pinout & multimeter test checklist
  python run.py uart              # Opens UART serial console / auto-baud detector
  python run.py scan              # Scans router gateway management ports
  python run.py tftp              # Starts unbricking TFTP server
  python run.py ping              # Monitors router power-cycle & TTL bootloader recovery
  python run.py firmware --file <path> # Inspects firmware binary headers
  python run.py troubleshoot      # Step-by-step router unbrick playbooks
  python run.py web               # Launches local web dashboard on http://127.0.0.1:8000
"""

import sys
from router_debugger.cli import main

if __name__ == "__main__":
    main()
