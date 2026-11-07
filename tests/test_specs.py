from router_debugger.hardware.uart import extract_technical_specs

SAMPLE_BOOT_LOG = """
U-Boot 1.1.4 (Aug 15 2021 - 10:22:15)
AP121 (AR9341) U-boot
DRAM: 64 MB
Top of RAM usable for U-Boot at: 84000000
Reserving 263k for U-Boot at: 83fbc000
Flash: 8 MB
CPU: 535 MHz
In:    serial
Out:   serial
Err:   serial
Net:   ag934x_enet_initialize...
eth0: 00:03:7f:ba:db:01
Hit any key to stop autoboot:  0 
Booting image at 0x9f020000 ...
Linux version 3.10.14 (buildroot@builder) (gcc version 4.8.3)
0x000000000000-0x000000020000 : "u-boot"
0x000000020000-0x000000140000 : "kernel"
0x000000140000-0x0000007f0000 : "rootfs"
0x0000007f0000-0x000000800000 : "art"
Kernel command line: console=ttyS0,115200 root=/dev/mtdblock2 rootfstype=squashfs
"""

def test_extract_technical_specs():
    specs = extract_technical_specs(SAMPLE_BOOT_LOG)
    assert specs["bootloader"] is not None
    assert "U-Boot" in specs["bootloader"]
    assert "64 MB" in specs["ram_memory"]
    assert "8 MB" in specs["flash_chip"]
    assert "535 MHz" in specs["cpu_clock"]
    assert "3.10.14" in specs["linux_kernel"]
    assert "00:03:7f:ba:db:01" in specs["mac_addresses"]
    assert len(specs["mtd_partitions"]) == 4
    assert specs["mtd_partitions"][0]["name"] == "u-boot"
    assert specs["mtd_partitions"][3]["name"] == "art"
