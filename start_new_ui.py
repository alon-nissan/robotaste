#!/usr/bin/env python3
"""
RoboTaste React + FastAPI Launcher
Starts FastAPI backend, Vite dev server, and optionally the pump service.

Usage:
    python start_new_ui.py [--with-pump] [--build]

Options:
    --with-pump     Also start the pump control service (requires hardware)
    --build         Serve production build via FastAPI instead of Vite dev server

Press Ctrl+C to stop all services.
"""

import sys
import subprocess
import time
import signal
import argparse
import os
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
    END = '\033[0m'


def _port_in_use(port: int) -> bool:
    """Check if a port is already in use (IPv4 or IPv6)."""
    import socket
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


class ReactLauncher:
    """Manages FastAPI, Vite, and pump service processes."""

    def __init__(self, with_pump: bool = False, build_mode: bool = False):
        self.api_process = None
        self.vite_process = None
        self.pump_process = None
        self.with_pump = with_pump
        self.build_mode = build_mode
        self.project_root = Path(__file__).parent
        self.frontend_dir = self.project_root / "frontend"

    def print_banner(self):
        print(f"\n{Colors.BOLD}{Colors.CYAN}{'='*70}{Colors.END}")
        print(f"{Colors.BOLD}{Colors.CYAN}{'RoboTaste — React + FastAPI':^70}{Colors.END}")
        print(f"{Colors.BOLD}{Colors.CYAN}{'='*70}{Colors.END}\n")

    def check_ports(self) -> bool:
        """Check that required ports are free."""
        ok = True
        for port, name in [(8000, "FastAPI"), (5173, "Vite")]:
            if self.build_mode and port == 5173:
                continue
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

    def start_api(self) -> bool:
        """Start FastAPI backend on port 8000."""
        step = 1
        print(f"{Colors.BLUE}[{step}] Starting FastAPI backend...{Colors.END}")
        try:
            log = self._open_log("fastapi_process")
            self.api_process = subprocess.Popen(
                [
                    sys.executable, "-m", "uvicorn",
                    "api.main:app",
                    "--reload", "--port", "8000"
                ],
                cwd=str(self.project_root),
                stdout=log,
                stderr=log,
                start_new_session=True,
            )
            # Wait for uvicorn to bind
            for _ in range(20):
                time.sleep(0.5)
                if _port_in_use(8000):
                    print(f"{Colors.GREEN}✓ FastAPI started on http://localhost:8000{Colors.END}")
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
        if self.build_mode:
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
        print(f"\n{Colors.BOLD}{Colors.GREEN}{'='*70}{Colors.END}")
        print(f"{Colors.BOLD}{Colors.GREEN}{'RoboTaste is ready!':^70}{Colors.END}")
        print(f"{Colors.BOLD}{Colors.GREEN}{'='*70}{Colors.END}\n")

        if self.build_mode:
            base = "http://localhost:8000"
        else:
            base = "http://localhost:5173"

        print(f"{Colors.BOLD}Access URLs:{Colors.END}\n")
        print(f"  {Colors.CYAN}Moderator:{Colors.END}  {base}/")
        print(f"  {Colors.CYAN}Subject:{Colors.END}    {base}/subject\n")

        print(f"{Colors.BOLD}Services running:{Colors.END}")
        print(f"  • FastAPI API    → http://localhost:8000/api")
        if not self.build_mode:
            print(f"  • Vite dev       → http://localhost:5173 (hot reload)")
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
        "--build",
        action="store_true",
        help="Serve production build via FastAPI instead of Vite dev server"
    )
    args = parser.parse_args()

    launcher = ReactLauncher(with_pump=args.with_pump, build_mode=args.build)

    def signal_handler(sig, frame):
        launcher.cleanup()
        sys.exit(0)

    signal.signal(signal.SIGINT, signal_handler)

    sys.exit(launcher.run())


if __name__ == "__main__":
    main()
