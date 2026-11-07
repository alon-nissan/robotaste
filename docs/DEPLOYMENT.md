# Making RoboTaste Reachable Over the Web

RoboTaste normally runs on a lab computer, and tablets connect over WiFi or Tailscale
(see [MULTI_DEVICE_SETUP.md](MULTI_DEVICE_SETUP.md)). This guide covers two other setups:

1. **Quick public link from your laptop**, using a Cloudflare tunnel. It is free, needs no
   account, and keeps all data on your laptop. Use it for demos.
2. **A permanent server**, such as a university VM running Docker. Use it for long-running or
   real-data deployments.

> **Pumps:** both setups suit the **pumpless / hand-served** (questionnaire-only) mode.
> Pump hardware must be plugged into the computer that runs `pump_control_service.py`.
> Option 1 still supports `--with-pump` when the laptop is connected to the pumps.

---

## ⚠️ Privacy first

- **Always set a password when the app is reachable from the internet.** Without one, anyone
  who has the URL can open the moderator page and download all session data.
- **Use demo or test data only** on a laptop tunnel or a commercial cloud.
- **Real participant data** belongs on university-controlled infrastructure. It also needs
  whatever your ethics (IRB/Helsinki) approval and data-protection rules require.
- Use pseudonymous subject IDs. Do not enter names, emails or phone numbers.
- The SQLite file (`robotaste.db`) **is** the data. Back it up, and delete it when you are
  supposed to.

---

## Option 1: Public link from your laptop (Cloudflare quick tunnel)

### How it works
`cloudflared` opens an outgoing connection from your laptop to Cloudflare. Cloudflare then
gives you a random `https://<words>.trycloudflare.com` address that forwards to RoboTaste on
your laptop.
- Tablets can be on **any** network, including mobile data, so you don't need to share WiFi
  or use Tailscale.
- No ports are opened on your router or the university network.
- Data never leaves your laptop. Cloudflare only relays the encrypted traffic.

### One-time setup
Install `cloudflared` (free, open source, no account needed):

macOS (Homebrew):
```bash
brew install cloudflared
```

Windows (PowerShell or Command Prompt):
```bash
winget install --id Cloudflare.cloudflared
```

Close and reopen the terminal afterwards so `cloudflared` is on your PATH. Check it works with
`cloudflared --version`.

### Each time you run a demo
From the RoboTaste folder:

```bash
python start_new_ui.py --tunnel --password choose-a-password
```

Add `--with-pump` if the pumps are connected. The launcher then:
1. builds the frontend if needed,
2. starts the tunnel and prints the public URL,
3. starts the server, and
4. prints the **moderator URL**, the **subject URL** and a **QR code** for the tablet.

When the browser asks you to log in, use:
- **Username:** `robotaste` (change it with the `ROBOTASTE_USER` environment variable)
- **Password:** whatever you passed to `--password`

Each device asks only once. On the moderator page, the *Subject Connection* card shows the
same public link and QR code.

### Demo-day checklist
- [ ] Laptop is **plugged in** and **will not sleep**:
  - macOS: run `caffeinate -dis` in a second terminal window, or use System Settings → Battery.
  - Windows: Settings → System → Power → Screen and sleep → *Never* while plugged in.
- [ ] Laptop has internet. Venue WiFi is fine, and a phone hotspot is a good backup.
- [ ] Started with `--password`.
- [ ] Opened the public URL on the tablet once before the demo and logged in.
- [ ] Loaded a pumpless protocol, e.g. `protocols/questionnaire_only_example.json`.

### Things to know
- **The URL changes every time you restart.** Re-scan the QR code after a restart.
- Quick tunnels are meant for testing and demos. Cloudflare gives no uptime guarantee.
  For a stable URL, use a named tunnel (needs a free Cloudflare account and a domain) or
  Option 2.
- If the tunnel never prints a URL, check `logs/cloudflared_process.log`. Some
  networks block the outgoing connection that cloudflared needs. Try a phone hotspot.

### Alternative: Tailscale Funnel
If you already use Tailscale, `tailscale funnel 8000` publishes the app on a stable
`https://<machine>.<tailnet>.ts.net` URL. Funnel must be enabled for your tailnet in the
Tailscale admin console. Start RoboTaste with
`ROBOTASTE_PASSWORD=... python start_new_ui.py` so the app is password protected.

---

## Option 2: Permanent server (Docker)

The `Dockerfile` in the repo root builds one image that contains the API and the built
frontend. It runs on any Linux server with Docker, such as a university VM.

```bash
docker build -t robotaste .
```

```bash
docker run -d --name robotaste --restart unless-stopped \
  -p 127.0.0.1:8000:8000 \
  -v /srv/robotaste:/data \
  -e ROBOTASTE_PASSWORD=change-me \
  -e ROBOTASTE_PUBLIC_URL=https://robotaste.example.ac.il \
  robotaste
```

- The database lives in the mounted volume, at `/srv/robotaste/robotaste.db` on the host,
  so it survives container upgrades. Back up that file by copying it while the container is
  stopped, or with `sqlite3 robotaste.db ".backup backup.db"`.
- Put a reverse proxy with HTTPS in front, e.g. Caddy (`reverse_proxy 127.0.0.1:8000`) or nginx,
  and ask university IT for a hostname and certificate.
- The image runs a single uvicorn worker on purpose, because SQLite needs a single writer.
- Health check: `GET /api/health`, which is never password protected.

To upgrade:

```bash
git pull && docker build -t robotaste . && docker rm -f robotaste
```

Then run the same `docker run …` command again.

---

## Configuration reference

| Environment variable | Default | Purpose |
|---|---|---|
| `ROBOTASTE_PASSWORD` | *(unset = no login)* | Require HTTP Basic login on every page and API call (except `/api/health`). |
| `ROBOTASTE_USER` | `robotaste` | Username for the login above. |
| `ROBOTASTE_PUBLIC_URL` | *(auto)* | Public base URL shown in the subject link and QR code. It is set automatically by `--tunnel`. If unset, the app uses the domain the moderator browsed to, falling back to the LAN/Tailscale IP. |
| `ROBOTASTE_DB_PATH` | `./robotaste.db` | Location of the SQLite database (`/data/robotaste.db` in Docker). |
