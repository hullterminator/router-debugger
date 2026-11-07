"""
Interactive Rich CLI for Router Debugging and Hardware Hacking Toolkit.
"""

import sys
import time
import argparse
from pathlib import Path
from typing import Optional

from rich.console import Console
from rich.table import Table
from rich.panel import Panel
from rich.text import Text
from rich.prompt import Prompt, Confirm

from router_debugger.hardware.pinout_guide import (
    get_hardware_safety_summary, UART_SAFETY_RULES, MULTIMETER_PROCEDURE, SPI_FLASH_SOIC8_PINOUT
)
from router_debugger.hardware.uart import (
    list_serial_ports, detect_baud_rate, interrupt_bootloader, SerialLogger
)
from router_debugger.network.tftp_server import TFTPServer
from router_debugger.network.scanner import detect_default_gateway, scan_router_ports
from router_debugger.network.ping_monitor import PingMonitor
from router_debugger.firmware.analyzer import scan_firmware_file
from router_debugger.troubleshooting.playbooks import PLAYBOOKS, list_playbooks

console = Console()

BANNER = """
[bold cyan]╔══════════════════════════════════════════════════════════════╗
║        [bold yellow]ROUTER HARDWARE HACKING & DEBUGGING TOOLKIT[/bold yellow]           ║
║   UART Console • Bootloader Interrupt • TFTP Unbrick • Recon  ║
╚══════════════════════════════════════════════════════════════╝[/bold cyan]
"""

def show_pinout_guide():
    console.print(Panel.fit("[bold red]CRITICAL HARDWARE SAFETY RULES[/bold red]", border_style="red"))
    for idx, rule in enumerate(UART_SAFETY_RULES, 1):
        console.print(f"[bold yellow]![/bold yellow] [bold white]{idx}.[/bold white] {rule}")

    console.print("\n[bold cyan]Step-by-Step Multimeter Pin Identification Procedure:[/bold cyan]")
    table = Table(title="UART Header Discovery Checklist", header_style="bold magenta")
    table.add_column("Step", style="cyan", width=6)
    table.add_column("Target Pin", style="bold green", width=14)
    table.add_column("DMM Setting", style="yellow", width=22)
    table.add_column("Power State", style="red", width=22)
    table.add_column("Instructions", style="white")

    for s in MULTIMETER_PROCEDURE:
        table.add_row(
            str(s["step"]),
            s["name"],
            s["mode"],
            s["power"],
            s["instructions"]
        )
    console.print(table)

    console.print("\n[bold cyan]SPI Flash (SOIC-8) Pinout & Flashrom Recovery:[/bold cyan]")
    flash_table = Table(header_style="bold blue")
    flash_table.add_column("Pin #", style="cyan", width=8)
    flash_table.add_column("Pin Name", style="bold yellow", width=16)
    flash_table.add_column("Function", style="white")
    for p in SPI_FLASH_SOIC8_PINOUT["pins"]:
        flash_table.add_row(str(p["pin"]), p["name"], p["description"])
    console.print(flash_table)

def handle_uart(args):
    ports = list_serial_ports()
    table = Table(title="Detected Serial Ports", header_style="bold cyan")
    table.add_column("Device / COM", style="bold green")
    table.add_column("Description", style="white")
    table.add_column("Hardware ID", style="dim")

    for p in ports:
        table.add_row(p["device"], p["description"], p["hwid"])
    console.print(table)

    if not ports or ports[0]["device"] == "N/A":
        console.print("[yellow]No active serial ports found. Connect your USB-UART adapter (CP2102/FT232/CH340).[/yellow]")
        return

    selected_port = args.port or ports[0]["device"]

    if args.detect_baud:
        console.print(f"[cyan]Scanning baud rates on [bold]{selected_port}[/bold]... Please power cycle the router.[/cyan]")
        res = detect_baud_rate(selected_port)
        b_table = Table(title=f"Baud Rate Probing on {selected_port}", header_style="bold magenta")
        b_table.add_column("Baud", style="bold yellow")
        b_table.add_column("Printable %", style="cyan")
        b_table.add_column("Keywords Detected", style="green")
        b_table.add_column("Confidence", style="bold white")
        b_table.add_column("Preview", style="dim")

        for r in res.get("results", []):
            if "error" in r:
                b_table.add_row(str(r["baud"]), "ERROR", r["error"], "0%", "")
            else:
                kws = ", ".join(r["keywords_found"]) if r["keywords_found"] else "None"
                b_table.add_row(
                    str(r["baud"]),
                    f"{r['printable_ratio']*100:.1f}%",
                    kws,
                    f"{r['confidence']}%",
                    repr(r["sample"][:40])
                )
        console.print(b_table)
        if res.get("best_baud"):
            console.print(f"[bold green]Best match baud rate detected: {res['best_baud']}[/bold green]")
        return

    if args.interrupt:
        console.print(f"[bold yellow]Ready to interrupt bootloader on {selected_port} ({args.baud} baud).[/bold yellow]")
        console.print("[cyan]Turn ON router power NOW![/cyan]")
        res = interrupt_bootloader(
            selected_port,
            baudrate=args.baud,
            trigger_sequence=args.trigger,
            callback=lambda text: console.print(text, end="")
        )
        if res["success"]:
            console.print("\n[bold green]>>> BOOTLOADER INTERRUPTED SUCCESSFULLY! Prompt detected. <<<[/bold green]")
        else:
            console.print("\n[bold red]Autoboot window passed or no prompt detected. Try again or change trigger sequence.[/bold red]")
        return

    # Default: Serial Terminal
    console.print(f"[bold green]Connecting to {selected_port} at {args.baud} baud... (Ctrl+C to exit)[/bold green]")
    try:
        logger = SerialLogger(selected_port, args.baud, args.log_file)
        logger.start(on_data=lambda t: console.print(t, end=""))
        while True:
            cmd = input()
            logger.write(cmd + "\n")
    except KeyboardInterrupt:
        console.print("\n[yellow]Serial session closed.[/yellow]")
    finally:
        if 'logger' in locals():
            logger.stop()

