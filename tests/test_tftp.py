import socket
import time
import struct
from pathlib import Path
from router_debugger.network.tftp_server import TFTPServer, OP_RRQ, OP_DATA, OP_ACK

def test_tftp_server_startup_and_stop(tmp_path):
    server = TFTPServer(root_dir=str(tmp_path), host="127.0.0.1", port=6969)
    server.start()
    assert server.running is True
    time.sleep(0.2)
    server.stop()
    assert server.running is False

def test_tftp_download_transfer(tmp_path):
    # Place a small dummy firmware file
    fw_content = b"TEST_ROUTER_FIRMWARE_PAYLOAD_1234567890"
    fw_file = tmp_path / "firmware.bin"
    fw_file.write_bytes(fw_content)

    server = TFTPServer(root_dir=str(tmp_path), host="127.0.0.1", port=7979)
    server.start()
    time.sleep(0.2)

    try:
        # Create client socket to simulate U-Boot TFTP request
        client = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        client.settimeout(2.0)

        # RRQ packet: OpCode 1 + "firmware.bin\0octet\0"
        rrq = struct.pack("!H", OP_RRQ) + b"firmware.bin\x00octet\x00"
        client.sendto(rrq, ("127.0.0.1", 7979))

        # Receive data block 1
        data, server_worker_addr = client.recvfrom(1024)
        opcode, block_num = struct.unpack("!HH", data[:4])
        payload = data[4:]

        assert opcode == OP_DATA
        assert block_num == 1
        assert payload == fw_content

        # Send ACK block 1
        ack = struct.pack("!HH", OP_ACK, 1)
        client.sendto(ack, server_worker_addr)

        client.close()
        time.sleep(0.1)
        assert server.stats["transfers_completed"] == 1
    finally:
        server.stop()
