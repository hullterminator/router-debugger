import struct
import tempfile
from pathlib import Path
import pytest
from router_debugger.firmware.analyzer import scan_firmware_file, parse_uboot_image, parse_trx_header

def test_uboot_header_parser():
    # Construct a synthetic 64-byte U-Boot header
    # magic: 0x27051956, hcrc: 0x12345678, time: 0, size: 1024, load: 0x80060000, ep: 0x80060000
    # dcrc: 0x87654321, os: 5 (Linux), arch: 5 (MIPS), type: 2, comp: 3
    magic = 0x27051956
    hcrc = 0x12345678
    time_stamp = 0
    size = 1024
    load = 0x80060000
    ep = 0x80060000
    dcrc = 0x87654321
    os_id = 5
    arch_id = 5
    type_id = 2
    comp_id = 3
    name = b"OpenWrt Kernel\x00" + (b"\x00" * 17)

    raw_header = struct.pack("!IIIIIIIBBBB", magic, hcrc, time_stamp, size, load, ep, dcrc, os_id, arch_id, type_id, comp_id) + name
    assert len(raw_header) == 64

    parsed = parse_uboot_image(raw_header)
    assert parsed["image_name"] == "OpenWrt Kernel"
    assert parsed["os"] == "Linux"
    assert parsed["arch"] == "MIPS"
    assert parsed["payload_size"] == 1024
    assert parsed["load_address"] == "0x80060000"

def test_trx_header_parser():
    # TRX: HDR0 + len (28) + crc32 + flags_version + 3 offsets
    magic = b"HDR0"
    length = 28
    crc32 = 0xAABBCCDD
    flags_ver = 1
    o1 = 28
    o2 = 1000
    o3 = 2000
    raw_trx = struct.pack("<4sIIIIII", magic, length, crc32, flags_ver, o1, o2, o3)
    parsed = parse_trx_header(raw_trx)
    assert parsed["magic"] == "HDR0"
    assert parsed["partitions"]["kernel_offset"] == 28

def test_scan_firmware_file(tmp_path):
    fw_file = tmp_path / "test_fw.bin"
    # Create file with squashfs magic
    fw_content = b"RANDOMBOOTLOADER" + b"sqsh" + b"\x00" * 100 + b"bootargs=console=ttyS0,115200\x00"
    fw_file.write_bytes(fw_content)

    res = scan_firmware_file(fw_file)
    assert res["file_size"] == len(fw_content)
    assert any(sig["name"] == "SquashFS (Little-Endian)" for sig in res["signatures"])
    assert any("bootargs=" in env for env in res["embedded_env_vars"])