def handle_tftp(args):
    root = Path(args.dir or "./firmware_recovery").resolve()
    root.mkdir(parents=True, exist_ok=True)
    console.print(Panel(
        f"[bold green]Router Unbricking TFTP Server[/bold green]\n"
        f"Serving directory: [cyan]{root}[/cyan]\n"
        f"Bind address: [cyan]{args.host}:{args.port}[/cyan]\n"
        f"Put recovery firmware (e.g. [bold]firmware.bin[/bold] or [bold]openwrt.bin[/bold]) into this folder.",
        border_style="green"
    ))
    server = TFTPServer(
        root_dir=str(root),
        host=args.host,
        port=args.port,
        log_callback=lambda msg: console.print(f"[bold blue]{msg}[/bold blue]")
    )
    server.start()
    console.print("[yellow]Server is listening... Press Ctrl+C to terminate.[/yellow]")
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        server.stop()

def handle_scan(args):
    gw = args.ip or detect_default_gateway()
    console.print(f"[bold cyan]Scanning target router at: [yellow]{gw}[/yellow]...[/bold cyan]")
    open_ports = scan_router_ports(gw)

    if not open_ports:
        console.print(f"[red]No open management ports found on {gw}. Ensure router is connected via Ethernet.[/red]")
        return

    table = Table(title=f"Discovered Router Services on {gw}", header_style="bold green")
    table.add_column("Port", style="bold yellow", width=8)
    table.add_column("Status", style="green", width=10)
    table.add_column("Service Description", style="cyan", width=36)
    table.add_column("Banner / Greeting", style="white")

    for p in open_ports:
        table.add_row(str(p["port"]), p["status"], p["service"], p.get("banner", "")[:60])
    console.print(table)

def handle_ping(args):
    gw = args.ip or detect_default_gateway()
    console.print(f"[cyan]Monitoring ping and TTL on [bold]{gw}[/bold] for {args.duration}s...[/cyan]")
    console.print("[dim]Power-cycle router now. TTL=100 indicates Bootloader Recovery mode, TTL=64 indicates Linux.[/dim]\n")

    monitor = PingMonitor(gw, interval=args.interval)
    def on_status(s):
        if s["alive"]:
            color = "green" if s.get("ttl") == 100 else "cyan"
            console.print(f"[{color}][+] ONLINE | TTL={s.get('ttl')} | {s.get('latency_ms')}ms | Stage: {s.get('stage')}[/{color}]")
        else:
            console.print("[dim red][-] Waiting for response...[/dim red]")

    try:
        monitor.watch(duration_seconds=args.duration, on_status=on_status)
    except KeyboardInterrupt:
        monitor.stop()

