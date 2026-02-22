# Multi-Device Setup (LAN)

How to run RoboTaste with a moderator computer and a subject tablet on the same network.

## Architecture

```
┌─────────────────────────────────────────────────┐
│  Moderator's Computer                           │
│                                                 │
│  FastAPI server (0.0.0.0:8000)                  │
│  ├── /api/*       → REST API                    │
│  ├── /assets/*    → React static files          │
│  └── /*           → React SPA (index.html)      │
│                                                 │
│  + pump_control_service.py (optional)           │
│  + SQLite DB (robotaste.db)                     │
└──────────────┬──────────────────────────────────┘
               │ WiFi (same network)
               │
    ┌──────────┴──────────┐
    │                     │
┌───┴────┐          ┌────┴─────┐
│ Moderator         │ Subject   │
│ Browser           │ Tablet    │
│ localhost:8000    │ 192.168.x.y:8000
│ /moderator/setup  │ /subject  │
└────────┘          └──────────┘
```

Everything runs on **one port** (8000). The React frontend and API are served together — no tunneling, no public exposure, no CORS issues.

## Quick Start

### 1. Install dependencies (one time)

```bash
pip install -r requirements.txt
cd frontend && npm install && cd ..
```

### 2. Start the server

```bash
python start_new_ui.py                # Without pumps
python start_new_ui.py --with-pump    # With pump hardware
```

The terminal will display:
- The **subject URL** (e.g., `http://192.168.1.42:8000/subject`)
- A **QR code** you can show to the subject

### 3. Connect the tablet

**Option A — QR code (easiest):**
Scan the QR code shown in the terminal or on the moderator monitoring page.

**Option B — URL:**
Open Chrome on the tablet and navigate to the subject URL shown in the terminal.

**Option C — Bookmark:**
After connecting once, bookmark the page. The URL remains the same as long as the
computer's IP doesn't change.

### 4. Run the experiment

1. **Moderator** opens `http://localhost:8000/` → selects a protocol → starts session
2. **Subject tablet** auto-detects the active session and begins the experiment flow
3. **Moderator** monitors progress on the monitoring page (includes QR code card)

## Development Mode

For frontend development with hot reload:

```bash
python start_new_ui.py --dev
```

This starts:
- FastAPI on `localhost:8000` (API only)
- Vite dev server on `localhost:5173` (frontend with hot reload)
- Vite proxies `/api` requests to FastAPI automatically

Development mode binds to `localhost` only — not accessible from other devices.

## Troubleshooting

### Tablet can't reach the server

| Symptom | Cause | Fix |
|---------|-------|-----|
| Connection refused | Server not bound to 0.0.0.0 | Use `python start_new_ui.py` (not `--dev`) |
| Connection timed out | Network blocks device-to-device traffic | Use a personal hotspot (see below) |
| "No active sessions" | No session started yet | Start a session from the moderator page first |
| Wrong IP shown | Multiple network interfaces | Check `ifconfig` / `ipconfig` for the correct WiFi IP |

### Using a personal hotspot (fallback)

If your organization's WiFi blocks device-to-device traffic (client isolation):

1. Enable personal hotspot on your phone
2. Connect both the computer and tablet to the hotspot
3. Run `python start_new_ui.py` — the detected IP will be from the hotspot network
4. Everything works identically

### Firewall issues (macOS)

On first run, macOS may ask "Do you want the application to accept incoming network
connections?" — click **Allow**. If you accidentally clicked Deny:

1. Open System Settings → Network → Firewall → Options
2. Find Python and set it to "Allow incoming connections"

### Firewall issues (Windows)

Windows Defender Firewall may block the server. When prompted, allow Python
on **private networks**. If you missed the prompt:

1. Open Windows Defender Firewall → Advanced Settings
2. Inbound Rules → New Rule → Port → TCP 8000 → Allow

## Options Reference

```
python start_new_ui.py [options]

Options:
  --with-pump     Start the pump control service (requires hardware)
  --dev           Development mode (Vite hot reload, localhost only)
  --port PORT     Server port (default: 8000)
  --build         Legacy alias for default mode (backward compatible)
```
