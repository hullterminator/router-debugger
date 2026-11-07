"""
FastAPI Web Dashboard for Router Debugging and Hardware Hacking Toolkit.
"""

import os
from pathlib import Path
from typing import Optional
from fastapi import FastAPI, UploadFile, File, Form, HTTPException
from fastapi.responses import HTMLResponse, JSONResponse

from router_debugger.hardware.pinout_guide import get_hardware_safety_summary
from router_debugger.hardware.uart import list_serial_ports, detect_baud_rate
from router_debugger.network.scanner import detect_default_gateway, scan_router_ports
from router_debugger.network.ping_monitor import PingMonitor
from router_debugger.network.tftp_server import TFTPServer
from router_debugger.firmware.analyzer import scan_firmware_file
from router_debugger.troubleshooting.playbooks import PLAYBOOKS, list_playbooks, get_playbook

app = FastAPI(title="Router Hardware Hacking & Debugging Toolkit", version="0.1.0")

# Active TFTP instance reference
active_tftp_server: Optional[TFTPServer] = None

HTML_PAGE = """
<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>Router Hardware Debugger & Fixer</title>
  <script src="https://cdn.tailwindcss.com"></script>
  <style>
    body { background-color: #0d1117; color: #c9d1d9; font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif; }
    .card { background-color: #161b22; border: 1px solid #30363d; border-radius: 8px; padding: 1.25rem; }
    .tab-btn.active { border-bottom: 2px solid #58a6ff; color: #58a6ff; }
  </style>
</head>
<body class="p-6">
  <div class="max-w-6xl mx-auto">
    <!-- Header -->
    <header class="flex justify-between items-center pb-6 border-b border-gray-800">
      <div>
        <h1 class="text-2xl font-bold text-white flex items-center gap-2">
          <span class="text-cyan-400">⚡</span> Router Hardware Debugger & Fixer
        </h1>
        <p class="text-sm text-gray-400 mt-1">UART Console • Bootloader Intercept • TFTP Unbrick • Hardware Diagnostics</p>
      </div>
      <div class="flex items-center gap-3">
        <span class="px-3 py-1 bg-green-950 text-green-400 border border-green-800 rounded-full text-xs font-mono">Toolkit Ready</span>
      </div>
    </header>

    <!-- Navigation Tabs -->
    <div class="flex gap-6 mt-6 border-b border-gray-800 text-sm font-medium">
      <button onclick="switchTab('pinout')" id="tab-pinout" class="tab-btn active pb-3 text-gray-300">Hardware Pinouts & Safety</button>
      <button onclick="switchTab('uart')" id="tab-uart" class="tab-btn pb-3 text-gray-400 hover:text-gray-200">UART & Serial</button>
      <button onclick="switchTab('network')" id="tab-network" class="tab-btn pb-3 text-gray-400 hover:text-gray-200">Network Recon & Gateway</button>
      <button onclick="switchTab('tftp')" id="tab-tftp" class="tab-btn pb-3 text-gray-400 hover:text-gray-200">TFTP Recovery Server</button>
      <button onclick="switchTab('firmware')" id="tab-firmware" class="tab-btn pb-3 text-gray-400 hover:text-gray-200">Firmware Analyzer</button>
      <button onclick="switchTab('troubleshoot')" id="tab-troubleshoot" class="tab-btn pb-3 text-gray-400 hover:text-gray-200">Issue Playbooks</button>
    </div>

    <!-- TAB 1: PINOUT & SAFETY -->
    <div id="content-pinout" class="tab-content mt-6 space-y-6">
      <div class="card border-red-900/60 bg-red-950/20">
        <h2 class="text-lg font-bold text-red-400 flex items-center gap-2">⚠️ Golden Hardware Rules (Avoid Frying Your Router)</h2>
        <ul class="mt-3 space-y-2 text-sm text-red-200" id="safety-rules">
          <li>• NEVER connect VCC (3.3V or 5V) from USB adapter if router is plugged into power! Only connect GND, TX, and RX.</li>
          <li>• Verify 3.3V TTL logic level. Never use RS-232 (+/- 12V).</li>
        </ul>
      </div>

      <div class="card">
        <h3 class="text-md font-bold text-white mb-3">Multimeter Pin Identification Checklist</h3>
        <div class="overflow-x-auto">
          <table class="w-full text-left text-sm text-gray-300">
            <thead class="bg-gray-800 text-gray-400 font-mono text-xs">
              <tr>
                <th class="p-3">Step</th>
                <th class="p-3">Target Pin</th>
                <th class="p-3">Multimeter Mode</th>
                <th class="p-3">Router Power</th>
                <th class="p-3">Procedure</th>
              </tr>
            </thead>
            <tbody id="multimeter-steps" class="divide-y divide-gray-800">
              <!-- populated by JS -->
            </tbody>
          </table>
        </div>
      </div>

      <div class="card">
        <h3 class="text-md font-bold text-white mb-3">SPI Flash (SOIC-8) Pinout for CH341A External Programmer</h3>
        <div class="grid grid-cols-2 md:grid-cols-4 gap-4" id="spi-pins">
          <!-- populated by JS -->
        </div>
      </div>
    </div>

    <!-- TAB 2: UART & SERIAL -->
    <div id="content-uart" class="tab-content hidden mt-6 space-y-6">
      <div class="card">
        <div class="flex justify-between items-center mb-4">
          <h3 class="text-md font-bold text-white">Detected Serial COM Ports</h3>
          <button onclick="refreshPorts()" class="px-3 py-1 bg-blue-600 hover:bg-blue-500 text-white rounded text-xs font-semibold">Refresh Ports</button>
        </div>
        <div id="ports-list" class="space-y-2 text-sm">
          <div class="text-gray-400">Loading ports...</div>
        </div>
      </div>

      <div class="grid grid-cols-1 md:grid-cols-2 gap-6">
        <div class="card">
          <h3 class="text-md font-bold text-white mb-2">Auto-Detect Baud Rate</h3>
          <p class="text-xs text-gray-400 mb-4">Samples serial data across 115200, 57600, 38400, etc. to detect ASCII text.</p>
          <div class="flex gap-2">
            <input id="baud-port-input" type="text" placeholder="COM3" class="bg-gray-900 border border-gray-700 px-3 py-1.5 rounded text-sm w-full">
            <button onclick="runBaudDetect()" class="px-4 py-1.5 bg-cyan-600 hover:bg-cyan-500 text-white rounded text-sm font-semibold whitespace-nowrap">Detect Baud</button>
          </div>
          <div id="baud-results" class="mt-4 text-xs font-mono text-gray-300"></div>
        </div>

        <div class="card">
          <h3 class="text-md font-bold text-white mb-2">Bootloader Interrupter</h3>
          <p class="text-xs text-gray-400 mb-4">Spams break sequence on power-cycle to interrupt U-Boot / CFE into interactive shell.</p>
          <div class="space-y-3">
            <div class="flex gap-2">
              <input id="interrupt-port" type="text" placeholder="COM3" class="bg-gray-900 border border-gray-700 px-3 py-1.5 rounded text-sm w-1/2">
              <select id="interrupt-seq" class="bg-gray-900 border border-gray-700 px-3 py-1.5 rounded text-sm w-1/2">
                <option value="space">Spacebar (' ')</option>
                <option value="enter">Enter (\r\n)</option>
                <option value="ctrl_c">Ctrl+C (\x03)</option>
                <option value="tpl">TP-Link ('tpl')</option>
                <option value="all">All Combinations</option>
              </select>
            </div>
            <button onclick="triggerInterrupt()" class="w-full py-2 bg-yellow-600 hover:bg-yellow-500 text-white rounded text-sm font-semibold">Start Bootloader Interrupt</button>
          </div>
          <div id="interrupt-status" class="mt-3 text-xs text-gray-300"></div>
        </div>
      </div>
    </div>

    <!-- TAB 3: NETWORK RECON -->
    <div id="content-network" class="tab-content hidden mt-6 space-y-6">
      <div class="card">
        <h3 class="text-md font-bold text-white mb-3">Router Discovery & Port Scanner</h3>
        <div class="flex gap-3 items-center">
          <input id="target-ip" type="text" placeholder="192.168.1.1" class="bg-gray-900 border border-gray-700 px-3 py-2 rounded text-sm w-64">
          <button onclick="detectGateway()" class="px-3 py-2 bg-gray-800 hover:bg-gray-700 text-gray-200 rounded text-sm">Auto-Detect Gateway</button>
          <button onclick="scanPorts()" class="px-4 py-2 bg-green-600 hover:bg-green-500 text-white rounded text-sm font-semibold">Scan Management Ports</button>
        </div>
        <div id="scan-results" class="mt-4">
          <p class="text-xs text-gray-500">Scan router for open Telnet, SSH, HTTP, TR-069, and Debug ports.</p>
        </div>
      </div>
    </div>

    <!-- TAB 4: TFTP UNBRICK -->
    <div id="content-tftp" class="tab-content hidden mt-6 space-y-6">
      <div class="card">
        <h3 class="text-md font-bold text-white mb-2">TFTP Recovery Server (RFC 1350)</h3>
        <p class="text-xs text-gray-400 mb-4">Serves recovery firmware images to U-Boot / CFE recovery mode on port 69.</p>
        <div class="flex gap-3 items-center mb-4">
          <input id="tftp-dir" type="text" value="./firmware_recovery" class="bg-gray-900 border border-gray-700 px-3 py-2 rounded text-sm w-72">
          <button onclick="toggleTftp()" id="tftp-toggle-btn" class="px-4 py-2 bg-blue-600 hover:bg-blue-500 text-white rounded text-sm font-semibold">Start TFTP Server</button>
        </div>
        <div id="tftp-status" class="p-4 bg-gray-900 rounded font-mono text-xs text-gray-300 space-y-1">
          <div>Status: Stopped</div>
          <div class="text-gray-500">Drop firmware files (firmware.bin, tp_recovery.bin) into ./firmware_recovery/</div>
        </div>
      </div>
    </div>

    <!-- TAB 5: FIRMWARE ANALYZER -->
    <div id="content-firmware" class="tab-content hidden mt-6 space-y-6">
      <div class="card">
        <h3 class="text-md font-bold text-white mb-3">Firmware Header & Partition Inspector</h3>
        <p class="text-xs text-gray-400 mb-4">Analyzes binary files for TRX, SquashFS, U-Boot uImage headers, checksums, and boot parameters.</p>
        <div class="flex gap-3">
          <input id="fw-path-input" type="text" placeholder="C:/path/to/firmware.bin" class="bg-gray-900 border border-gray-700 px-3 py-2 rounded text-sm flex-1">
          <button onclick="analyzeFirmwarePath()" class="px-4 py-2 bg-cyan-600 hover:bg-cyan-500 text-white rounded text-sm font-semibold">Analyze Path</button>
        </div>
        <div id="fw-results" class="mt-6 text-sm"></div>
      </div>
    </div>

    <!-- TAB 6: TROUBLESHOOTING PLAYBOOKS -->
    <div id="content-troubleshoot" class="tab-content hidden mt-6 space-y-6">
      <div class="grid grid-cols-1 md:grid-cols-3 gap-6">
        <div class="card col-span-1">
          <h3 class="text-md font-bold text-white mb-3">Issue Categories</h3>
          <div id="playbooks-nav" class="space-y-2">
            <!-- populated by JS -->
          </div>
        </div>
        <div class="card col-span-2" id="playbook-viewer">
          <div class="text-gray-500 text-sm">Select an issue on the left to see diagnosis and repair steps.</div>
        </div>
      </div>
    </div>
  </div>

  <script>
    function switchTab(tabId) {
      document.querySelectorAll('.tab-content').forEach(el => el.classList.add('hidden'));
      document.querySelectorAll('.tab-btn').forEach(el => el.classList.remove('active', 'text-cyan-400'));
      document.getElementById('content-' + tabId).classList.remove('hidden');
      document.getElementById('tab-' + tabId).classList.add('active', 'text-cyan-400');
    }

    // Load initial data
    async function init() {
      const pinoutRes = await fetch('/api/pinout');
      const pinout = await pinoutRes.json();
      
      const tbody = document.getElementById('multimeter-steps');
      tbody.innerHTML = pinout.procedure.map(s => `
        <tr class="hover:bg-gray-800/50">
          <td class="p-3 text-cyan-400 font-bold">${s.step}</td>
          <td class="p-3 text-green-400 font-semibold">${s.name}</td>
          <td class="p-3 text-yellow-300 font-mono text-xs">${s.mode}</td>
          <td class="p-3 text-red-300 text-xs">${s.power}</td>
          <td class="p-3 text-gray-300 text-xs">${s.instructions}</td>
        </tr>
      `).join('');

      const spiDiv = document.getElementById('spi-pins');
      spiDiv.innerHTML = pinout.spi_flash.pins.map(p => `
        <div class="p-2.5 bg-gray-900 border border-gray-800 rounded">
          <div class="text-xs text-gray-500 font-mono">Pin ${p.pin}</div>
          <div class="font-bold text-yellow-400 text-sm">${p.name}</div>
          <div class="text-xs text-gray-400 mt-1">${p.description}</div>
        </div>
      `).join('');

      refreshPorts();
      detectGateway();
      loadPlaybooks();
    }

    async function refreshPorts() {
      const res = await fetch('/api/uart/ports');
      const data = await res.json();
      const div = document.getElementById('ports-list');
      if (!data.ports || data.ports.length === 0 || data.ports[0].device === 'N/A') {
        div.innerHTML = '<div class="text-yellow-400 text-xs">No active serial COM ports detected. Plug in your USB-UART adapter.</div>';
        return;
      }
      div.innerHTML = data.ports.map(p => `
        <div class="flex justify-between items-center p-2.5 bg-gray-900 border border-gray-800 rounded">
          <div>
            <span class="font-mono font-bold text-green-400 mr-2">${p.device}</span>
            <span class="text-gray-300 text-xs">${p.description}</span>
          </div>
          <button onclick="selectPort('${p.device}')" class="px-2.5 py-1 bg-gray-800 hover:bg-gray-700 text-xs rounded text-gray-300">Select</button>
        </div>
      `).join('');
    }

    function selectPort(name) {
      document.getElementById('baud-port-input').value = name;
      document.getElementById('interrupt-port').value = name;
    }

    async function detectGateway() {
      const res = await fetch('/api/network/gateway');
      const data = await res.json();
      if (data.gateway) {
        document.getElementById('target-ip').value = data.gateway;
      }
    }

    async function scanPorts() {
      const ip = document.getElementById('target-ip').value;
      const resDiv = document.getElementById('scan-results');
      resDiv.innerHTML = '<div class="text-xs text-cyan-400">Scanning ports on ' + ip + '...</div>';
      const res = await fetch('/api/network/scan?ip=' + encodeURIComponent(ip));
      const data = await res.json();
      if (!data.open_ports || data.open_ports.length === 0) {
        resDiv.innerHTML = '<div class="text-xs text-red-400">No open ports found on ' + ip + '.</div>';
        return;
      }
      resDiv.innerHTML = `
        <table class="w-full text-left text-xs mt-2">
          <thead class="bg-gray-800 text-gray-400 font-mono">
            <tr><th class="p-2">Port</th><th class="p-2">Status</th><th class="p-2">Service</th><th class="p-2">Banner</th></tr>
          </thead>
          <tbody class="divide-y divide-gray-800">
            ${data.open_ports.map(p => `
              <tr>
                <td class="p-2 font-mono font-bold text-yellow-400">${p.port}</td>
                <td class="p-2 text-green-400">${p.status}</td>
                <td class="p-2 text-cyan-300">${p.service}</td>
                <td class="p-2 text-gray-400 font-mono">${p.banner || ''}</td>
              </tr>
            `).join('')}
          </tbody>
        </table>
      `;
    }

    async function loadPlaybooks() {
      const res = await fetch('/api/troubleshoot/playbooks');
      const data = await res.json();
      const nav = document.getElementById('playbooks-nav');
      nav.innerHTML = data.playbooks.map(p => `
        <button onclick="viewPlaybook('${p.id}')" class="w-full text-left p-2.5 rounded bg-gray-900 border border-gray-800 hover:border-gray-700 text-xs font-medium text-gray-300 block">
          ${p.title}
        </button>
      `).join('');
    }

    async function viewPlaybook(id) {
      const res = await fetch('/api/troubleshoot/playbook/' + id);
      const p = await res.json();
      const viewer = document.getElementById('playbook-viewer');
      viewer.innerHTML = `
        <h2 class="text-lg font-bold text-white mb-2">${p.title}</h2>
        <div class="mb-4">
          <div class="text-xs font-bold text-red-400 mb-1">Symptoms:</div>
          <ul class="text-xs text-gray-300 list-disc list-inside space-y-1">
            ${p.symptoms.map(s => `<li>${s}</li>`).join('')}
          </ul>
        </div>
        <div class="mb-4">
          <div class="text-xs font-bold text-yellow-400 mb-1">Root Causes:</div>
          <ul class="text-xs text-gray-300 list-disc list-inside space-y-1">
            ${p.root_causes.map(c => `<li>${c}</li>`).join('')}
          </ul>
        </div>
        <div class="space-y-3">
          <div class="text-xs font-bold text-cyan-400">Repair Steps:</div>
          ${p.steps.map(st => `
            <div class="p-3 bg-gray-900 border border-gray-800 rounded">
              <div class="text-xs font-bold text-green-400 mb-1">Step ${st.step}: ${st.action}</div>
              <pre class="text-xs text-gray-300 whitespace-pre-wrap font-sans">${st.detail}</pre>
            </div>
          `).join('')}
        </div>
      `;
    }

    async function analyzeFirmwarePath() {
      const path = document.getElementById('fw-path-input').value;
      const resDiv = document.getElementById('fw-results');
      resDiv.innerHTML = '<div class="text-xs text-cyan-400">Scanning firmware binary...</div>';
      const res = await fetch('/api/firmware/analyze?path=' + encodeURIComponent(path));
      const data = await res.json();
      if (data.error) {
        resDiv.innerHTML = '<div class="text-xs text-red-400">' + data.error + '</div>';
        return;
      }
      resDiv.innerHTML = `
        <div class="p-4 bg-gray-900 border border-gray-800 rounded mb-4">
          <div class="text-sm font-bold text-white mb-2">Integrity Hashes</div>
          <div class="font-mono text-xs text-gray-300 space-y-1">
            <div>MD5: ${data.checksums.md5}</div>
            <div>SHA256: ${data.checksums.sha256}</div>
            <div>CRC32: ${data.checksums.crc32}</div>
          </div>
        </div>
        <div class="p-4 bg-gray-900 border border-gray-800 rounded">
          <div class="text-sm font-bold text-white mb-2">Identified Signatures & Components (${data.signatures.length})</div>
          <table class="w-full text-left text-xs">
            <thead class="bg-gray-800 text-gray-400 font-mono">
              <tr><th class="p-2">Offset</th><th class="p-2">Component</th><th class="p-2">Type</th><th class="p-2">Description</th></tr>
            </thead>
            <tbody class="divide-y divide-gray-800">
              ${data.signatures.map(s => `
                <tr>
                  <td class="p-2 font-mono text-cyan-400">${s.hex_offset}</td>
                  <td class="p-2 font-bold text-green-400">${s.name}</td>
                  <td class="p-2 text-yellow-300">${s.type}</td>
                  <td class="p-2 text-gray-300">${s.description}</td>
                </tr>
              `).join('')}
            </tbody>
          </table>
        </div>
      `;
    }

    async function toggleTftp() {
      const btn = document.getElementById('tftp-toggle-btn');
      const dir = document.getElementById('tftp-dir').value;
      const statusDiv = document.getElementById('tftp-status');

      if (btn.innerText.includes('Start')) {
        const res = await fetch('/api/tftp/start', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ dir: dir, port: 69 })
        });
        const data = await res.json();
        btn.innerText = 'Stop TFTP Server';
        btn.classList.replace('bg-blue-600', 'bg-red-600');
        statusDiv.innerHTML = `<div>Status: <span class="text-green-400 font-bold">LISTENING</span> on port 69</div><div>Serving: ${dir}</div>`;
      } else {
        await fetch('/api/tftp/stop', { method: 'POST' });
        btn.innerText = 'Start TFTP Server';
        btn.classList.replace('bg-red-600', 'bg-blue-600');
        statusDiv.innerHTML = `<div>Status: <span class="text-gray-400">Stopped</span></div>`;
      }
    }

    window.onload = init;
  </script>
</body>
</html>
"""