def handle_firmware(args):
    fw_path = Path(args.file)
    if not fw_path.exists():
        console.print(f"[bold red]File not found: {fw_path}[/bold red]")
        return

    console.print(f"[cyan]Analyzing firmware binary: [bold]{fw_path.name}[/bold] ({fw_path.stat().st_size} bytes)...[/cyan]")
    res = scan_firmware_file(fw_path)

    chk_panel = (
        f"[bold]MD5:[/bold]    {res['checksums']['md5']}\n"
        f"[bold]SHA256:[/bold] {res['checksums']['sha256']}\n"
        f"[bold]CRC32:[/bold]  {res['checksums']['crc32']}"
    )
    console.print(Panel(chk_panel, title="Firmware Integrity Hashes", border_style="cyan"))

    if res.get("uboot_header"):
        u = res["uboot_header"]
        u_panel = (
            f"[bold green]Name:[/bold green]         {u.get('image_name')}\n"
            f"[bold green]OS / Arch:[/bold green]    {u.get('os')} / {u.get('arch')}\n"
            f"[bold green]Load Address:[/bold green] {u.get('load_address')}\n"
            f"[bold green]Entry Point:[/bold green]  {u.get('entry_point')}\n"
            f"[bold green]Payload Size:[/bold green] {u.get('payload_size')} bytes"
        )
        console.print(Panel(u_panel, title="U-Boot Legacy Image Header Detected", border_style="green"))

    if res.get("trx_header"):
        t = res["trx_header"]
        console.print(Panel(str(t), title="Broadcom TRX Header Detected", border_style="magenta"))

    if res.get("signatures"):
        table = Table(title="Detected Embedded Headers & Partitions", header_style="bold yellow")
        table.add_column("Offset (Hex)", style="bold cyan", width=14)
        table.add_column("Component", style="bold green", width=26)
        table.add_column("Type", style="yellow", width=18)
        table.add_column("Description", style="white")

        for sig in res["signatures"]:
            table.add_row(sig["hex_offset"], sig["name"], sig["type"], sig["description"])
        console.print(table)

    if res.get("embedded_env_vars"):
        console.print("\n[bold cyan]Found Bootloader / Kernel Environment Variables:[/bold cyan]")
        for env in res["embedded_env_vars"]:
            console.print(f"  [yellow]•[/yellow] [white]{env}[/white]")

def handle_troubleshoot():
    console.print("[bold cyan]Select a router issue playbook to get step-by-step unbricking instructions:[/bold cyan]\n")
    pb_list = list_playbooks()
    for idx, pb in enumerate(pb_list, 1):
        console.print(f"[bold yellow]{idx}.[/bold yellow] [bold white]{pb['title']}[/bold white]")

    choice = Prompt.ask("\nEnter issue number", choices=[str(i) for i in range(1, len(pb_list) + 1)])
    selected_id = pb_list[int(choice) - 1]["id"]
    pb_data = PLAYBOOKS[selected_id]

    console.print(f"\n[bold green]═══ {pb_data['title'].upper()} ═══[/bold green]")
    console.print("[bold red]Symptoms:[/bold red]")
    for s in pb_data["symptoms"]:
        console.print(f"  • {s}")
    console.print("\n[bold yellow]Common Root Causes:[/bold yellow]")
    for c in pb_data["root_causes"]:
        console.print(f"  • {c}")

    console.print("\n[bold cyan]Actionable Repair Steps:[/bold cyan]")
    for st in pb_data["steps"]:
        console.print(Panel(st["detail"], title=f"Step {st['step']}: {st['action']}", border_style="cyan"))

def interactive_menu():
    console.print(BANNER)
    while True:
        console.print("\n[bold cyan]Main Menu:[/bold cyan]")
        console.print("  [bold yellow]1[/bold yellow] - Hardware Pinout & Multimeter Safety Guide (UART, JTAG, SPI Flash)")
        console.print("  [bold yellow]2[/bold yellow] - UART Console / Auto-Baud Detection / Bootloader Interrupter")
        console.print("  [bold yellow]3[/bold yellow] - Router Unbrick TFTP Recovery Server")
        console.print("  [bold yellow]4[/bold yellow] - Network Gateway & Debug Port Scanner")
        console.print("  [bold yellow]5[/bold yellow] - Ping & TTL Bootloader Recovery Monitor")
        console.print("  [bold yellow]6[/bold yellow] - Firmware Header & Partition Analyzer")
        console.print("  [bold yellow]7[/bold yellow] - Step-by-Step Issue Troubleshooting Playbooks")
        console.print("  [bold yellow]8[/bold yellow] - Start Web Dashboard (FastAPI)")
        console.print("  [bold yellow]0[/bold yellow] - Exit")

        choice = Prompt.ask("Select an option", choices=["0", "1", "2", "3", "4", "5", "6", "7", "8"], default="1")
        if choice == "0":
            break
        elif choice == "1":
            show_pinout_guide()
        elif choice == "2":
            sub_parser = argparse.Namespace(
                port=None, baud=115200, detect_baud=False, interrupt=False, trigger="space", log_file=None
            )
            sub_choice = Prompt.ask("UART Action: [1] List Ports [2] Auto-Detect Baud [3] Interrupt Bootloader [4] Open Terminal", choices=["1", "2", "3", "4"], default="1")
            if sub_choice == "2":
                sub_parser.detect_baud = True
            elif sub_choice == "3":
                sub_parser.interrupt = True
            handle_uart(sub_parser)
        elif choice == "3":
            tftp_parser = argparse.Namespace(dir="./firmware_recovery", host="0.0.0.0", port=69)
            handle_tftp(tftp_parser)
        elif choice == "4":
            gw_ip = Prompt.ask("Router IP address", default=detect_default_gateway())
            scan_parser = argparse.Namespace(ip=gw_ip)
            handle_scan(scan_parser)
        elif choice == "5":
            gw_ip = Prompt.ask("Router IP address", default=detect_default_gateway())
            ping_parser = argparse.Namespace(ip=gw_ip, duration=20.0, interval=0.5)
            handle_ping(ping_parser)
        elif choice == "6":
            fw_file = Prompt.ask("Enter path to firmware binary (.bin, .trx, .img)")
            fw_parser = argparse.Namespace(file=fw_file)
            handle_firmware(fw_parser)
        elif choice == "7":
            handle_troubleshoot()
        elif choice == "8":
            start_web_server()

