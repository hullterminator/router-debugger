"""
Hardware Pinout Guide & Multimeter Safety Procedures for Router Hacking.
"""

from typing import Dict, List, Any

UART_SAFETY_RULES = [
    "NEVER connect VCC (3.3V or 5V) from your USB-UART adapter if the router is powered via AC/DC adapter! Routers already have their own power rail. Connecting external VCC can fry the SoC.",
    "Only 3 connections are needed: GND (Router) -> GND (Adapter), TX (Router) -> RX (Adapter), RX (Router) -> TX (Adapter).",
    "Verify logic level: Most modern routers use 3.3V TTL logic. Never use standard 5V RS232 (which swings to +/- 12V and will instantly destroy router GPIOs) or 5V TTL without level shifting.",
    "Always check with a digital multimeter (DMM) before attaching any serial wires."
]

MULTIMETER_PROCEDURE = [
    {
        "step": 1,
        "name": "Identify Ground (GND)",
        "mode": "Continuity / Resistance mode (beep mode)",
        "power": "Router POWERED OFF (Unplugged from wall)",
        "instructions": (
            "Place one multimeter probe on a known ground (the metal shielding can, the outer shield of an Ethernet port, "
            "or antenna ground screw). Probe the 4 UART test header pins. The pin that beeps with near 0 ohms resistance is GND."
        )
    },
    {
        "step": 2,
        "name": "Identify VCC (Power)",
        "mode": "DC Voltage mode (20V DC range)",
        "power": "Router POWERED ON",
        "instructions": (
            "Keep black probe on the verified GND. Power on the router and touch each of the remaining 3 pins. "
            "The pin that shows a steady +3.3V (or +5.0V / +1.8V) immediately upon power-up and NEVER fluctuates is VCC. "
            "DO NOT connect to this pin!"
        )
    },
    {
        "step": 3,
        "name": "Identify TX (Router Transmit)",
        "mode": "DC Voltage mode (20V DC range)",
        "power": "Router POWERED ON / Rebooting",
        "instructions": (
            "Black probe on GND. Monitor the remaining two pins while power-cycling the router. "
            "The TX pin will typically idle at ~3.3V, but during boot it will visibly fluctuate (e.g. 2.7V - 3.2V) as data packets "
            "stream out over the serial line. This is the Router's TX -> connect to Adapter's RX."
        )
    },
    {
        "step": 4,
        "name": "Identify RX (Router Receive)",
        "mode": "DC Voltage mode (20V DC range)",
        "power": "Router POWERED ON",
        "instructions": (
            "The last remaining pin is RX. It typically floats around 0V or stays at 3.3V high-impedance without fluctuations. "
            "This is the Router's RX -> connect to Adapter's TX."
        )
    }
]

COMMON_ROUTER_BAUD_RATES = [
    115200,  # Most common (Broadcom, MediaTek/Ralink, Qualcomm/Atheros, Realtek)
    57600,   # Very common on older Ralink, MediaTek, and Linksys/Netgear
    38400,   # Older routers / DSL modems
    9600,    # Industrial / legacy bootloaders
    19200,   # Rare
    230400   # Fast bootloaders
]

SPI_FLASH_SOIC8_PINOUT = {
    "description": "Standard 8-pin SPI NOR Flash (Winbond 25Qxx, Macronix MX25Lxx, GigaDevice GD25Qxx) used for firmware storage.",
    "pins": [
        {"pin": 1, "name": "/CS", "description": "Chip Select (Active Low)"},
        {"pin": 2, "name": "SO / MISO", "description": "Serial Data Output"},
        {"pin": 3, "name": "/WP", "description": "Write Protect (tie high for write)"},
        {"pin": 4, "name": "GND", "description": "Ground"},
        {"pin": 5, "name": "SI / MOSI", "description": "Serial Data Input"},
        {"pin": 6, "name": "SCK", "description": "Serial Clock"},
        {"pin": 7, "name": "/HOLD", "description": "Hold / Reset (tie high)"},
        {"pin": 8, "name": "VCC", "description": "Supply Voltage (typically 3.3V or 1.8V!)"}
    ],
    "ch341a_recovery_tips": [
        "Check flash chip voltage marking before clipping! 25Q64FVSIG is 3.3V, but 25Q64FW is 1.8V and needs a 1.8V adapter or it will burn out.",
        "When using SOIC8 test clip directly on motherboard without desoldering, ensure router is UNPLUGGED. The CH341A provides 3.3V. If the SoC draws too much current, desolder pin 8 (VCC) or the whole chip."
    ]
}

def get_hardware_safety_summary() -> Dict[str, Any]:
    return {
        "rules": UART_SAFETY_RULES,
        "procedure": MULTIMETER_PROCEDURE,
        "common_baud_rates": COMMON_ROUTER_BAUD_RATES,
        "spi_flash": SPI_FLASH_SOIC8_PINOUT
    }
