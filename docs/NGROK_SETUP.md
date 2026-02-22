# Multi-Device Setup with ngrok

> **⚠️ DEPRECATED:** This guide covers the legacy Streamlit + ngrok setup.
> For the React + FastAPI stack, use LAN-based multi-device setup instead:
> see **[MULTI_DEVICE_SETUP.md](MULTI_DEVICE_SETUP.md)** or run `python start_new_ui.py`.

This guide explains how to set up RoboTaste for multi-device experiments where:
- **PC**: Runs the moderator interface, connects to pumps via serial, stores data
- **Tablet/Phone**: Displays the subject interface for participants

## Overview

RoboTaste uses ngrok to expose your local Streamlit server to a public URL, allowing subjects on different devices to access the experiment interface.

```
┌─────────────────────────────────────────────────────────────────────┐
│                         Your PC (Host Machine)                       │
│  ┌─────────────────┐  ┌─────────────────┐  ┌─────────────────┐      │
│  │   Streamlit     │  │  Pump Service   │  │     ngrok       │      │
│  │  localhost:8501 │  │   (hardware)    │  │   tunnel        │      │
│  └────────┬────────┘  └─────────────────┘  └────────┬────────┘      │
│           │                                          │               │
│           └──────────────────────────────────────────┘               │
│                              ▼                                       │
└──────────────────────────────┼───────────────────────────────────────┘
                               │
                    Public URL: https://xxxx.ngrok-free.app
                               │
              ┌────────────────┴────────────────┐
              ▼                                 ▼
      ┌───────────────┐                 ┌───────────────┐
      │   Moderator   │                 │    Subject    │
      │   (PC browser)│                 │   (Tablet)    │
      └───────────────┘                 └───────────────┘
```

## Prerequisites

- RoboTaste installed and working locally
- Internet connection on PC
- Subject device (tablet/phone) with a browser

## Step 1: Create ngrok Account (One-Time Setup)

