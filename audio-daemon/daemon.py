#!/usr/bin/env python3
"""
Warehouse Audio Daemon
Plays alert sounds when new orders arrive.
Runs on bodega PC - cross-platform (Windows/Mac/Linux)

Usage:
    python daemon.py
    Configure via .env file or environment variables.
"""

import asyncio
import json
import logging
import os
import platform
import sys
import time
from datetime import datetime
from pathlib import Path

import requests
import websockets
from colorama import Fore, Style, init as colorama_init
from dotenv import load_dotenv

# ---------------------------------------------------------------------------
# Bootstrap: load .env from the directory containing this script
# ---------------------------------------------------------------------------

SCRIPT_DIR = Path(__file__).resolve().parent
load_dotenv(SCRIPT_DIR / ".env")

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

VPS_HOST: str = os.getenv("VPS_HOST", "http://127.0.0.1:8000").rstrip("/")
WS_PATH: str = os.getenv("WS_PATH", "/ws")
POLL_INTERVAL: int = int(os.getenv("POLL_INTERVAL", "60"))
SOUND_FILE: Path = SCRIPT_DIR / os.getenv("SOUND_FILE", "sounds/nuevo_pedido.mp3")
DAEMON_SECRET: str = os.getenv("DAEMON_SECRET", "")
RECONNECT_DELAY_INITIAL: float = float(os.getenv("RECONNECT_DELAY_SECONDS", "5"))
RECONNECT_DELAY_MAX: float = 120.0  # never wait more than 2 minutes
STATUS_INTERVAL: int = 10  # seconds between status prints

# Derive WebSocket URL from VPS_HOST
def _build_ws_url(host: str, path: str) -> str:
    """Convert http(s):// prefix to ws(s):// and append path."""
    if host.startswith("https://"):
        return "wss://" + host[len("https://"):] + path
    if host.startswith("http://"):
        return "ws://" + host[len("http://"):] + path
    # No scheme supplied – default to ws
    return "ws://" + host + path

WS_URL: str = _build_ws_url(VPS_HOST, WS_PATH)
ORDERS_URL: str = f"{VPS_HOST}/api/orders/pending-count"

# ---------------------------------------------------------------------------
# Logging – plain text to file, coloured to stdout handled manually
# ---------------------------------------------------------------------------

logging.basicConfig(
    level=logging.WARNING,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[
        logging.FileHandler(SCRIPT_DIR / "daemon.log", encoding="utf-8"),
    ],
)
logger = logging.getLogger("warehouse-daemon")

# ---------------------------------------------------------------------------
# Coloured terminal helpers
# ---------------------------------------------------------------------------

colorama_init(autoreset=True)


def _ts() -> str:
    return datetime.now().strftime("%H:%M:%S")


def log_info(msg: str) -> None:
    print(f"{Fore.CYAN}[{_ts()}] {msg}{Style.RESET_ALL}", flush=True)


def log_ok(msg: str) -> None:
    print(f"{Fore.GREEN}[{_ts()}] {msg}{Style.RESET_ALL}", flush=True)


def log_warn(msg: str) -> None:
    print(f"{Fore.YELLOW}[{_ts()}] WARNING: {msg}{Style.RESET_ALL}", flush=True)


def log_error(msg: str) -> None:
    print(f"{Fore.RED}[{_ts()}] ERROR: {msg}{Style.RESET_ALL}", flush=True)


def log_alert(msg: str) -> None:
    print(f"{Fore.MAGENTA}{Style.BRIGHT}[{_ts()}] *** {msg} ***{Style.RESET_ALL}", flush=True)


# ---------------------------------------------------------------------------
# Audio subsystem
# ---------------------------------------------------------------------------

_pygame_ok: bool = False
_sound_obj = None  # pygame.mixer.Sound instance, if loaded


