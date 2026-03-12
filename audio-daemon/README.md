# Warehouse Audio Daemon

A lightweight Python daemon that runs on the bodega (warehouse) PC and plays an audio alert whenever new orders arrive from the VPS. Works on Windows, macOS, and Linux.

---

## How It Works

The daemon runs three concurrent background tasks:

| Task | Description |
|---|---|
| **WebSocket listener** | Maintains a persistent connection to `ws://VPS_HOST/ws`. Triggers an alert immediately when it receives `{"type": "new_order", ...}`. Reconnects automatically with exponential backoff if the connection drops. |
| **REST polling** | Calls `GET http://VPS_HOST/api/orders/pending-count` every 60 seconds. Triggers an alert if `count > 0` goes from zero, and clears the alert when count reaches 0. |
| **Sound loop** | Plays the alert sound once immediately on trigger, then repeats every 60 seconds while pending orders exist. Stops automatically when the count reaches 0. |

A fourth task prints a colour-coded status line to the terminal every 10 seconds.

---

## Requirements

- Python 3.11 or newer
- A working audio output device (or the system beep fallback will be used)

---

## Installation

### 1. Clone / copy the files

Place the `audio-daemon/` directory on the bodega PC.

### 2. Install Python dependencies

```bash
cd audio-daemon
pip install -r requirements.txt
```

On Linux you may also need the SDL2 audio library:

```bash
sudo apt install libsdl2-mixer-2.0-0   # Debian / Ubuntu
sudo yum install SDL2_mixer             # CentOS / RHEL
```

### 3. Add your alert sound

Copy your alert audio file into the `sounds/` directory:

```
audio-daemon/
└── sounds/
    └── nuevo_pedido.mp3   ← put your file here
```

See `sounds/README.txt` for supported formats and tips.

---

## Configuration

Copy `.env.example` to `.env` and edit it:

```bash
cp .env.example .env
```

```dotenv
# .env
VPS_HOST=http://203.0.113.42:8000      # required – your VPS address
WS_PATH=/ws                             # optional, default /ws
POLL_INTERVAL=60                        # optional, seconds between REST polls
SOUND_FILE=sounds/nuevo_pedido.mp3     # optional, path to sound file
DAEMON_SECRET=                          # optional, sent as X-Daemon-Secret header
RECONNECT_DELAY_SECONDS=5              # optional, initial WS reconnect delay
```

The `.env` file must be in the same directory as `daemon.py` (or the compiled executable).

---

## Running Directly with Python

```bash
python daemon.py
```

Press `Ctrl+C` to stop gracefully.

---

## Building a Standalone Executable (PyInstaller)

A standalone executable lets you run the daemon on machines that do not have Python installed.

### Windows

```bat
build_windows.bat
```

Output: `dist\bodega-daemon.exe`

Copy the entire `sounds\` folder next to the `.exe` before distributing.

### macOS

```bash
chmod +x build_mac.sh
./build_mac.sh
```

Output: `dist/bodega-daemon`

### Linux

```bash
chmod +x build_linux.sh
./build_linux.sh
```

Output: `dist/bodega-daemon`

After building, the `sounds/` folder is bundled inside the binary. You only need to distribute:

- The single executable (`bodega-daemon` or `bodega-daemon.exe`)
- The `.env` file (placed next to the executable)

---

## Auto-Start on Windows (Task Scheduler)

1. Open **Task Scheduler** (`taskschd.msc`).
2. Click **Create Basic Task**.
3. Name it `Warehouse Daemon`.
4. Trigger: **When the computer starts**.
5. Action: **Start a program**.
   - Program: `C:\bodega\bodega-daemon.exe`
   - Start in: `C:\bodega\`
6. Finish. Check **Run whether user is logged on or not** if needed.

Alternatively, use the Windows `sc` command to create a proper service (requires [NSSM](https://nssm.cc/)):

```bat
nssm install WarehouseDaemon "C:\bodega\bodega-daemon.exe"
nssm set WarehouseDaemon AppDirectory "C:\bodega"
nssm start WarehouseDaemon
```

---

## Auto-Start on Linux (systemd)

Create the service file at `/etc/systemd/system/warehouse-daemon.service`:

```ini
[Unit]
Description=Warehouse Audio Daemon
After=network.target sound.target

[Service]
Type=simple
User=bodega
WorkingDirectory=/opt/warehouse-daemon
ExecStart=/opt/warehouse-daemon/bodega-daemon
Restart=on-failure
RestartSec=10
Environment=DISPLAY=:0
Environment=PULSE_SERVER=unix:/run/user/1000/pulse/native

[Install]
WantedBy=multi-user.target
```

Enable and start:

```bash
sudo systemctl daemon-reload
sudo systemctl enable warehouse-daemon
sudo systemctl start warehouse-daemon

# Check status
sudo systemctl status warehouse-daemon

# Watch live logs
journalctl -fu warehouse-daemon
```

> **Note:** On a desktop Linux PC without a logged-in user session, audio output requires pointing `PULSE_SERVER` (or `ALSA_CARD`) at the correct audio server. Adjust the `Environment=` lines to match your setup.

---

## Auto-Start on macOS (launchd)

Create `~/Library/LaunchAgents/com.agentesluxury.warehouse-daemon.plist`:

```xml
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN"
  "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>Label</key>
    <string>com.agentesluxury.warehouse-daemon</string>
    <key>ProgramArguments</key>
    <array>
        <string>/Users/bodega/warehouse-daemon/bodega-daemon</string>
    </array>
    <key>WorkingDirectory</key>
    <string>/Users/bodega/warehouse-daemon</string>
    <key>RunAtLoad</key>
    <true/>
    <key>KeepAlive</key>
    <true/>
    <key>StandardOutPath</key>
    <string>/Users/bodega/warehouse-daemon/daemon-stdout.log</string>
    <key>StandardErrorPath</key>
    <string>/Users/bodega/warehouse-daemon/daemon-stderr.log</string>
</dict>
</plist>
```

Load it:

```bash
launchctl load ~/Library/LaunchAgents/com.agentesluxury.warehouse-daemon.plist
```

---

## VPS API Contract

The daemon expects the following from the VPS:

### WebSocket – `ws://VPS_HOST/ws`

Messages from server to daemon:

```json
{ "type": "new_order", "order_id": "...", "..." : "..." }
```

Any message with `"type": "new_order"` triggers an immediate alert.

### REST – `GET /api/orders/pending-count`

Expected response (JSON):

```json
{ "count": 3 }
```

Also accepted: `{ "pending_count": 3 }`, `{ "total": 3 }`, or a plain integer `3`.

### Authentication (optional)

If `DAEMON_SECRET` is set, every request includes the header:

```
X-Daemon-Secret: <value>
```

---

## Logs

The daemon writes a log file to `daemon.log` in its working directory. Coloured status output goes to the terminal (stdout). If running as a service, redirect stdout to a file via the service manager.

---

## Troubleshooting

| Symptom | Fix |
|---|---|
| "Sound file not found" warning | Place `nuevo_pedido.mp3` in `sounds/` next to the executable. |
| No sound on Linux | Install `libsdl2-mixer-2.0-0`; check `PULSE_SERVER` environment variable. |
| WebSocket keeps reconnecting | Verify `VPS_HOST` in `.env`; check VPS firewall; confirm `/ws` endpoint is live. |
| `ModuleNotFoundError` | Run `pip install -r requirements.txt` in the same Python environment. |
| Daemon exits immediately | Check `daemon.log` for the error message. |
