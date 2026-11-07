"""
Router Firmware Analyzer & Signature Scanner.
Detects U-Boot uImage, TRX, SquashFS, JFFS2, CramFS, Device Tree, and U-Boot env strings.
"""

import os
import struct
import hashlib
import binascii
from pathlib import Path
from typing import Dict, List, Optional, Any

# Magic Byte Signatures
MAGIC_SIGNATURES = [
    {
        "name": "U-Boot uImage Header",
        "magic": b"\x27\x05\x19\x56",
        "type": "boot_image",
        "description": "Standard U-Boot Legacy Image Header (Kernel / Ramdisk)"
    },
    {
        "name": "TRX Header (Broadcom)",
        "magic": b"HDR0",
        "type": "firmware_container",
        "description": "Broadcom TRX container (Netgear, Linksys, Asus, DD-WRT)"
    },
    {
        "name": "SquashFS (Little-Endian)",
        "magic": b"sqsh",
        "type": "filesystem",
        "description": "SquashFS Compressed Read-Only Root Filesystem"
    },
    {
        "name": "SquashFS (Big-Endian)",
        "magic": b"hsqs",
        "type": "filesystem",
        "description": "SquashFS Big-Endian (Common on MIPS/Atheros routers)"
    },
    {
        "name": "Device Tree Blob (DTB)",
        "magic": b"\xd0\x0d\xfe\xed",
        "type": "hardware_tree",
        "description": "Flattened Device Tree Blob"
    },
    {
        "name": "CramFS Filesystem",
        "magic": b"\x28\xcd\x3d\x45",
        "type": "filesystem",
        "description": "CramFS Compressed ROM Filesystem"
    },
    {
        "name": "JFFS2 Filesystem",
        "magic": b"\x85\x19",
        "type": "filesystem",
        "description": "Journaling Flash File System v2"
    },
    {
        "name": "LZMA Compressed Stream",
        "magic": b"\x5d\x00\x00",
        "type": "compression",
        "description": "LZMA Compressed Block"
    },
    {
        "name": "GZIP Compressed Stream",
        "magic": b"\x1f\x8b\x08",
        "type": "compression",
        "description": "GZIP Compressed Kernel / Ramdisk"
    }
]

UBOOT_OS_MAP = {
    1: "OpenBSD", 2: "NetBSD", 3: "FreeBSD", 4: "4.4BSD",
    5: "Linux", 6: "SVR4", 7: "Esix", 8: "Solaris",
    9: "Irix", 10: "SCO", 11: "Dell", 12: "NCR",
    15: "VxWorks", 16: "QNX", 17: "U-Boot", 18: "RTEMS",
    19: "ARTOS", 20: "Unity OS"
}

UBOOT_ARCH_MAP = {
    1: "Alpha", 2: "ARM", 3: "I386", 4: "IA64",
    5: "MIPS", 6: "MIPS64", 7: "PowerPC", 8: "IBM S390",
    9: "SuperH", 10: "SPARC", 11: "SPARC64", 12: "M68K",
    14: "MicroBlaze", 21: "ARM64", 22: "RISC-V"
}

def calculate_checksums(file_path: Path) -> Dict[str, str]:
    """Calculate MD5, SHA-1, SHA-256, and CRC32."""
    md5 = hashlib.md5()
    sha1 = hashlib.sha1()
    sha256 = hashlib.sha256()
    crc = 0

    with open(file_path, "rb") as f:
        while chunk := f.read(65536):
            md5.update(chunk)
            sha1.update(chunk)
            sha256.update(chunk)
            crc = binascii.crc32(chunk, crc)

    return {
        "md5": md5.hexdigest(),
        "sha1": sha1.hexdigest(),
        "sha256": sha256.hexdigest(),
        "crc32": f"{crc & 0xFFFFFFFF:08x}"
    }

