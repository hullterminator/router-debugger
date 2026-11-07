"""
Router Hardware Troubleshooting & Unbricking Playbooks.
Step-by-step interactive decision trees and remedies for common hardware & firmware failures.
"""

from typing import Dict, List, Any

PLAYBOOKS = {
    "boot_loop": {
        "title": "Boot Loop / Continuous Restart",
        "symptoms": [
            "LEDs flash and device resets every 10-30 seconds",
            "Network connection connects and disconnects repeatedly",
            "Kernel panic or watchdog timer reset"
        ],
        "root_causes": [
            "Corrupt JFFS2/UBI filesystem partition",
            "Bad NVRAM parameter causing kernel crash during initialization",
            "Incompatible firmware image flashed to flash memory"
        ],
        "steps": [
            {
                "step": 1,
                "action": "Connect UART Serial Console (TX, RX, GND).",
                "detail": "Set baud rate to 115200 (or use auto-baud detector). Watch the serial log to pinpoint where it crashes."
            },
            {
                "step": 2,
                "action": "Interrupt the Bootloader.",
                "detail": "Power cycle the router and run the bootloader interrupter to drop into U-Boot or CFE prompt."
            },
            {
                "step": 3,
                "action": "Reset Environment Variables / NVRAM.",
                "detail": "In U-Boot run:\n  env default -a\n  saveenv\n  reset\nIn CFE run:\n  nvram erase\n  reboot"
            },
            {
                "step": 4,
                "action": "Re-flash clean firmware via TFTP.",
                "detail": "Run the built-in TFTP recovery server and use `tftpboot` or router recovery web interface."
            }
        ]
    },
    "soft_brick": {
        "title": "Soft Brick / No Web GUI / Fails to Obtain IP",
        "symptoms": [
            "Power LED is solid or flashing, but no DHCP IP is handed out",
            "Web interface at 192.168.1.1 is unreachable",
            "Router seems unresponsive to reset button in normal mode"
        ],
        "root_causes": [
            "Bricked network daemon or corrupted config",
            "Failed OTA update",
            "OpenWrt failsafe mode triggered"
        ],
        "steps": [
            {
                "step": 1,
                "action": "Test OpenWrt / Vendor Failsafe Mode.",
                "detail": (
                    "Power on the router. As soon as the SYS/Power LED starts blinking rapidly (usually 2-3 seconds after power-on), "
                    "press the WPS or Reset button once. The LED will blink at 10Hz, indicating Failsafe mode. "
                    "Set your PC IP to 192.168.1.2 / 255.255.255.0 and telnet to 192.168.1.1 without password. "
                    "Run `mount_root` then `firstboot -y && reboot`."
                )
            },
            {
                "step": 2,
                "action": "Trigger Hardware TFTP Recovery Mode.",
                "detail": (
                    "Power off router. Hold the Reset button down with a pin. Power on while KEEPING the button held for 15-20 seconds. "
                    "Watch LEDs: Many routers (Asus, Netgear, TP-Link) will blink in a distinct pattern indicating TFTP recovery. "
                    "Ping 192.168.1.1 — if TTL=100, the bootloader is awaiting firmware."
                )
            },
            {
                "step": 3,
                "action": "Serve clean recovery firmware.",
                "detail": "Launch `router-debugger tftp --file <factory_firmware.bin>` and allow the router to download the recovery image."
            }
        ]
    },
    "hard_brick": {
        "title": "Hard Brick / Completely Dead / Corrupt Bootloader",
        "symptoms": [
            "No LEDs at all, or all LEDs permanently frozen solid on power-up",
            "Completely silent on UART (no serial data transmitted)",
            "No Ethernet link lights on connected PC"
        ],
        "root_causes": [
            "Bootloader (U-Boot/CFE) partition was erased or overwritten with invalid code",
            "Blown power regulation capacitor/buck converter",
            "Defective SPI Flash IC"
        ],
        "steps": [
            {
                "step": 1,
                "action": "Check Hardware Power Rails with Multimeter.",
                "detail": (
                    "Test barrel jack voltage (typically 12V DC). Probe voltage regulators on board: "
                    "Verify 5.0V, 3.3V (flash & I/O), 1.8V (DDR RAM), and 1.1V/1.2V (CPU core). "
                    "If rails are missing, replace faulty buck regulator or SMD capacitor."
                )
            },
            {
                "step": 2,
                "action": "Identify SPI Flash Chip.",
                "detail": "Locate 8-pin SOIC IC (e.g. Winbond 25Q64FVSIG, Macronix MX25L128). Check if it is 3.3V or 1.8V!"
            },
            {
                "step": 3,
                "action": "Connect External CH341A / Raspberry Pi SPI Programmer.",
                "detail": (
                    "Attach SOIC-8 test clip to the flash chip (Pin 1 matches dot on chip). Router must be POWERED OFF. "
                    "Read current contents twice with flashrom:\n"
                    "  flashrom -p ch341a_spi -r backup1.bin\n"
                    "  flashrom -p ch341a_spi -r backup2.bin\n"
                    "Confirm both checksums match before touching anything!"
                )
            },
            {
                "step": 4,
                "action": "Preserve ART (Calibration) and Write Bootloader.",
                "detail": (
                    "CRITICAL: The last 64KB of flash contains ART (Atheros Radio Test) / EEPROM with unique MAC address and Wi-Fi calibration. "
                    "Never erase without extracting this block! Splicing fresh U-Boot + clean firmware + original ART, then write:\n"
                    "  flashrom -p ch341a_spi -w restored_full.bin"
                )
            }
        ]
    },
    "serial_garbage": {
        "title": "Serial Console Outputs Scrambled / Garbage Characters",
        "symptoms": [
            "Characters appear as gibberish (e.g. ^X)",
            "Serial connects but nothing is human readable"
        ],
        "root_causes": [
            "Incorrect baud rate",
            "Floating ground (missing GND connection between router and adapter)",
            "Voltage level mismatch (5V vs 3.3V)"
        ],
        "steps": [
            {
                "step": 1,
                "action": "Run Baud Rate Auto-Detector.",
                "detail": "Use `router-debugger uart --detect-baud` to sample across 115200, 57600, 38400, 19200, 9600, 230400."
            },
            {
                "step": 2,
                "action": "Verify Common Ground (GND).",
                "detail": "Ensure GND of your USB-UART adapter is securely bonded to the router GND pin or shield. A loose ground is the #1 cause of serial noise."
            },
            {
                "step": 3,
                "action": "Verify 3.3V TTL Level.",
                "detail": "Ensure your USB adapter jumper is set to 3.3V (not 5V). Standard RS232 converters (+/- 12V) invert signal polarity and will destroy router GPIOs."
            }
        ]
    },
    "root_shell_bypass": {
        "title": "Root Shell Access via Bootloader (Bypass Locked Console)",
        "symptoms": [
            "Serial console presents a login prompt with unknown credentials",
            "Web interface password is unknown and reset is not desired"
        ],
        "root_causes": [
            "Vendor locked debug console"
        ],
        "steps": [
            {
                "step": 1,
                "action": "Interrupt U-Boot Bootloader.",
                "detail": "Reboot router and trigger interrupt (`router-debugger uart --interrupt`). Drop to `=>` prompt."
            },
            {
                "step": 2,
                "action": "Inspect current boot arguments.",
                "detail": "Run:\n  printenv bootargs\n  printenv bootcmd"
            },
            {
                "step": 3,
                "action": "Inject init=/bin/sh into bootargs.",
                "detail": (
                    "Append single-user init hook:\n"
                    "  setenv bootargs console=ttyS0,115200 root=/dev/mtdblock2 rootfstype=squashfs init=/bin/sh\n"
                    "  boot"
                )
            },
            {
                "step": 4,
                "action": "Reset root password or extract credentials.",
                "detail": (
                    "Once at `#` root shell:\n"
                    "  mount -o remount,rw /\n"
                    "  passwd -d root  (clears root password)\n"
                    "  cat /etc/shadow"
                )
            }
        ]
    }
}

def list_playbooks() -> List[Dict[str, str]]:
    """Returns list of available troubleshooting guides."""
    return [{"id": k, "title": v["title"]} for k, v in PLAYBOOKS.items()]

def get_playbook(playbook_id: str) -> Dict[str, Any]:
    """Retrieves a specific playbook by ID."""
    return PLAYBOOKS.get(playbook_id, {})