def _init_audio() -> None:
    """Initialise pygame mixer. Gracefully degrade if unavailable."""
    global _pygame_ok, _sound_obj

    try:
        import pygame  # noqa: PLC0415
        pygame.mixer.init()
        _pygame_ok = True
        log_ok("Audio initialised via pygame.")
    except Exception as exc:  # noqa: BLE001
        log_warn(f"pygame unavailable ({exc}). Will use system beep fallback.")
        return

    if not SOUND_FILE.exists():
        log_warn(
            f"Sound file not found: {SOUND_FILE}\n"
            "    Place nuevo_pedido.mp3 in the sounds/ directory.\n"
            "    Falling back to system beep."
        )
        _pygame_ok = False
        return

    try:
        import pygame  # noqa: PLC0415
        _sound_obj = pygame.mixer.Sound(str(SOUND_FILE))
        log_ok(f"Sound loaded: {SOUND_FILE.name}")
    except Exception as exc:  # noqa: BLE001
        log_warn(f"Could not load sound file ({exc}). Falling back to system beep.")
        _pygame_ok = False


def _play_sound() -> None:
    """Play the alert sound (or a fallback beep)."""
    if _pygame_ok and _sound_obj is not None:
        try:
            _sound_obj.play()
            return
        except Exception as exc:  # noqa: BLE001
            log_warn(f"pygame playback failed ({exc}). Falling back to beep.")

    # Fallback
    _system_beep()


def _system_beep() -> None:
    """Cross-platform terminal / system beep."""
    system = platform.system()
    if system == "Windows":
        try:
            import winsound  # noqa: PLC0415
            winsound.Beep(1000, 400)  # 1 kHz, 400 ms
            return
        except Exception:  # noqa: BLE001
            pass
    # Mac / Linux: write BEL character
    sys.stdout.write("\a")
    sys.stdout.flush()


# ---------------------------------------------------------------------------
# Shared state
# ---------------------------------------------------------------------------

class DaemonState:
    """Thread-safe (asyncio-safe) shared state for the three tasks."""

    def __init__(self) -> None:
        self.ws_connected: bool = False
        self.pending_count: int = 0
        self.last_order_at: datetime | None = None
        self.last_poll_at: datetime | None = None
        self.last_sound_at: datetime | None = None
        self.reconnect_attempts: int = 0
        self.total_orders_received: int = 0

        # Event set whenever a new order is detected (WS or polling → count > 0)
        self.alert_event: asyncio.Event = asyncio.Event()
        # Shutdown flag
        self.running: bool = True

    def trigger_alert(self, source: str = "websocket") -> None:
        log_alert(f"NEW ORDER DETECTED via {source}!")
        self.last_order_at = datetime.now()
        self.total_orders_received += 1
        self.alert_event.set()

    def status_line(self) -> str:
        ws_status = (
            f"{Fore.GREEN}CONNECTED{Style.RESET_ALL}"
            if self.ws_connected
            else f"{Fore.RED}DISCONNECTED{Style.RESET_ALL}"
        )
        last_order = (
            self.last_order_at.strftime("%H:%M:%S") if self.last_order_at else "none yet"
        )
        last_poll = (
            self.last_poll_at.strftime("%H:%M:%S") if self.last_poll_at else "never"
        )
        return (
            f"WS: {ws_status} | "
            f"Pending: {Fore.YELLOW}{self.pending_count}{Style.RESET_ALL} | "
            f"Last order: {last_order} | "
            f"Last poll: {last_poll} | "
            f"Total received: {self.total_orders_received}"
        )


# ---------------------------------------------------------------------------
# Task 1 – WebSocket listener
# ---------------------------------------------------------------------------

