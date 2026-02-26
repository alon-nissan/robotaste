#!/usr/bin/env python3
"""
RoboTaste React + FastAPI Launcher
Starts FastAPI backend, Vite dev server, and optionally the pump service.

Usage:
    python start_new_ui.py [--with-pump] [--build] [--dev] [--port PORT]

Modes:
    (default)       Production: builds frontend, serves everything on one port.
                    Subject tablets connect via LAN IP shown at startup.
    --dev           Development: runs Vite dev server (hot reload) + FastAPI separately.
    --build         Alias for default mode (kept for backward compatibility).

Options:
    --with-pump     Also start the pump control service (requires hardware)
    --port PORT     Server port (default: 8000)

Press Ctrl+C to stop all services.
"""

import sys
import subprocess
import time
import signal
import argparse
import os
import socket
from pathlib import Path


class Colors:
    """ANSI color codes for terminal output."""
    HEADER = '\033[95m'
    BLUE = '\033[94m'
    CYAN = '\033[96m'
    GREEN = '\033[92m'
    YELLOW = '\033[93m'
    RED = '\033[91m'
    BOLD = '\033[1m'
    DIM = '\033[2m'
    END = '\033[0m'


def _port_in_use(port: int) -> bool:
    """Check if a port is already in use (IPv4 or IPv6)."""
    for family in (socket.AF_INET, socket.AF_INET6):
        try:
            with socket.socket(family, socket.SOCK_STREAM) as s:
                addr = ('::1', port, 0, 0) if family == socket.AF_INET6 else ('localhost', port)
                if s.connect_ex(addr) == 0:
                    return True
        except OSError:
            continue
    return False


def _kill_port_occupant(port: int) -> bool:
    """Kill whatever process is holding *port*. Returns True if cleared."""
    try:
        result = subprocess.run(
            ["lsof", "-nP", f"-iTCP:{port}", "-sTCP:LISTEN", "-t"],
            capture_output=True, text=True
        )
        pids = [int(p) for p in result.stdout.split() if p.strip()]
        if not pids:
            return True
        for pid in pids:
            os.kill(pid, signal.SIGTERM)
        time.sleep(0.5)
        return not _port_in_use(port)
    except Exception:
        return False


def _get_lan_ip() -> str:
    """Detect the machine's LAN IP address."""
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as s:
            s.connect(("8.8.8.8", 80))
            return s.getsockname()[0]
    except Exception:
        return "127.0.0.1"


def _get_tailscale_ip() -> str | None:
    """Detect the machine's Tailscale IP, if Tailscale is running."""
    try:
        # Try common Tailscale binary locations
        for cmd in ["tailscale", "/Applications/Tailscale.app/Contents/MacOS/Tailscale"]:
            try:
                result = subprocess.run(
                    [cmd, "ip", "-4"],
                    capture_output=True, text=True, timeout=3,
                )
                if result.returncode == 0 and result.stdout.strip():
                    return result.stdout.strip().split("\n")[0]
            except (FileNotFoundError, subprocess.TimeoutExpired):
                continue
    except Exception:
        pass
    # Fallback: check for Tailscale interface by scanning interfaces
    try:
        import netifaces  # type: ignore
    except ImportError:
        pass
    # Check for 100.x.y.z addresses on any interface
    try:
        import fcntl
        import struct
        for iface_name in socket.if_nameindex():
            try:
                s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
                ip = socket.inet_ntoa(fcntl.ioctl(
                    s.fileno(), 0x8915,  # SIOCGIFADDR
                    struct.pack('256s', iface_name[1].encode())
                )[20:24])
                if ip.startswith("100."):
                    return ip
            except Exception:
                continue
    except Exception:
        pass
    return None


def _generate_qr_text(url: str) -> str:
    """Generate a text-based QR code for terminal display using segno."""
    try:
        import segno
        import io
        qr = segno.make(url)
        buf = io.StringIO()
        qr.terminal(out=buf, compact=True)
        return buf.getvalue()
    except ImportError:
        return ""


