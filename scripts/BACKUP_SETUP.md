# Network backup setup (Windows)

`backup_to_network.py` snapshots the live database and mirrors `logs/` and
`protocols/` to a shared network folder, so any PC on the network can read the
latest data. `backup_to_network.bat` is the entry point for Task Scheduler.

## 1. Configure the destination

Edit `BACKUP_DEST` near the top of `scripts/backup_to_network.py`:

```python
_BACKUP_DEST_PLACEHOLDER = r"\\SERVER\Share\RoboTaste"
```

Replace it with your real UNC path, e.g. `\\FILESERVER\Lab\RoboTaste`. Alternatively,
leave the file alone and set the environment variable `ROBOTASTE_BACKUP_DEST` on the
Windows host (e.g. in the scheduled task's action, or via `setx`).

Other overridable settings (env vars, all optional):

| Variable | Default | Purpose |
|---|---|---|
| `ROBOTASTE_BACKUP_DEST` | placeholder above | destination share root |
| `ROBOTASTE_DB_PATH` | `<repo>\robotaste.db` | source DB (matches the main app's setting) |
| `ROBOTASTE_BACKUP_KEEP` | `30` | number of timestamped DB snapshots to retain |

**Important:** use the full UNC path (`\\server\share\...`), not a mapped drive letter
(`Z:\...`) — mapped drives are per-user and typically aren't available to a Task
Scheduler task running "whether user is logged on or not."

## 2. Confirm share permissions

The Windows account the scheduled task runs as needs read/write access to the share.
Test manually first:

```bat
cd C:\path\to\RoboTaste
scripts\backup_to_network.bat
```

Check the exit code (`echo %ERRORLEVEL%` — 0 means success) and confirm files appeared
under the share: `db\robotaste_latest.db`, `logs\`, `protocols\`, `backup.log`.

## 3. Register the scheduled task

GUI: Task Scheduler → Create Task…
- **General:** Run whether user is logged on or not; Run with highest privileges if needed.
- **Triggers:** New → Daily, e.g. 02:00.
- **Actions:** New → Start a program
  - Program/script: `C:\path\to\RoboTaste\scripts\backup_to_network.bat`
  - Start in: `C:\path\to\RoboTaste`
- **Settings:** "If the task fails, restart every 5 minutes, up to 3 times" is a
  reasonable default for a flaky network share.

Or from an elevated command prompt:

```bat
schtasks /Create /TN "RoboTaste Network Backup" ^
  /TR "\"C:\path\to\RoboTaste\scripts\backup_to_network.bat\"" ^
  /SC DAILY /ST 02:00 /RL HIGHEST /RU SYSTEM
```

(Use `/RU SYSTEM` only if the machine account itself has share access; otherwise use
`/RU "DOMAIN\user" /RP "password"` for a specific account with share permissions.)

## 4. Verify

- Run the task manually once: Task Scheduler → right-click the task → Run.
- Check **Last Run Result** = `0x0`.
- From a *different* PC on the network, open `\\server\share\RoboTaste\db\robotaste_latest.db`
  and confirm it opens and has recent data.
- Tail `\\server\share\RoboTaste\backup.log` for a history of run results.
