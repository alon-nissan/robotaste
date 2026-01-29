#!/usr/bin/env python3
"""
RoboTaste Unified Launcher
Starts both Streamlit and ngrok in a single command.

Usage:
    python start_robotaste.py [--with-pump]

Options:
    --with-pump     Also start the pump control service (requires hardware)

Press Ctrl+C to stop all services.
"""

import sys
import subprocess
import time
import signal
import argparse
import json
import requests
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
    UNDERLINE = '\033[4m'
    END = '\033[0m'


class RoboTasteLauncher:
    """Manages Streamlit and ngrok processes."""
    
    def __init__(self, with_pump=False):
        self.streamlit_process = None
        self.ngrok_process = None
        self.pump_process = None
        self.with_pump = with_pump
        self.ngrok_url = None
        
    def print_banner(self):
        """Print startup banner."""
        print(f"\n{Colors.BOLD}{Colors.CYAN}{'='*70}{Colors.END}")
        print(f"{Colors.BOLD}{Colors.CYAN}{'RoboTaste Multi-Device Experiment Platform':^70}{Colors.END}")
        print(f"{Colors.BOLD}{Colors.CYAN}{'='*70}{Colors.END}\n")
        
    def check_ngrok_installed(self):
        """Check if ngrok is installed."""
        try:
            subprocess.run(
                ["ngrok", "version"],
                capture_output=True,
                check=True
            )
            return True
        except (subprocess.CalledProcessError, FileNotFoundError):
            return False
            
    def start_streamlit(self):
        """Start Streamlit server."""
        print(f"{Colors.BLUE}[1/3] Starting Streamlit...{Colors.END}")
        
        try:
            self.streamlit_process = subprocess.Popen(
                ["streamlit", "run", "main_app.py"],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True
            )
            
            # Wait for Streamlit to start
            time.sleep(3)
            
            if self.streamlit_process.poll() is None:
                print(f"{Colors.GREEN}✓ Streamlit started on http://localhost:8501{Colors.END}")
                return True
            else:
                print(f"{Colors.RED}✗ Streamlit failed to start{Colors.END}")
                return False
                
        except Exception as e:
            print(f"{Colors.RED}✗ Error starting Streamlit: {e}{Colors.END}")
            return False
            
    def start_pump_service(self):
        """Start pump control service."""
        if not self.with_pump:
            return True
            
        print(f"{Colors.BLUE}[2/3] Starting pump control service...{Colors.END}")
        
        try:
            self.pump_process = subprocess.Popen(
                [
                    "python",
                    "pump_control_service.py",
                    "--db-path", "robotaste.db",
                    "--poll-interval", "0.5"
                ],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True
            )
            
            time.sleep(1)
            
            if self.pump_process.poll() is None:
                print(f"{Colors.GREEN}✓ Pump service started{Colors.END}")
                return True
            else:
                print(f"{Colors.RED}✗ Pump service failed to start{Colors.END}")
                return False
                
        except Exception as e:
            print(f"{Colors.RED}✗ Error starting pump service: {e}{Colors.END}")
            return False
            
    def start_ngrok(self):
        """Start ngrok tunnel."""
        step = "3/3" if not self.with_pump else "3/4"
        print(f"{Colors.BLUE}[{step}] Starting ngrok tunnel...{Colors.END}")
        
        try:
            self.ngrok_process = subprocess.Popen(
                ["ngrok", "http", "8501", "--log=stdout"],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True
            )
            
            # Wait for ngrok to start and get the URL
            print(f"{Colors.YELLOW}Waiting for ngrok tunnel...{Colors.END}")
            
            for _ in range(10):
                time.sleep(1)
                url = self.get_ngrok_url()
                if url:
                    self.ngrok_url = url
                    # Save URL to file for Streamlit to read
                    self.save_ngrok_url(url)
                    print(f"{Colors.GREEN}✓ ngrok tunnel established{Colors.END}\n")
                    return True
                    
            print(f"{Colors.RED}✗ Could not get ngrok URL{Colors.END}")
            return False
            
        except Exception as e:
            print(f"{Colors.RED}✗ Error starting ngrok: {e}{Colors.END}")
            return False
            
    def save_ngrok_url(self, url):
        """Save ngrok URL to file for Streamlit to read."""
        try:
            with open(".ngrok_url", "w") as f:
                f.write(url)
        except Exception as e:
            print(f"{Colors.YELLOW}Warning: Could not save ngrok URL: {e}{Colors.END}")
            
    def get_ngrok_url(self):
        """Get the public ngrok URL from the API."""
        try:
            response = requests.get("http://127.0.0.1:4040/api/tunnels", timeout=1)
            if response.status_code == 200:
                data = response.json()
                for tunnel in data.get("tunnels", []):
                    if tunnel.get("proto") == "https":
                        return tunnel.get("public_url")
        except:
            pass
        return None
        
    def print_access_info(self):
        """Print access information with role-specific URLs."""
        print(f"{Colors.BOLD}{Colors.GREEN}{'='*70}{Colors.END}")
        print(f"{Colors.BOLD}{Colors.GREEN}RoboTaste is ready!{Colors.END}")
        print(f"{Colors.BOLD}{Colors.GREEN}{'='*70}{Colors.END}\n")
        
        print(f"{Colors.BOLD}Access URLs:{Colors.END}\n")
        
        # Local URLs
        print(f"  {Colors.CYAN}Local Access (this computer):{Colors.END}")
        print(f"    {Colors.BOLD}Moderator:{Colors.END} http://localhost:8501/?role=moderator")
        print(f"    {Colors.BOLD}Subject:{Colors.END}    http://localhost:8501/?role=subject\n")
        
        # Remote URLs (ngrok)
        if self.ngrok_url:
            print(f"  {Colors.CYAN}Remote Access (tablets/other devices):{Colors.END}")
            print(f"    {Colors.BOLD}Moderator:{Colors.END} {self.ngrok_url}/?role=moderator")
            print(f"    {Colors.BOLD}Subject:{Colors.END}    {self.ngrok_url}/?role=subject")
            print(f"    {Colors.YELLOW}⚠ First visit: Click 'Visit Site' on ngrok warning page{Colors.END}\n")
        
        print(f"{Colors.BOLD}Workflow:{Colors.END}")
        print(f"  1. {Colors.CYAN}Moderator{Colors.END} opens moderator URL (on this computer or tablet)")
        print(f"  2. Create a new session")
        print(f"  3. {Colors.CYAN}Subject{Colors.END} opens subject URL (on their tablet)")
        print(f"  4. Subject auto-joins or selects session from list\n")
        
        if self.with_pump:
            print(f"{Colors.YELLOW}⚠ Pump service is running - ensure pumps are connected{Colors.END}\n")
            
        print(f"{Colors.BOLD}Press Ctrl+C to stop all services{Colors.END}\n")
        print(f"{Colors.BOLD}{Colors.GREEN}{'='*70}{Colors.END}\n")
        
    def cleanup(self):
        """Terminate all processes."""
        print(f"\n{Colors.YELLOW}Shutting down...{Colors.END}")
        
        # Clean up ngrok URL file
        try:
            Path(".ngrok_url").unlink(missing_ok=True)
        except:
            pass
        
        processes = [
            ("Streamlit", self.streamlit_process),
            ("ngrok", self.ngrok_process),
            ("Pump service", self.pump_process)
        ]
        
        for name, process in processes:
            if process and process.poll() is None:
                print(f"Stopping {name}...")
                process.terminate()
                try:
                    process.wait(timeout=5)
                except subprocess.TimeoutExpired:
                    process.kill()
                    
        print(f"{Colors.GREEN}All services stopped.{Colors.END}\n")
        
    def run(self):
        """Main run loop."""
        self.print_banner()
        
        # Check prerequisites
        if not self.check_ngrok_installed():
            print(f"{Colors.RED}Error: ngrok is not installed{Colors.END}")
            print(f"Install with: {Colors.CYAN}brew install ngrok{Colors.END}")
            print(f"Or download from: {Colors.CYAN}https://ngrok.com/download{Colors.END}")
            return 1
            
        # Start services
        if not self.start_streamlit():
            self.cleanup()
            return 1
            
        if not self.start_pump_service():
            self.cleanup()
            return 1
            
        if not self.start_ngrok():
            self.cleanup()
            return 1
            
        # Print access information
        self.print_access_info()
        
        # Wait for Ctrl+C
        try:
            while True:
                # Check if any process has died
                if self.streamlit_process.poll() is not None:
                    print(f"{Colors.RED}Streamlit has stopped unexpectedly{Colors.END}")
                    break
                if self.ngrok_process.poll() is not None:
                    print(f"{Colors.RED}ngrok has stopped unexpectedly{Colors.END}")
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
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description="RoboTaste unified launcher for Streamlit + ngrok"
    )
    parser.add_argument(
        "--with-pump",
        action="store_true",
        help="Also start the pump control service (requires hardware connection)"
    )
    
    args = parser.parse_args()
    
    launcher = RoboTasteLauncher(with_pump=args.with_pump)
    
    # Handle Ctrl+C gracefully
    def signal_handler(sig, frame):
        launcher.cleanup()
        sys.exit(0)
        
    signal.signal(signal.SIGINT, signal_handler)
    
    sys.exit(launcher.run())


if __name__ == "__main__":
    main()