class ReactLauncher:
    """Manages FastAPI, Vite, and pump service processes."""

    def __init__(self, with_pump: bool = False, dev_mode: bool = False, port: int = 8000):
        self.api_process = None
        self.vite_process = None
        self.pump_process = None
        self.with_pump = with_pump
        self.dev_mode = dev_mode
        self.port = port
        self.project_root = Path(__file__).parent
        self.frontend_dir = self.project_root / "frontend"
        self.dist_dir = self.frontend_dir / "dist"

    def print_banner(self):
        mode_label = "Development" if self.dev_mode else "Production (LAN)"
        print(f"\n{Colors.BOLD}{Colors.CYAN}{'='*70}{Colors.END}")
        print(f"{Colors.BOLD}{Colors.CYAN}{f'RoboTaste — {mode_label}':^70}{Colors.END}")
        print(f"{Colors.BOLD}{Colors.CYAN}{'='*70}{Colors.END}\n")

    def check_ports(self) -> bool:
        """Check that required ports are free."""
        ok = True
        ports = [(self.port, "FastAPI")]
        if self.dev_mode:
            ports.append((5173, "Vite"))
        for port, name in ports:
            if _port_in_use(port):
                print(f"{Colors.YELLOW}⚠ Port {port} ({name}) is in use — killing stale process...{Colors.END}")
                if _kill_port_occupant(port):
                    print(f"{Colors.GREEN}  ✓ Cleared{Colors.END}")
                else:
                    print(f"{Colors.RED}✗ Could not clear port {port}. Run: lsof -i :{port} | grep LISTEN{Colors.END}")
                    ok = False
        return ok

    def _open_log(self, name: str):
        """Open a log file in the logs/ directory for a subprocess."""
        log_dir = self.project_root / "logs"
        log_dir.mkdir(exist_ok=True)
        return open(log_dir / f"{name}.log", "a")

    def build_frontend(self) -> bool:
        """Build the React frontend if dist/ is missing or stale."""
        if self.dev_mode:
            return True

        index_html = self.dist_dir / "index.html"
        src_dir = self.frontend_dir / "src"

        # Check if build is needed
        needs_build = False
        if not index_html.exists():
            needs_build = True
            print(f"{Colors.BLUE}[0] Building React frontend (first time)...{Colors.END}")
        else:
            # Rebuild if any source file is newer than the build output
            build_time = index_html.stat().st_mtime
            for src_file in src_dir.rglob("*"):
                if src_file.is_file() and src_file.stat().st_mtime > build_time:
                    needs_build = True
                    print(f"{Colors.BLUE}[0] Rebuilding React frontend (source changed)...{Colors.END}")
                    break

        if not needs_build:
            print(f"{Colors.GREEN}✓ Frontend build is up to date{Colors.END}")
            return True

        try:
            result = subprocess.run(
                ["npm", "run", "build"],
                cwd=str(self.frontend_dir),
                capture_output=True,
                text=True,
                timeout=120,
            )
            if result.returncode == 0:
                print(f"{Colors.GREEN}✓ Frontend built successfully{Colors.END}")
                return True
            else:
                print(f"{Colors.RED}✗ Frontend build failed:{Colors.END}")
                print(result.stderr[-500:] if result.stderr else result.stdout[-500:])
                return False
        except subprocess.TimeoutExpired:
            print(f"{Colors.RED}✗ Frontend build timed out{Colors.END}")
            return False
        except FileNotFoundError:
            print(f"{Colors.RED}✗ npm not found. Run: cd frontend && npm install{Colors.END}")
            return False

    def start_api(self) -> bool:
        """Start FastAPI backend."""
        step = 1
        bind_host = "127.0.0.1" if self.dev_mode else "0.0.0.0"
        print(f"{Colors.BLUE}[{step}] Starting FastAPI backend ({bind_host}:{self.port})...{Colors.END}")
        try:
            log = self._open_log("fastapi_process")
            cmd = [
                sys.executable, "-m", "uvicorn",
                "api.main:app",
                "--host", bind_host,
                "--port", str(self.port),
            ]
            if self.dev_mode:
                cmd.append("--reload")
            self.api_process = subprocess.Popen(
                cmd,
                cwd=str(self.project_root),
                stdout=log,
                stderr=log,
                start_new_session=True,
            )
            # Wait for uvicorn to bind
            for _ in range(20):
                time.sleep(0.5)
                if _port_in_use(self.port):
                    print(f"{Colors.GREEN}✓ FastAPI started on {bind_host}:{self.port}{Colors.END}")
                    return True
                if self.api_process.poll() is not None:
                    break

            print(f"{Colors.RED}✗ FastAPI failed to start{Colors.END}")
            return False
        except Exception as e:
            print(f"{Colors.RED}✗ Error starting FastAPI: {e}{Colors.END}")
            return False

    def start_vite(self) -> bool:
        """Start Vite dev server on port 5173."""
        if not self.dev_mode:
            return True  # skip — FastAPI serves static build
        print(f"{Colors.BLUE}[2] Starting Vite dev server...{Colors.END}")
        try:
            log = self._open_log("vite_process")
            self.vite_process = subprocess.Popen(
                ["npm", "run", "dev"],
                cwd=str(self.frontend_dir),
                stdout=log,
                stderr=log,
                start_new_session=True,
            )
            for _ in range(20):
                time.sleep(0.5)
                if _port_in_use(5173):
                    print(f"{Colors.GREEN}✓ Vite dev server on http://localhost:5173{Colors.END}")
                    return True
                if self.vite_process.poll() is not None:
                    break

            print(f"{Colors.RED}✗ Vite failed to start{Colors.END}")
            return False
        except Exception as e:
            print(f"{Colors.RED}✗ Error starting Vite: {e}{Colors.END}")
            return False

    def start_pump_service(self) -> bool:
        """Start pump control service (if requested)."""
        if not self.with_pump:
            return True
        print(f"{Colors.BLUE}[3] Starting pump control service...{Colors.END}")
        try:
            log = self._open_log("pump_service_process")
            self.pump_process = subprocess.Popen(
                [
                    sys.executable,
                    "pump_control_service.py",
                    "--db-path", "robotaste.db",
                    "--poll-interval", "0.5"
                ],
                cwd=str(self.project_root),
                stdout=log,
                stderr=log,
                start_new_session=True,
            )
            time.sleep(1)
            if self.pump_process.poll() is None:
                print(f"{Colors.GREEN}✓ Pump service started (polling robotaste.db){Colors.END}")
                return True
            else:
                print(f"{Colors.RED}✗ Pump service failed to start{Colors.END}")
                return False
        except Exception as e:
            print(f"{Colors.RED}✗ Error starting pump service: {e}{Colors.END}")
            return False

    def print_access_info(self):
        lan_ip = _get_lan_ip()
        tailscale_ip = _get_tailscale_ip()

        print(f"\n{Colors.BOLD}{Colors.GREEN}{'='*70}{Colors.END}")
        print(f"{Colors.BOLD}{Colors.GREEN}{'RoboTaste is ready!':^70}{Colors.END}")
        print(f"{Colors.BOLD}{Colors.GREEN}{'='*70}{Colors.END}\n")

        if self.dev_mode:
            print(f"{Colors.BOLD}Development Mode:{Colors.END}\n")
            print(f"  {Colors.CYAN}Moderator:{Colors.END}  http://localhost:5173/")
            print(f"  {Colors.CYAN}Subject:{Colors.END}    http://localhost:5173/subject")
            print(f"  {Colors.CYAN}API:{Colors.END}        http://localhost:{self.port}/api")
            print(f"  {Colors.CYAN}API docs:{Colors.END}   http://localhost:{self.port}/docs\n")
            print(f"{Colors.DIM}  Note: Vite proxies /api to FastAPI automatically.{Colors.END}")
            print(f"{Colors.DIM}  For multi-device testing, use: python start_new_ui.py{Colors.END}\n")
        else:
            # Prefer Tailscale IP (works through client isolation)
            preferred_ip = tailscale_ip or lan_ip
            subject_url = f"http://{preferred_ip}:{self.port}/subject"

            print(f"{Colors.BOLD}Moderator (this computer):{Colors.END}\n")
            print(f"  {Colors.CYAN}→{Colors.END}  http://localhost:{self.port}/\n")

            print(f"{Colors.BOLD}Subject (tablet):{Colors.END}\n")
            if tailscale_ip:
                print(f"  {Colors.CYAN}→{Colors.END}  http://{tailscale_ip}:{self.port}/subject  {Colors.GREEN}(Tailscale ✓){Colors.END}")
                if lan_ip != "127.0.0.1":
                    print(f"  {Colors.DIM}   http://{lan_ip}:{self.port}/subject  (LAN — may not work with client isolation){Colors.END}")
            else:
                print(f"  {Colors.CYAN}→{Colors.END}  http://{lan_ip}:{self.port}/subject")
            print()

            # Show QR code for easy tablet connection
            qr = _generate_qr_text(subject_url)
            if qr:
                print(f"{Colors.BOLD}Scan this QR code on the tablet:{Colors.END}\n")
                print(qr)
            else:
                print(f"{Colors.DIM}  (Install 'segno' for a QR code: pip install segno){Colors.END}\n")

            if preferred_ip == "127.0.0.1":
                print(f"{Colors.YELLOW}⚠ Could not detect LAN IP. Are you connected to WiFi?{Colors.END}\n")
            elif not tailscale_ip:
                print(f"{Colors.DIM}  Tip: Install Tailscale for reliable connectivity through firewalls.{Colors.END}\n")

        print(f"{Colors.BOLD}Services running:{Colors.END}")
        print(f"  • FastAPI API    → http://localhost:{self.port}/api")
        if self.dev_mode:
            print(f"  • Vite dev       → http://localhost:5173 (hot reload)")
        else:
            print(f"  • React frontend → served from FastAPI (production build)")
        if self.with_pump:
            print(f"  • Pump service   → polling robotaste.db")
        print()

        print(f"{Colors.BOLD}Logs:{Colors.END}")
        print(f"  • API server     → logs/api_server_*.log")
        print(f"  • Pump ops       → logs/api_pump_operations_*.log")
        if self.with_pump:
            print(f"  • Pump service   → logs/pump_control_service.log")
        print()

        if self.with_pump:
            print(f"{Colors.YELLOW}⚠ Pump service is running — ensure pumps are connected{Colors.END}\n")

        print(f"{Colors.BOLD}Press Ctrl+C to stop all services{Colors.END}\n")
        print(f"{Colors.GREEN}{'='*70}{Colors.END}\n")

    def cleanup(self):
        """Terminate all child processes."""
        print(f"\n{Colors.YELLOW}Shutting down...{Colors.END}")

        for name, proc in [
            ("FastAPI", self.api_process),
            ("Vite", self.vite_process),
            ("Pump service", self.pump_process),
        ]:
            if proc and proc.poll() is None:
                print(f"  Stopping {name}...")
                try:
                    os.killpg(os.getpgid(proc.pid), signal.SIGTERM)
                except ProcessLookupError:
                    pass
                try:
                    proc.wait(timeout=5)
                except subprocess.TimeoutExpired:
                    try:
                        os.killpg(os.getpgid(proc.pid), signal.SIGKILL)
                    except ProcessLookupError:
                        pass

        print(f"{Colors.GREEN}All services stopped.{Colors.END}\n")

    def run(self) -> int:
        self.print_banner()

        if not self.check_ports():
            return 1

        if not self.build_frontend():
            return 1

        if not self.start_api():
            self.cleanup()
            return 1

        if not self.start_vite():
            self.cleanup()
            return 1

        if not self.start_pump_service():
            self.cleanup()
            return 1

        self.print_access_info()

        # Monitor processes until Ctrl+C or unexpected exit
        try:
            while True:
                if self.api_process and self.api_process.poll() is not None:
                    print(f"{Colors.RED}FastAPI has stopped unexpectedly{Colors.END}")
                    break
                if self.vite_process and self.vite_process.poll() is not None:
                    print(f"{Colors.RED}Vite has stopped unexpectedly{Colors.END}")
                    break
                if self.with_pump and self.pump_process and self.pump_process.poll() is not None:
                    print(f"{Colors.RED}Pump service has stopped unexpectedly{Colors.END}")
                    break
                time.sleep(1)
        except KeyboardInterrupt:
            pass

        self.cleanup()
        return 0


def main():
    parser = argparse.ArgumentParser(
        description="RoboTaste React+FastAPI launcher"
    )
    parser.add_argument(
        "--with-pump",
        action="store_true",
        help="Also start the pump control service (requires hardware)"
    )
    parser.add_argument(
        "--dev",
        action="store_true",
        help="Development mode: run Vite dev server with hot reload (localhost only)"
    )
    parser.add_argument(
        "--build",
        action="store_true",
        help="(Legacy alias) Same as default mode — build and serve production frontend"
    )
    parser.add_argument(
        "--port",
        type=int,
        default=8000,
        help="Server port (default: 8000)"
    )
    args = parser.parse_args()

    # Default is production mode; --dev enables development mode
    dev_mode = args.dev

    launcher = ReactLauncher(with_pump=args.with_pump, dev_mode=dev_mode, port=args.port)

    def signal_handler(sig, frame):
        launcher.cleanup()
        sys.exit(0)

    signal.signal(signal.SIGINT, signal_handler)

    sys.exit(launcher.run())


if __name__ == "__main__":
    main()
