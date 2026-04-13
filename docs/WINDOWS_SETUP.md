# RoboTaste Setup on a New Windows Computer

This guide is the **runtime setup path** for running experiments on Windows.
It does **not** cover developer mode (`--dev`).

---

## 1. What you need

- Windows 10 or 11
- Internet connection
- Python 3.10+ (from [python.org](https://www.python.org/downloads/windows/))
- Node.js 18+ LTS (from [nodejs.org](https://nodejs.org/))
- Git (from [git-scm.com](https://git-scm.com/download/win))
- Optional: Tailscale account + app (recommended for tablet connectivity)
- Optional: NE-4000 pumps + USB-to-serial adapter

> During Python install, enable **"Add python.exe to PATH"**.

---

## 2. Clone the project

Open **PowerShell** and run:

```powershell
cd $HOME
mkdir Projects -ErrorAction SilentlyContinue
cd Projects
git clone <YOUR_REPO_URL> RoboTaste
cd RoboTaste
```

If the repository is already copied to this machine, just `cd` into that folder.

---

## 3. Create a virtual environment and install dependencies

From the project root (`RoboTaste`):

```powershell
py -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
pip install -r requirements.txt
cd frontend
npm install
cd ..
```

You should now see `(.venv)` at the start of your PowerShell prompt.

---

## 4. (Recommended) Install Tailscale for tablet connectivity

Tailscale avoids campus/lab WiFi isolation issues.

1. Install from [tailscale.com/download/windows](https://tailscale.com/download/windows)
2. Sign in on the moderator computer
3. Install Tailscale on the subject tablet/phone
4. Sign in with the same account on the tablet

When both devices are connected, RoboTaste can use the `100.x.x.x` subject URL.

---

## 5. Start RoboTaste

From the same PowerShell window (with `(.venv)` active):

```powershell
python start_new_ui.py
```

If you are running hardware pumps:

```powershell
python start_new_ui.py --with-pump
```

Expected output includes:
- Moderator URL: `http://localhost:8000/`
- Subject URL: `http://<tailscale-or-lan-ip>:8000/subject`
- QR code for quick tablet connection

Keep this window open while the experiment is running.

---

## 6. Connect moderator and subject

1. On the moderator computer, open `http://localhost:8000/`
2. On the tablet, open the printed subject URL (or scan QR code)
3. In moderator UI, create and start a session
4. Tablet should move from waiting screen into the session flow

---

## 7. Optional pump path (NE-4000)

1. Connect pumps and USB-serial adapter before launch
2. Start with:
   ```powershell
   python start_new_ui.py --with-pump
   ```
3. Choose the serial port:
   - Typical Windows format: `COM3`, `COM4`, ...
   - Protocol wizard (Create Protocol → Pump step) can auto-detect ports
   - For manual JSON protocols, use the **Serial Port Detector** on the
     **Landing Page** (Moderator panel) for a quick recommended value and detected list
4. Keep pump service running for the full experiment

---

## 8. Stopping and restarting

- Stop all services: press `Ctrl+C` in the PowerShell window running `start_new_ui.py`
- Next run:
  1. Open PowerShell in project folder
  2. `.\.venv\Scripts\Activate.ps1`
  3. `python start_new_ui.py` (or `--with-pump`)

---

## 9. Optional one-click launcher

You can also run `RoboTaste.bat` by double-clicking it. It:
1. checks git updates and prompts before pulling when safe
2. starts RoboTaste in `--with-pump` mode
3. looks for Python in:
   - `.venv\Scripts\python.exe`
   - `venv\Scripts\python.exe`
   - system `python`

Use this after dependencies are installed.

---

## 10. Troubleshooting (Windows)

### `'python' is not recognized`

Use:

```powershell
py start_new_ui.py
```

If needed, reinstall Python and enable PATH integration.

### PowerShell blocks `Activate.ps1`

Run once in PowerShell:

```powershell
Set-ExecutionPolicy -ExecutionPolicy RemoteSigned -Scope CurrentUser
```

Then reopen PowerShell and activate `.venv` again.

### `'npm' is not recognized`

Reinstall Node.js 18+ LTS, then open a new PowerShell window.

### Firewall prompt appears

Allow Python on **Private networks**.

### Subject device cannot reach URL

Verify:
- RoboTaste process is still running
- Tailscale is connected on both devices (recommended path)
- Subject is using the exact `/subject` URL shown by startup output

### Serial port not visible

- Reconnect USB-serial adapter
- Click refresh in the Landing Page **Serial Port Detector** (or in wizard pump step)
- If still missing, check Windows Device Manager for COM assignment