def parse_uboot_image(header_bytes: bytes) -> Dict[str, Any]:
    """Parse 64-byte U-Boot legacy header."""
    if len(header_bytes) < 64:
        return {}
    magic, hcrc, time_stamp, size, load, ep, dcrc, os_id, arch_id, type_id, comp_id = struct.unpack(
        "!IIIIIIIBBBB", header_bytes[:32]
    )
    name = header_bytes[32:64].split(b"\x00")[0].decode("latin-1", errors="replace")
    return {
        "image_name": name,
        "payload_size": size,
        "load_address": f"0x{load:08X}",
        "entry_point": f"0x{ep:08X}",
        "os": UBOOT_OS_MAP.get(os_id, f"Unknown ({os_id})"),
        "arch": UBOOT_ARCH_MAP.get(arch_id, f"Unknown ({arch_id})"),
        "header_crc": f"0x{hcrc:08X}",
        "data_crc": f"0x{dcrc:08X}"
    }

def parse_trx_header(header_bytes: bytes) -> Dict[str, Any]:
    """Parse Broadcom TRX header."""
    if len(header_bytes) < 28 or header_bytes[:4] != b"HDR0":
        return {}
    magic, length, crc32, flags_version, offset1, offset2, offset3 = struct.unpack(
        "<4sIIIIII", header_bytes[:28]
    )
    return {
        "magic": "HDR0",
        "length": length,
        "crc32": f"0x{crc32:08X}",
        "version": flags_version & 0xFFFF,
        "partitions": {
            "kernel_offset": offset1,
            "rootfs_offset": offset2,
            "extra_offset": offset3
        }
    }

def scan_firmware_file(file_path: Path, max_scan_bytes: int = 64 * 1024 * 1024) -> Dict[str, Any]:
    """Scans a firmware binary to identify partitions, filesystem headers, and embedded parameters."""
    file_path = Path(file_path).resolve()
    if not file_path.exists():
        raise FileNotFoundError(f"Firmware file not found: {file_path}")

    file_size = file_path.stat().st_size
    checksums = calculate_checksums(file_path)

    signatures_found = []
    uboot_info = None
    trx_info = None

    with open(file_path, "rb") as f:
        data = f.read(min(file_size, max_scan_bytes))

        # Check for TRX at offset 0
        if data.startswith(b"HDR0"):
            trx_info = parse_trx_header(data[:28])

        # Scan for signatures across file
        for sig in MAGIC_SIGNATURES:
            needle = sig["magic"]
            offset = 0
            while True:
                found_idx = data.find(needle, offset)
                if found_idx == -1:
                    break
                
                detail = {"offset": found_idx, "hex_offset": f"0x{found_idx:08X}", **sig}
                detail.pop("magic", None)

                # Special parse for U-Boot image header
                if needle == b"\x27\x05\x19\x56" and found_idx + 64 <= len(data):
                    u_parsed = parse_uboot_image(data[found_idx:found_idx+64])
                    detail["uboot_details"] = u_parsed
                    if not uboot_info:
                        uboot_info = u_parsed

                signatures_found.append(detail)
                offset = found_idx + len(needle)
                if len(signatures_found) > 100:  # limit noise
                    break

        # Scan for U-Boot bootargs / environment strings
        env_strings = []
        for kw in [b"bootcmd=", b"bootargs=", b"ipaddr=", b"serverip=", b"ethaddr=", b"board="]:
            idx = data.find(kw)
            if idx != -1:
                # Read null terminated string
                end = data.find(b"\x00", idx)
                if end != -1:
                    env_str = data[idx:end].decode("latin-1", errors="replace")
                    env_strings.append(env_str)

    signatures_found.sort(key=lambda x: x["offset"])

    return {
        "filename": file_path.name,
        "file_size": file_size,
        "checksums": checksums,
        "signatures": signatures_found,
        "uboot_header": uboot_info,
        "trx_header": trx_info,
        "embedded_env_vars": env_strings
    }