def start_web_server(host: str = "127.0.0.1", port: int = 8000):
    try:
        import uvicorn
        console.print(f"[bold green]Starting Web Dashboard at http://{host}:{port}[/bold green]")
        uvicorn.run("router_debugger.web.app:app", host=host, port=port, reload=False)
    except Exception as e:
        console.print(f"[bold red]Failed to start web server: {e}[/bold red]")

def main():
    parser = argparse.ArgumentParser(description="Router Hardware Hacking & Troubleshooting Toolkit")
    subparsers = parser.add_subparsers(dest="command")

    # Pinout
    subparsers.add_parser("pinout", help="Show hardware pinout safety rules and multimeter procedures")

    # UART
    uart_p = subparsers.add_parser("uart", help="UART Serial debugging and bootloader interrupt")
    uart_p.add_argument("--port", help="COM port (e.g. COM3 or /dev/ttyUSB0)")
    uart_p.add_argument("--baud", type=int, default=115200, help="Baud rate (default: 115200)")
    uart_p.add_argument("--detect-baud", action="store_true", help="Auto-probe and detect correct baud rate")
    uart_p.add_argument("--interrupt", action="store_true", help="Auto-spam bootloader break keys on power-up")
    uart_p.add_argument("--trigger", choices=["space", "enter", "ctrl_c", "tpl", "all"], default="space", help="Bootloader interrupt keystroke")
    uart_p.add_argument("--log-file", help="File to log serial console output")

    # TFTP
    tftp_p = subparsers.add_parser("tftp", help="Launch TFTP unbrick server")
    tftp_p.add_argument("--dir", default="./firmware_recovery", help="Directory containing recovery .bin files")
    tftp_p.add_argument("--host", default="0.0.0.0", help="Host IP to bind (default 0.0.0.0)")
    tftp_p.add_argument("--port", type=int, default=69, help="UDP port (default 69)")

    # Scan
    scan_p = subparsers.add_parser("scan", help="Scan router management & debug ports")
    scan_p.add_argument("--ip", help="Router IP (auto-detected if omitted)")

    # Ping
    ping_p = subparsers.add_parser("ping", help="Monitor ping & TTL for bootloader recovery detection")
    ping_p.add_argument("--ip", help="Router IP (auto-detected if omitted)")
    ping_p.add_argument("--duration", type=float, default=30.0, help="Duration in seconds")
    ping_p.add_argument("--interval", type=float, default=0.5, help="Ping interval in seconds")

    # Firmware
    fw_p = subparsers.add_parser("firmware", help="Analyze firmware binary headers and signatures")
    fw_p.add_argument("--file", required=True, help="Path to firmware file")

    # Troubleshoot
    subparsers.add_parser("troubleshoot", help="Interactive router issue diagnosis & repair playbooks")

    # Web
    web_p = subparsers.add_parser("web", help="Launch web dashboard")
    web_p.add_argument("--host", default="127.0.0.1", help="Host IP")
    web_p.add_argument("--port", type=int, default=8000, help="Port")

    if len(sys.argv) == 1:
        interactive_menu()
        return

    args = parser.parse_args()
    if args.command == "pinout":
        show_pinout_guide()
    elif args.command == "uart":
        handle_uart(args)
    elif args.command == "tftp":
        handle_tftp(args)
    elif args.command == "scan":
        handle_scan(args)
    elif args.command == "ping":
        handle_ping(args)
    elif args.command == "firmware":
        handle_firmware(args)
    elif args.command == "troubleshoot":
        handle_troubleshoot()
    elif args.command == "web":
        start_web_server(args.host, args.port)
    else:
        interactive_menu()

if __name__ == "__main__":
    main()