async def websocket_listener(state: DaemonState) -> None:
    """
    Maintains a persistent WebSocket connection to the VPS.
    Triggers an alert whenever a {"type": "new_order"} message is received.
    Uses exponential backoff on reconnection.
    """
    delay = RECONNECT_DELAY_INITIAL

    while state.running:
        try:
            headers = {}
            if DAEMON_SECRET:
                headers["X-Daemon-Secret"] = DAEMON_SECRET

            log_info(f"Connecting to WebSocket: {WS_URL}")
            async with websockets.connect(
                WS_URL,
                additional_headers=headers,
                ping_interval=30,
                ping_timeout=10,
                close_timeout=5,
            ) as ws:
                state.ws_connected = True
                state.reconnect_attempts = 0
                delay = RECONNECT_DELAY_INITIAL
                log_ok("WebSocket connected.")

                async for raw in ws:
                    if not state.running:
                        break
                    try:
                        msg = json.loads(raw)
                    except json.JSONDecodeError:
                        log_warn(f"Received non-JSON WebSocket message: {raw!r}")
                        continue

                    msg_type = msg.get("type", "")
                    if msg_type == "new_order":
                        state.trigger_alert(source="WebSocket")
                    elif msg_type == "ping":
                        # Server keepalive ping – nothing to do; websockets library
                        # handles protocol-level pings automatically.
                        pass
                    else:
                        logger.debug("Unknown WS message type: %s", msg_type)

        except (websockets.exceptions.ConnectionClosedError,
                websockets.exceptions.ConnectionClosedOK) as exc:
            state.ws_connected = False
            log_warn(f"WebSocket connection closed: {exc}")
        except OSError as exc:
            state.ws_connected = False
            log_error(f"WebSocket network error: {exc}")
        except Exception as exc:  # noqa: BLE001
            state.ws_connected = False
            log_error(f"WebSocket unexpected error: {exc}")
            logger.exception("WebSocket unexpected error")

        if not state.running:
            break

        state.reconnect_attempts += 1
        log_warn(
            f"Reconnecting in {delay:.0f}s "
            f"(attempt #{state.reconnect_attempts})..."
        )
        await asyncio.sleep(delay)
        delay = min(delay * 2, RECONNECT_DELAY_MAX)

    log_info("WebSocket listener stopped.")


# ---------------------------------------------------------------------------
# Task 2 – REST polling loop
# ---------------------------------------------------------------------------

async def polling_loop(state: DaemonState) -> None:
    """
    Polls GET /api/orders/pending-count every POLL_INTERVAL seconds.
    Updates state.pending_count and triggers an alert if count > 0.
    """
    session = requests.Session()
    if DAEMON_SECRET:
        session.headers["X-Daemon-Secret"] = DAEMON_SECRET

    while state.running:
        try:
            resp = await asyncio.get_event_loop().run_in_executor(
                None,
                lambda: session.get(ORDERS_URL, timeout=10),
            )
            resp.raise_for_status()
            data = resp.json()

            # Accept both {"count": N} and plain integer responses
            if isinstance(data, int):
                count = data
            elif isinstance(data, dict):
                count = int(
                    data.get("count")
                    or data.get("pending_count")
                    or data.get("total")
                    or 0
                )
            else:
                count = 0

            prev_count = state.pending_count
            state.pending_count = count
            state.last_poll_at = datetime.now()

            if count > 0 and prev_count == 0:
                # Count just went from 0 → positive: trigger alert
                state.trigger_alert(source="polling")
            elif count == 0 and prev_count > 0:
                log_ok("All orders cleared – stopping repeat alert.")
                state.alert_event.clear()
            elif count > 0:
                # Still has orders; ensure event stays set so sound loop continues
                state.alert_event.set()

        except requests.exceptions.RequestException as exc:
            log_warn(f"Polling error: {exc}")
        except (ValueError, KeyError) as exc:
            log_warn(f"Polling response parse error: {exc}")
        except Exception as exc:  # noqa: BLE001
            log_error(f"Polling unexpected error: {exc}")
            logger.exception("Polling unexpected error")

        # Wait POLL_INTERVAL seconds, checking running flag every second
        for _ in range(POLL_INTERVAL):
            if not state.running:
                break
            await asyncio.sleep(1)

    log_info("Polling loop stopped.")


