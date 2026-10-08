"""Optional LAN Streamlit server and a temporary, narrowly scoped firewall rule."""

import atexit
import base64
import ipaddress
import json
import os
from pathlib import Path
import shutil
import socket
import subprocess
import sys
import tempfile
import threading
import time
import urllib.request
import uuid


LAN_CHILD = 'VIDEO_SCHOOL_LAN_CHILD'


def _ps_literal(value):
    return "'" + str(value).replace("'", "''") + "'"


def _encoded_command(source):
    return base64.b64encode(source.encode('utf-16-le')).decode('ascii')


def _route_address():
    """Find the address of the default IPv4 route without sending traffic."""
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as sock:
            sock.connect(('192.0.2.1', 80))
            return sock.getsockname()[0]
    except OSError:
        return socket.gethostbyname(socket.gethostname())


def _windows_addresses():
    """Read connected adapters without requiring administrator privileges."""
    script = """$ErrorActionPreference = 'Stop'
[Console]::OutputEncoding = New-Object System.Text.UTF8Encoding
$addresses = @(Get-NetIPConfiguration -All | ForEach-Object {
    $config = $_
    if ($config.NetAdapter.Status -eq 'Up') {
        $profile = Get-NetConnectionProfile -InterfaceIndex $config.InterfaceIndex -ErrorAction SilentlyContinue
        foreach ($address in $config.IPv4Address) {
            [PSCustomObject]@{
                Address = $address.IPAddress
                Adapter = $config.InterfaceAlias
                Physical = [bool]$config.NetAdapter.HardwareInterface
                Private = [bool]($profile.NetworkCategory -eq 'Private')
                Gateway = [bool]$config.IPv4DefaultGateway
            }
        }
    }
})
ConvertTo-Json -InputObject $addresses -Compress
"""
    result = subprocess.run(
        ['powershell.exe', '-NoProfile', '-EncodedCommand', _encoded_command(script)],
        capture_output=True, timeout=10,
        creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0),
    )
    if result.returncode:
        raise RuntimeError('Could not read Windows network adapters.')
    return json.loads(result.stdout.decode('utf-8-sig'))


def network_addresses():
    """Prefer physical private adapters over VPNs and virtual network routes."""
    if sys.platform == 'win32':
        try:
            records = _windows_addresses()
            if isinstance(records, dict):
                records = [records]
            candidates = []
            for record in records or []:
                address = ipaddress.IPv4Address(record['Address'])
                if address.is_loopback or address.is_unspecified or address.is_multicast:
                    continue
                score = (
                    bool(record.get('Physical')), bool(record.get('Private')),
                    bool(record.get('Gateway')), not address.is_link_local,
                )
                label = f"{record['Adapter']} — {address}"
                candidates.append((score, str(address), label))
            candidates.sort(key=lambda entry: entry[0], reverse=True)
            # One option per IP, even if Windows reports it more than once.
            options = {}
            for _, address, label in candidates:
                options.setdefault(address, label)
            if options:
                return list(options.items())
        except (OSError, subprocess.SubprocessError, ValueError, KeyError, TypeError, RuntimeError):
            pass
    address = _route_address()
    return [(address, f'Automatic — {address}')]


def lan_address():
    return network_addresses()[0][0]


def _free_port():
    for port in range(8502, 8602):
        try:
            with socket.socket() as sock:
                sock.bind(('0.0.0.0', port))
                return port
        except OSError:
            continue
    raise RuntimeError('No available port for the local server.')


def _firewall_script(directory, rule_name, port, child_pid, address=None):
    """The elevated helper owns removal, even if the app is abruptly closed."""
    local_address = f'-LocalAddress {_ps_literal(address)} ' if address else ''
    return f"""$ErrorActionPreference = 'Stop'
$directory = {_ps_literal(directory)}
$rule = {_ps_literal(rule_name)}
$owner = $null
$child = $null
try {{
    if (Test-Path "$directory/stop") {{ return }}
    $owner = Get-Process -Id {os.getpid()}
    $child = Get-Process -Id {child_pid}
    New-NetFirewallRule -Name $rule -DisplayName 'Video School local server' `
        -Direction Inbound -Action Allow -Protocol TCP -LocalPort {port} `
        -Program {_ps_literal(sys.executable)} {local_address}-Profile Private -RemoteAddress LocalSubnet | Out-Null
    Set-Content "$directory/ready" 'ready' -Encoding UTF8
    while (!(Test-Path "$directory/stop") -and !$owner.HasExited -and !$child.HasExited) {{
        Start-Sleep -Milliseconds 250
        $owner.Refresh()
        $child.Refresh()
    }}
}} catch {{
    Set-Content "$directory/error" $_.Exception.Message -Encoding UTF8
}} finally {{
    $removed = $false
    while (!$removed) {{
        try {{
            Get-NetFirewallRule -ErrorAction Stop | Where-Object {{ $_.Name -eq $rule }} | Remove-NetFirewallRule
            Set-Content "$directory/removed" 'removed' -Encoding UTF8
            $removed = $true
        }} catch {{
            Set-Content "$directory/error" $_.Exception.Message -Encoding UTF8
            Start-Sleep -Seconds 1
        }}
    }}
    if ($owner -and $child -and $owner.HasExited -and !$child.HasExited) {{ $child.Kill() }}
}}
"""


