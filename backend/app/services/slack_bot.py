"""
slack_bot.py
============
Slack bot using slack_bolt with Socket Mode.

Listens for file_shared events in any channel the bot is invited to.
When a PDF is shared:
  1. Downloads the file via the Slack Files API.
  2. Parses it with pdf_parser.parse_quote_pdf().
  3. Saves the order + items to Supabase.
  4. Broadcasts a WebSocket notification to connected clients (e.g. audio daemon).
  5. Posts a confirmation (or error) message back to the Slack channel.
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any, Dict

import requests
from slack_bolt import App
from slack_bolt.adapter.socket_mode import SocketModeHandler

from app.config import settings
from app.database import supabase
from app.services.pdf_parser import parse_quote_pdf

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Slack app instance
# ---------------------------------------------------------------------------

_app = App(
    token=settings.slack_bot_token,
    signing_secret=settings.slack_signing_secret,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _download_slack_file(file_id: str, token: str) -> bytes:
    """Fetch file info, then download the private URL using the bot token."""
    # Retrieve file metadata
    info_resp = _app.client.files_info(file=file_id)
    file_info: Dict[str, Any] = info_resp["file"]

    url_private: str = file_info.get("url_private_download") or file_info.get("url_private", "")
    if not url_private:
        raise ValueError(f"No download URL found for file {file_id}")

    headers = {"Authorization": f"Bearer {token}"}
    response = requests.get(url_private, headers=headers, timeout=30)
    response.raise_for_status()
    return response.content


def _save_order_to_db(parsed: Dict[str, Any], channel_id: str, message_ts: str) -> str:
    """Insert order + order_items into Supabase. Returns the new order UUID."""
    now_iso = datetime.now(timezone.utc).isoformat()

    order_payload = {
        "proforma_number": parsed["proforma_number"],
        "client_name": parsed["client_name"],
        "status": "pending",
        "slack_channel_id": channel_id,
        "slack_message_ts": message_ts,
        "raw_text": "",
        "created_at": now_iso,
    }
    order_result = supabase.table("orders").insert(order_payload).execute()
    if not order_result.data:
        raise RuntimeError("Supabase returned no data after order insert")

    order_id: str = order_result.data[0]["id"]

    items_payload = [
        {
            "order_id": order_id,
            "sku": item.get("sku"),
            "description": item["description"],
            "quantity": item["quantity"],
            "unit": item.get("unit", "unidad"),
            "zone": item.get("zone", ""),
            "created_at": now_iso,
        }
        for item in parsed.get("items", [])
    ]
    if items_payload:
        supabase.table("order_items").insert(items_payload).execute()

    return order_id


def _broadcast_new_order(order_id: str, client_name: str, proforma_number: str) -> None:
    """
    Fire-and-forget broadcast to all connected WebSocket clients.
    Importing inside the function avoids circular import issues at startup.
    """
    import asyncio

    from app.routers.ws import broadcast

    message = {
        "type": "new_order",
        "order_id": order_id,
        "client_name": client_name,
        "proforma_number": proforma_number,
    }
    # The Slack bot runs in a regular (non-async) thread; we need to schedule
    # the coroutine on the running event loop.
    try:
        loop = asyncio.get_event_loop()
        if loop.is_running():
            loop.create_task(broadcast(message))
        else:
            loop.run_until_complete(broadcast(message))
    except RuntimeError:
        # No event loop in this thread — create a new one just for this call.
        asyncio.run(broadcast(message))
    except Exception as exc:
        logger.warning("WebSocket broadcast failed: %s", exc)


# ---------------------------------------------------------------------------
# Event handlers
# ---------------------------------------------------------------------------

@_app.event("file_shared")
def handle_file_shared(event: Dict[str, Any], say: Any, client: Any) -> None:
    """
    Called whenever a file is shared to a channel the bot is in.
    Only processes PDF files; silently ignores everything else.
    """
    file_id: str = event.get("file_id", "")
    channel_id: str = event.get("channel_id", "")
    message_ts: str = event.get("event_ts", "")

    logger.info("file_shared event: file_id=%s channel=%s", file_id, channel_id)

    try:
        # Get full file info to check mimetype / name
        info_resp = client.files_info(file=file_id)
        file_meta: Dict[str, Any] = info_resp["file"]
        filename: str = file_meta.get("name", "")
        mimetype: str = file_meta.get("mimetype", "")

        is_pdf = mimetype == "application/pdf" or filename.lower().endswith(".pdf")
        if not is_pdf:
            logger.debug("Ignoring non-PDF file: %s (%s)", filename, mimetype)
            return

        # Download
        logger.info("Downloading PDF: %s", filename)
        pdf_bytes = _download_slack_file(file_id, settings.slack_bot_token)

        # Parse
        logger.info("Parsing PDF (%d bytes)", len(pdf_bytes))
        parsed = parse_quote_pdf(pdf_bytes)

        # Persist
        order_id = _save_order_to_db(parsed, channel_id, message_ts)
        logger.info("Order saved: id=%s proforma=%s", order_id, parsed["proforma_number"])

        # Notify WebSocket clients (audio daemon etc.)
        _broadcast_new_order(order_id, parsed["client_name"], parsed["proforma_number"])

        # Confirm in Slack
        item_count = len(parsed.get("items", []))
        say(
            channel=channel_id,
            text=(
                f"Pedido #{parsed['proforma_number']} de {parsed['client_name']} recibido. "
                f"Items extraídos: {item_count}. Bodega fue notificada."
            ),
        )

    except Exception as exc:
        logger.error("Error handling file_shared event: %s", exc, exc_info=True)
        try:
            client.chat_postMessage(
                channel=channel_id,
                text=(
                    f"No pude procesar el archivo PDF. "
                    f"Error: {str(exc)[:200]}"
                ),
            )
        except Exception as slack_err:
            logger.error("Failed to post error message to Slack: %s", slack_err)


@_app.event("message")
def handle_message_events(event: Dict[str, Any], logger: Any) -> None:
    """
    Catch-all for message subtypes so slack_bolt doesn't log unhandled warnings.
    We only care about file_shared, not generic messages.
    """
    pass  # intentionally no-op


# ---------------------------------------------------------------------------
# Public entry point
# ---------------------------------------------------------------------------

def start_slack_bot() -> None:
    """
    Start the Slack bot using Socket Mode (no public URL / ngrok needed).
    This is a blocking call — run it in a background daemon thread.
    """
    logger.info("Starting Slack bot in Socket Mode...")
    try:
        handler = SocketModeHandler(
            app=_app,
            app_token=settings.slack_app_token,
        )
        handler.start()  # blocks until the bot is stopped
    except Exception as exc:
        logger.error("Slack bot crashed: %s", exc, exc_info=True)
