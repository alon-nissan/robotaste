# Running a RoboTaste Experiment — Step by Step

This guide walks you through everything you need to set up and run a multi-device
taste experiment. The **moderator** uses a computer, and the **subject** uses a
tablet (or phone). No technical experience is required.

---

## Table of Contents

1. [What You Need](#what-you-need)
2. [One-Time Setup (do this once)](#one-time-setup)
   - [Install Software on the Computer](#step-1-install-software-on-the-computer)
   - [Install Tailscale on the Computer](#step-2-install-tailscale-on-the-computer)
   - [Install Tailscale on the Tablet](#step-3-install-tailscale-on-the-tablet)
3. [Running an Experiment](#running-an-experiment)
   - [Start the Server](#step-1-start-the-server)
   - [Connect the Tablet](#step-2-connect-the-tablet)
   - [Create and Start a Session](#step-3-create-and-start-a-session)
   - [Monitor the Experiment](#step-4-monitor-the-experiment)
4. [Troubleshooting](#troubleshooting)
5. [How It Works (for the curious)](#how-it-works)
6. [Command Reference](#command-reference)

---

## What You Need

| Item | Details |
|------|---------|
| **Computer** (moderator) | Mac or Windows, with Python 3.10+ and Node.js 18+ installed |
| **Tablet or phone** (subject) | Android or iPad, with Chrome or Safari |
| **Network connection** | Both devices need internet access (for Tailscale) |
| **Tailscale account** | Free — sign up at [tailscale.com](https://tailscale.com/) |
| **NE-4000 pump** (optional) | Only needed if running automated dispensing experiments |

> **Why Tailscale?** Most university and enterprise WiFi networks block devices
> from talking to each other directly (this is called "client isolation"). Tailscale
> creates a secure, private connection between your computer and tablet that works
> through any network — even if they're on completely different WiFi networks. It's
> free for personal use and takes about 5 minutes to set up.

---

## One-Time Setup

You only need to do these steps once. After that, running an experiment takes about
30 seconds.

### Step 1: Install Software on the Computer

Open the **Terminal** app (Mac) or **Command Prompt** (Windows) and run:

```bash
# Navigate to the RoboTaste folder
cd path/to/Software

# Install Python dependencies
pip install -r requirements.txt

# Install frontend dependencies
cd frontend
npm install
cd ..
```

If any of these commands fail, make sure Python 3.10+ and Node.js 18+ are installed:
- **Python**: Download from [python.org](https://www.python.org/downloads/)
- **Node.js**: Download from [nodejs.org](https://nodejs.org/)

### Step 2: Install Tailscale on the Computer

**On Mac (two options):**

**Option A — Mac App Store (easiest):**
1. Open the **App Store** on your Mac
2. Search for **"Tailscale"**
3. Click **Get** → **Install**
4. Open Tailscale from your Applications folder
5. Click **Log in** — you'll be taken to a browser to sign in
6. Create a free account (you can use Google, Microsoft, or GitHub to sign in)
7. After signing in, you'll see the Tailscale icon (⬡) in your menu bar at the top of the screen — this means it's running

**Option B — Homebrew (for developers):**
```bash
brew install tailscale
sudo tailscaled &      # Start the background service
tailscale up           # Log in (opens browser)
```

**On Windows:**
1. Download Tailscale from [tailscale.com/download/windows](https://tailscale.com/download/windows)
2. Run the installer
3. Click the Tailscale icon in the system tray → **Log in**
4. Sign in with the **same account** you'll use on the tablet

**Verify it's working:** After signing in, you should see your computer listed in the
[Tailscale admin console](https://login.tailscale.com/admin/machines). Your computer
will be assigned an IP address starting with `100.` (e.g., `100.105.132.1`).

### Step 3: Install Tailscale on the Tablet

**On Android:**
1. Open the **Google Play Store**
2. Search for **"Tailscale"**
3. Tap **Install**
4. Open the Tailscale app
5. Tap **Sign in** and log in with the **same account** you used on the computer
6. When prompted, allow the VPN connection (this is local/private — not a traditional VPN)
7. You should see both your computer and tablet listed in the Tailscale app

**On iPad/iPhone:**
1. Open the **App Store**
2. Search for **"Tailscale"**
3. Tap **Get** → **Install**
4. Open Tailscale, tap **Sign in**, and log in with the **same account**
5. Allow the VPN configuration when prompted

**Verify the connection:** In the Tailscale app on the tablet, you should see
your computer listed with a green dot (online). Both devices are now connected
on a private network, regardless of what WiFi they're on.

> **Tip:** Tailscale runs in the background and reconnects automatically. You
> generally don't need to open it again after the initial setup. Just make sure
> the VPN toggle is on (you'll see a small key icon 🔑 in the tablet's status bar).

---

## Running an Experiment

### Step 1: Start the Server

On the **computer**, open Terminal and run:

```bash
cd path/to/Software
python start_new_ui.py
```

If you're using hardware pumps, add the `--with-pump` flag:

```bash
python start_new_ui.py --with-pump
```

You'll see output like this:

```
======================================================================
                       RoboTaste is ready!
======================================================================

Moderator (this computer):

  →  http://localhost:8000/

Subject (tablet):

  →  http://100.105.132.1:8000/subject  (Tailscale ✓)

Scan this QR code on the tablet:

  █████████████████████████
  █ ▄▄▄▄▄ █ ▀▄▀  █ ▄▄▄▄▄ █
  ...
```

> **Important:** Keep this terminal window open for the entire experiment.
> To stop the server when you're done, press **Ctrl+C** in the terminal.

### Step 2: Connect the Tablet

You have three options to connect the subject's tablet:

**Option A — Scan the QR code (easiest):**
1. Open the **camera app** on the tablet
2. Point it at the QR code shown in the terminal (or on the moderator's monitoring page)
3. Tap the link that appears — it will open in Chrome/Safari

**Option B — Type the URL:**
1. Open **Chrome** (Android) or **Safari** (iPad) on the tablet
2. Type the subject URL shown in the terminal (e.g., `http://100.105.132.1:8000/subject`)
3. Press Enter

**Option C — Use a saved bookmark:**
After connecting the first time, bookmark the page on the tablet. The URL stays the
same as long as you're using Tailscale (the `100.x.x.x` address doesn't change).

The tablet should show a **"Waiting for session"** screen. This means it's connected
and waiting for you to start an experiment session.

### Step 3: Create and Start a Session

On the **computer's browser**, go to `http://localhost:8000/`:

1. You'll see the **Landing Page** — click **"New Session"**
2. On the **Setup Page**:
   - Select a **protocol** from the dropdown (this defines the experiment flow)
   - Configure pump settings if applicable
   - Click **"Start Session"**
3. The subject's tablet will **automatically detect** the new session and begin
   showing the experiment flow (consent form → registration → instructions → etc.)

### Step 4: Monitor the Experiment

After starting the session, the moderator is taken to the **Monitoring Page** which shows:

- The current **phase** of the experiment (e.g., "Selection", "Questionnaire")
- The current **cycle** number and results so far
- A **QR code card** (in case you need to reconnect the tablet)
- Bayesian Optimization visualizations (if the protocol uses BO)
- Controls to **advance**, **skip**, or **end** the experiment

The experiment cycles automatically between selection → preparation → questionnaire
until the protocol's stopping criteria are met, or you manually end it.

---

## Troubleshooting

### The tablet shows "This site can't be reached" or "ERR_ADDRESS_UNREACHABLE"

**Most likely cause:** Tailscale is not running on one or both devices.

**Fix:**
1. On the **tablet**: Open the Tailscale app and make sure it's connected (green dot
   next to your computer's name, VPN toggle is on)
2. On the **computer**: Check that the Tailscale icon is in the menu bar (Mac) or
   system tray (Windows). Click it to verify it says "Connected"
3. Restart the RoboTaste server (`Ctrl+C` in terminal, then run `python start_new_ui.py` again)

### The tablet shows "Waiting for session" but nothing happens

**Cause:** No experiment session has been started yet.

**Fix:** Go to `http://localhost:8000/` on the moderator's computer and start a new session.

### The terminal says "Could not detect LAN IP"

**Cause:** The computer isn't connected to any network.

**Fix:** Make sure the computer is connected to WiFi or Ethernet. If you're using
Tailscale, make sure it's running — the server will use the Tailscale IP instead.

### The QR code is too small or hard to scan

**Fix:** Use the QR code on the **moderator monitoring page** instead — it's larger
and easier to scan. Or type the URL manually on the tablet.

### macOS asks "Do you want the application to accept incoming network connections?"

**Click "Allow."** This lets the tablet connect to the server. If you accidentally
clicked "Deny":

1. Open **System Settings** → **Network** → **Firewall** → **Options**
2. Find **Python** in the list and set it to **"Allow incoming connections"**

### Windows Firewall blocks the connection

When Windows asks, allow Python on **private networks**. If you missed the prompt:

1. Open **Windows Defender Firewall** → **Advanced Settings**
2. **Inbound Rules** → **New Rule** → **Port** → **TCP 8000** → **Allow**

### "I don't want to use Tailscale — is there another way?"

Yes. If you can connect both devices to the same WiFi network that doesn't have
client isolation (e.g., a home network or phone hotspot):

1. Create a **personal hotspot** on your phone
2. Connect both the computer and tablet to the hotspot's WiFi
3. Run `python start_new_ui.py` — it will show a `192.168.x.x` address
4. Use that address on the tablet

This works on any hotspot but requires you to use your phone's data plan during
the experiment.

---

## How It Works

For those who want to understand the technical setup:

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
               │
     Tailscale private network (100.x.y.z)
     or LAN / hotspot (192.168.x.y)
               │
    ┌──────────┴──────────┐
    │                     │
┌───┴────┐          ┌────┴─────┐
│ Moderator         │ Subject   │
│ Browser           │ Tablet    │
│ localhost:8000    │ 100.x.y.z:8000
│ /moderator/setup  │ /subject  │
└────────┘          └──────────┘
```

- **Single port**: Both the API and the web interface are served from port 8000.
  No tunneling, no public internet exposure.
- **Automatic IP detection**: The server detects whether Tailscale is installed and
  prefers the Tailscale IP (`100.x.y.z`) over the LAN IP (`192.168.x.y`).
- **QR code**: Generated locally — no internet connection needed for the QR code itself.
- **Database polling**: The subject's tablet checks for experiment updates every few
  seconds via the API. No WebSocket or push notification setup needed.

---

## Command Reference

```
python start_new_ui.py [options]

Options:
  --with-pump     Start the pump control service (requires NE-4000 hardware)
  --dev           Development mode (Vite hot reload, localhost only — not for experiments)
  --port PORT     Server port (default: 8000)
  --build         Legacy alias for default mode (backward compatible)
```

### Development Mode (for developers only)

```bash
python start_new_ui.py --dev
```

This starts the frontend with hot reload (code changes appear instantly) but only
works on localhost — the tablet cannot connect in this mode. Use it for UI development,
not for running experiments.