@app.get("/", response_class=HTMLResponse)
def index():
    return HTML_PAGE

@app.get("/api/pinout")
def api_pinout():
    return get_hardware_safety_summary()

@app.get("/api/uart/ports")
def api_uart_ports():
    return {"ports": list_serial_ports()}

@app.get("/api/uart/detect_baud")
def api_detect_baud(port: str):
    return detect_baud_rate(port)

@app.get("/api/network/gateway")
def api_gateway():
    return {"gateway": detect_default_gateway()}

@app.get("/api/network/scan")
def api_scan(ip: Optional[str] = None):
    target = ip or detect_default_gateway()
    return {"ip": target, "open_ports": scan_router_ports(target)}

@app.post("/api/tftp/start")
def api_tftp_start(payload: dict):
    global active_tftp_server
    if active_tftp_server and active_tftp_server.running:
        active_tftp_server.stop()
    root_dir = payload.get("dir", "./firmware_recovery")
    port = payload.get("port", 69)
    active_tftp_server = TFTPServer(root_dir=root_dir, port=port)
    active_tftp_server.start()
    return {"status": "started", "dir": root_dir, "port": port}

@app.post("/api/tftp/stop")
def api_tftp_stop():
    global active_tftp_server
    if active_tftp_server:
        active_tftp_server.stop()
        active_tftp_server = None
    return {"status": "stopped"}

@app.get("/api/firmware/analyze")
def api_firmware_analyze(path: str):
    p = Path(path)
    if not p.exists():
        return {"error": f"File not found: {path}"}
    return scan_firmware_file(p)

@app.get("/api/troubleshoot/playbooks")
def api_playbooks():
    return {"playbooks": list_playbooks()}

@app.get("/api/troubleshoot/playbook/{playbook_id}")
def api_playbook_detail(playbook_id: str):
    pb = get_playbook(playbook_id)
    if not pb:
        raise HTTPException(status_code=404, detail="Playbook not found")
    return pb