class LocalServer:
    """One controller shared by all browser sessions of the desktop server."""

    def __init__(self):
        self.process = None
        self.directory = None
        self.port = None
        self.address = None
        self.firewall_requested = False
        self.lock = threading.RLock()
        atexit.register(self.stop)

    @property
    def running(self):
        return self.process is not None and self.process.poll() is None

    @property
    def url(self):
        return f'http://{self.address}:{self.port}'

    def _firewall_error(self):
        error = self.directory / 'error'
        return error.read_text(encoding='utf-8-sig').strip() if error.exists() else ''

    def _open_firewall(self):
        rule = 'VideoSchool-LAN-' + uuid.uuid4().hex
        script = _firewall_script(self.directory, rule, self.port, self.process.pid, self.address)
        encoded = _encoded_command(script)
        # Encode the whole script: paths and apostrophes cannot become shell code.
        elevate = (
            "$ErrorActionPreference = 'Stop'; "
            "Start-Process -FilePath \"$PSHOME/powershell.exe\" -Verb RunAs "
            f"-WindowStyle Hidden -ArgumentList '-NoProfile -EncodedCommand {encoded}'"
        )
        self.firewall_requested = True
        result = subprocess.run(
            ['powershell.exe', '-NoProfile', '-EncodedCommand', _encoded_command(elevate)],
            capture_output=True, creationflags=subprocess.CREATE_NO_WINDOW,
            timeout=60,
        )
        if result.returncode:
            self.firewall_requested = False
            raise RuntimeError('Windows did not approve the firewall change. Accept the administrator prompt to enable sharing.')
        deadline = time.monotonic() + 20
        while time.monotonic() < deadline:
            error = self._firewall_error()
            if error:
                raise RuntimeError(f'Windows Firewall: {error}')
            if (self.directory / 'ready').exists():
                return
            time.sleep(0.1)
        raise RuntimeError('Timed out waiting for Windows Firewall. The server will be stopped.')

    def start(self, address=None):
        with self.lock:
            if self.running:
                return
            self.stop()
            self.port = _free_port()
            self.address = str(ipaddress.IPv4Address(address or lan_address()))
            self.directory = Path(tempfile.mkdtemp(prefix='video-school-lan-'))
            root = Path(__file__).resolve().parents[1]
            environment = os.environ.copy()
            environment[LAN_CHILD] = '1'
            command = [
                sys.executable, '-m', 'streamlit', 'run', str(root / 'app.py'),
                '--server.address', self.address, '--server.port', str(self.port),
                '--server.headless', 'true', '--browser.serverAddress', self.address,
                '--browser.gatherUsageStats', 'false', '--global.developmentMode', 'false',
            ]
            try:
                with (self.directory / 'server.log').open('wb') as log:
                    self.process = subprocess.Popen(
                        command, cwd=Path.cwd(), env=environment,
                        stdout=log, stderr=subprocess.STDOUT,
                        creationflags=subprocess.CREATE_NO_WINDOW if sys.platform == 'win32' else 0,
                    )
                deadline = time.monotonic() + 30
                while time.monotonic() < deadline:
                    if not self.running:
                        raise RuntimeError('Local server failed to start: ' +
                                           (self.directory / 'server.log').read_text(errors='replace')[-1200:])
                    try:
                        # A local health check must bypass browser/system proxies.
                        with urllib.request.build_opener(urllib.request.ProxyHandler({})).open(
                            f'{self.url}/_stcore/health', timeout=1
                        ) as response:
                            if response.status == 200:
                                break
                    except OSError:
                        time.sleep(0.2)
                else:
                    raise RuntimeError('Local server startup timed out.')
                if sys.platform == 'win32':
                    self._open_firewall()
            except Exception:
                self.stop()
                raise

    def stop(self):
        with self.lock:
            if self.directory:
                (self.directory / 'stop').touch()
            if self.process:
                if self.running:
                    self.process.terminate()
                    try:
                        self.process.wait(timeout=5)
                    except subprocess.TimeoutExpired:
                        self.process.kill()
                        self.process.wait(timeout=5)
                self.process = None
            if self.directory:
                if self.firewall_requested:
                    # Even a delayed UAC approval sees the stop marker and removes
                    # its own rule; retain these files until cleanup is confirmed.
                    deadline = time.monotonic() + 10
                    while not (self.directory / 'removed').exists():
                        if time.monotonic() >= deadline:
                            raise RuntimeError(
                                'Server stopped, but firewall cleanup is not confirmed. '
                                'Try disabling again. ' + self._firewall_error()
                            )
                        time.sleep(0.1)
                shutil.rmtree(self.directory, ignore_errors=True)
                self.directory = None
                self.firewall_requested = False