1. Go to [https://ngrok.com/signup](https://ngrok.com/signup)
2. Sign up for a free account
3. After signing in, go to [https://dashboard.ngrok.com/get-started/your-authtoken](https://dashboard.ngrok.com/get-started/your-authtoken)
4. Copy your authtoken (you'll need this in Step 3)

## Step 2: Install ngrok

### macOS (Homebrew)
```bash
brew install ngrok
```

### macOS (Direct Download)
```bash
# Download from https://ngrok.com/download
# Unzip and move to /usr/local/bin
unzip ngrok-v3-stable-darwin-amd64.zip
sudo mv ngrok /usr/local/bin/
```

### Windows
1. Download from [https://ngrok.com/download](https://ngrok.com/download)
2. Unzip the file
3. Add ngrok.exe to your PATH or run from the unzipped folder

### Verify Installation
```bash
ngrok version
```

## Step 3: Configure ngrok Authtoken (One-Time Setup)

```bash
ngrok config add-authtoken YOUR_AUTHTOKEN_HERE
```

Replace `YOUR_AUTHTOKEN_HERE` with the token from Step 1.

## Step 4: Running an Experiment

### Quick Start (Recommended)

Use the unified launcher to start everything in one command:

```bash
cd /path/to/RoboTaste/Software
python start_robotaste.py
```

The launcher will:
1. Start Streamlit (localhost:8501)
2. Start ngrok tunnel
3. Display the ngrok URL prominently
4. Handle cleanup when you press Ctrl+C

**With pump hardware:**
```bash
python start_robotaste.py --with-pump
```

### Manual Start (Advanced)

If you prefer to run services separately, you'll need **three terminal windows** on your PC:

### Terminal 1: Start Streamlit
```bash
cd /path/to/RoboTaste/Software
streamlit run main_app.py
```
Wait for: `You can now view your Streamlit app in your browser: http://localhost:8501`

### Terminal 2: Start Pump Service (if using hardware)
```bash
cd /path/to/RoboTaste/Software
python pump_control_service.py --db-path robotaste.db --poll-interval 0.5
```

### Terminal 3: Start ngrok Tunnel
```bash
ngrok http 8501
```

ngrok will display output like:
```
Session Status                online
Account                       your-email@example.com (Plan: Free)
Forwarding                    https://abc123xyz.ngrok-free.app -> http://localhost:8501
```

**Copy the `https://....ngrok-free.app` URL** - this is your public URL.

## Step 5: Connect Devices

### Moderator (PC)
1. Open your browser on the PC
2. Go to the ngrok URL: `https://abc123xyz.ngrok-free.app`
3. Click "New Session" and create your experiment
4. A QR code will be generated automatically

### Subject (Tablet)
**Option A: Scan QR Code**
1. On the tablet, open the camera app
2. Scan the QR code displayed on the moderator screen
3. Tap the link to open in browser

**Option B: Enter Session Code**
1. On the tablet, open a browser
2. Go to the ngrok URL: `https://abc123xyz.ngrok-free.app`
3. Click "Join Session"
4. Enter the 6-character session code shown on the moderator screen

## Complete Workflow Example

### Quick Workflow (Recommended)
```
1. PC Terminal:      python start_robotaste.py
                     → Note the URL: https://abc123.ngrok-free.app

2. PC Browser:       Go to https://abc123.ngrok-free.app
                     → Create new session
                     → Configure experiment
                     → QR code appears

3. Tablet:           Scan QR code OR enter session code
                     → Subject interface loads
                     → Ready for experiment!

4. When done:        Press Ctrl+C in terminal to stop everything
```

### Manual Workflow (Advanced)

```
1. PC Terminal 1:    streamlit run main_app.py
2. PC Terminal 2:    python pump_control_service.py --db-path robotaste.db
3. PC Terminal 3:    ngrok http 8501
                     → Note the URL: https://abc123.ngrok-free.app

4. PC Browser:       Go to https://abc123.ngrok-free.app
                     → Create new session
                     → Configure experiment
                     → QR code appears

5. Tablet:           Scan QR code OR enter session code
                     → Subject interface loads
                     → Ready for experiment!
```

## Free Tier Limitations

| Limitation | Impact | Workaround |
|------------|--------|------------|
| URL changes on restart | QR code invalid after ngrok restart | Re-share new QR code with subjects |
| Session timeout (~2 hours) | Tunnel disconnects | Restart ngrok, create new session |
| ngrok branding page | First-time visitors see ngrok warning | Click "Visit Site" to continue |
| Slower routing | ~200-500ms latency added | **Moderator uses localhost, subjects use ngrok** |

## Performance Best Practices

### Recommended Setup
```
Moderator (PC):          http://localhost:8501         ← Fast, no latency
Subjects (tablet):       https://xxx.ngrok-free.app   ← Remote access
```

### Why This Works Best
- **Moderator** configures experiments on fast local connection
- **QR codes** automatically show ngrok URL for subjects
- **No latency** for moderator while setting up
- **Best experience** for both moderator and subjects

### ngrok Warning Page
When subjects first visit the ngrok URL, they may see a page saying "You are about to visit..." - this is normal. Click **"Visit Site"** to proceed to RoboTaste.

## Troubleshooting

### Cannot Access ngrok URL from Same Computer

**Symptom**: The ngrok URL (e.g., https://abc123.ngrok-free.app) doesn't load when opened on the host computer

**Common Causes & Solutions**:

1. **ngrok Warning Page (Most Common)**
   - **What you see**: "You are about to visit..." ngrok branding page
   - **Solution**: Click **"Visit Site"** button to proceed
   - This is normal for ngrok free tier on first visit
   - Cookie is set, subsequent visits are direct

2. **Browser Cache/Cookies**
   - **Solution**: 
     ```
     - Clear browser cache (Cmd+Shift+R on Mac, Ctrl+Shift+R on Windows)
     - Try incognito/private browsing mode
     - Try a different browser
     ```

3. **URL Still Works Correctly**
   - Even if you can't access ngrok URL on your computer, the launcher saves the URL to a file
   - QR codes and subject URLs will still use the ngrok URL automatically
   - Subjects on other devices can access it normally

4. **Workaround: Use localhost for moderator**
   - Moderator can access via `http://localhost:8501`
   - Subject URLs/QR codes will still show the ngrok URL correctly
   - This is actually the recommended workflow

### QR Code Points to localhost
**Symptom**: Scanning QR code opens localhost:8501 instead of ngrok URL

**Solution**: Make sure the moderator is accessing the app through the ngrok URL, not localhost. The QR code URL is based on how the moderator accessed the app.

### Subject Can't Connect
**Symptom**: Tablet shows "Unable to connect" or timeout

**Checklist**:
1. Is Streamlit running? Check Terminal 1
2. Is ngrok running? Check Terminal 3
3. Is the tablet connected to the internet?
4. Try opening the ngrok URL on the PC first to verify it works

### ngrok Session Expired
**Symptom**: ngrok shows "Session expired" or "Tunnel closed"

**Solution**: 
1. Stop ngrok (Ctrl+C in Terminal 3)
2. Restart: `ngrok http 8501`
3. Share the new URL with subjects (old QR codes won't work)

### "Session Not Found" Error
**Symptom**: Subject enters code but gets "Invalid session"

**Possible Causes**:
1. Session was created on a different ngrok URL
2. Session expired
3. Typo in session code

**Solution**: Create a new session from the moderator interface

### Slow Performance via ngrok

**Symptom**: App is slow/laggy when accessing via ngrok URL, but fast on localhost

**Cause**: ngrok free tier routing
- Traffic path: Your PC → ngrok cloud servers → back to your PC
- Free tier has lower priority and bandwidth
- Adds ~200-500ms latency per request

**Solutions**:

1. **Best: Moderator uses localhost, subjects use ngrok**
   ```
   Moderator (PC):    http://localhost:8501        (fast, no latency)
   Subjects (tablet): https://xxx.ngrok-free.app   (necessary for remote access)
   ```
   QR codes will still show the ngrok URL correctly.

2. **Reduce database polling** (if needed for long sessions)
   - Edit `robotaste/data/session_repo.py`
   - Change polling from 5 seconds to 10 seconds:
     ```python
     time.sleep(10)  # instead of time.sleep(5)
     ```

3. **Paid ngrok tier** ($8/month)
   - Faster routing
   - Reserved domain (no random URLs)
   - Better bandwidth

4. **Local Network Alternative** (if devices on same WiFi)
   ```bash
   # No ngrok needed - use PC's local IP
   streamlit run main_app.py --server.address 0.0.0.0
   # Access from tablet: http://YOUR_PC_IP:8501
   ```

### Session Not Found
**Symptom**: Subject enters code but gets "Invalid session"

**Possible Causes**:
1. Session was created on a different ngrok URL
2. Session expired
3. Typo in session code

**Solution**: Create a new session from the moderator interface

## Security Considerations

- **Session Codes**: 6-character codes provide basic access control
- **Public URL**: Anyone with the ngrok URL can access the landing page
- **Data**: All experiment data stays on your PC (SQLite database)
- **Recommendation**: Don't share the ngrok URL publicly; only share with intended participants

## Paid ngrok Options (Optional)

For production or frequent use, consider ngrok paid plans:

| Feature | Free | Paid ($8/mo+) |
|---------|------|---------------|
| Static URL | ❌ Changes each restart | ✅ Reserved domain |
| Sessions | ~2 hour timeout | Longer/unlimited |
| Branding | ngrok warning page | Custom domain |

With a reserved domain, you could use the same URL for every experiment session.

## Alternative: Local Network (No Internet Required)

If all devices are on the same WiFi network, you can skip ngrok:

1. Find your PC's local IP: `ifconfig | grep "inet "` (macOS) or `ipconfig` (Windows)
2. Start Streamlit with: `streamlit run main_app.py --server.address 0.0.0.0`
3. Access from tablet: `http://YOUR_PC_IP:8501`

**Note**: This only works when devices are on the same network.