# ---------------------------------------------------------------------------
# Task 3 – Sound alert loop
# ---------------------------------------------------------------------------

async def sound_loop(state: DaemonState) -> None:
    """
    Waits for state.alert_event, plays sound immediately, then repeats
    every POLL_INTERVAL seconds while pending_count > 0.
    """
    while state.running:
        # Block until an alert is triggered
        try:
            await asyncio.wait_for(state.alert_event.wait(), timeout=1.0)
        except asyncio.TimeoutError:
            continue

        if not state.running:
            break

        # Play the sound now
        log_alert("Playing alert sound!")
        await asyncio.get_event_loop().run_in_executor(None, _play_sound)
        state.last_sound_at = datetime.now()

        # Repeat every POLL_INTERVAL seconds while there are pending orders
        while state.running and state.pending_count > 0:
            # Wait POLL_INTERVAL seconds
            waited = 0
            while state.running and waited < POLL_INTERVAL and state.pending_count > 0:
                await asyncio.sleep(1)
                waited += 1

            if state.running and state.pending_count > 0:
                log_alert(
                    f"Repeating alert – {state.pending_count} order(s) still pending."
                )
                await asyncio.get_event_loop().run_in_executor(None, _play_sound)
                state.last_sound_at = datetime.now()

        # Clear event only if pending count is 0
        if state.pending_count == 0:
            state.alert_event.clear()

    log_info("Sound loop stopped.")


# ---------------------------------------------------------------------------
# Task 4 – Status display
# ---------------------------------------------------------------------------

async def status_display(state: DaemonState) -> None:
    """Prints a status line every STATUS_INTERVAL seconds."""
    separator = "-" * 70
    while state.running:
        print(f"\n{Fore.BLUE}{separator}{Style.RESET_ALL}")
        print(f"  {state.status_line()}")
        print(f"{Fore.BLUE}{separator}{Style.RESET_ALL}\n", flush=True)

        for _ in range(STATUS_INTERVAL):
            if not state.running:
                break
            await asyncio.sleep(1)

    log_info("Status display stopped.")


# ---------------------------------------------------------------------------
# Main entry point
# ---------------------------------------------------------------------------

async def main() -> None:
    print(
        f"\n{Fore.CYAN}{Style.BRIGHT}"
        "╔══════════════════════════════════════════╗\n"
        "║    Warehouse Audio Daemon  v1.0          ║\n"
        "║    Agentes Luxury                        ║\n"
        "╚══════════════════════════════════════════╝"
        f"{Style.RESET_ALL}\n"
    )

    log_info(f"VPS host  : {VPS_HOST}")
    log_info(f"WebSocket : {WS_URL}")
    log_info(f"REST poll : {ORDERS_URL} every {POLL_INTERVAL}s")
    log_info(f"Sound file: {SOUND_FILE}")
    log_info(f"Secret    : {'set' if DAEMON_SECRET else 'not set'}")
    print()

    _init_audio()

    state = DaemonState()

    print()
    log_info("Starting daemon tasks. Press Ctrl+C to stop.\n")

    tasks = [
        asyncio.create_task(websocket_listener(state), name="ws-listener"),
        asyncio.create_task(polling_loop(state), name="poller"),
        asyncio.create_task(sound_loop(state), name="sound"),
        asyncio.create_task(status_display(state), name="status"),
    ]

    try:
        await asyncio.gather(*tasks)
    except asyncio.CancelledError:
        pass
    finally:
        state.running = False
        for task in tasks:
            task.cancel()
        # Wait briefly for graceful shutdown
        await asyncio.gather(*tasks, return_exceptions=True)
        log_info("Daemon stopped. Goodbye.")


def run() -> None:
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        # Clean shutdown on Ctrl+C
        print(f"\n{Fore.YELLOW}Interrupt received – shutting down…{Style.RESET_ALL}")


if __name__ == "__main__":
    run()
