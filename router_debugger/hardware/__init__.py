"""Hardware hacking modules for router debugging."""
from .pinout_guide import get_hardware_safety_summary, MULTIMETER_PROCEDURE, UART_SAFETY_RULES, SPI_FLASH_SOIC8_PINOUT
from .uart import list_serial_ports, detect_baud_rate, interrupt_bootloader, SerialLogger

__all__ = [
    "get_hardware_safety_summary",
    "MULTIMETER_PROCEDURE",
    "UART_SAFETY_RULES",
    "SPI_FLASH_SOIC8_PINOUT",
    "list_serial_ports",
    "detect_baud_rate",
    "interrupt_bootloader",
    "SerialLogger"
]
