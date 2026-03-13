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

from app.config import settings
from app.database import supabase
from app.services.pdf_parser import parse_quote_pdf

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _download_slack_file(client: Any, file_id: str) -> bytes:
    """Fetch file info, then download the private URL using the bot token."""
    info_resp = client.files_info(file=file_id)
    file_info: Dict[str, Any] = info_resp["file"]

    url_private: str = file_info.get("url_private_download") or file_info.get("url_private", "")
    if not url_private:
        raise ValueError(f"No download URL found for file {file_id}")

    headers = {"Authorization": f"Bearer {settings.slack_bot_token}"}
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
    """Fire-and-forget broadcast to all connected WebSocket clients."""
    import asyncio
    from app.routers.ws import broadcast

    message = {
        "type": "new_order",
        "order_id": order_id,
        "client_name": client_name,
        "proforma_number": proforma_number,
    }
    try:
        loop = asyncio.get_event_loop()
        if loop.is_running():
            loop.create_task(broadcast(message))
        else:
            loop.run_until_complete(broadcast(message))
    except RuntimeError:
        asyncio.run(broadcast(message))
    except Exception as exc:
        logger.warning("WebSocket broadcast failed: %s", exc)


# ---------------------------------------------------------------------------
# Public entry point
# ---------------------------------------------------------------------------

def start_slack_bot() -> None:
    """
    Start the Slack bot using Socket Mode (no public URL needed).
    This is a blocking call — run it in a background daemon thread.

    ⚠️  The App is initialized HERE (not at module level) so that a bad
    Slack token cannot crash FastAPI before it even starts serving requests.
    """
    logger.info("Starting Slack bot in Socket Mode...")

    try:
        # --- lazy import to avoid crashing at module load time ---
        from slack_bolt import App
        from slack_bolt.adapter.socket_mode import SocketModeHandler

        app = App(
            token=settings.slack_bot_token,
            signing_secret=settings.slack_signing_secret,
        )

        # ── Event: file shared in a channel ──────────────────────────────
        @app.event("file_shared")
        def handle_file_shared(event: Dict[str, Any], say: Any, client: Any) -> None:
            file_id: str = event.get("file_id", "")
            channel_id: str = event.get("channel_id", "")
            message_ts: str = event.get("event_ts", "")

            logger.info("file_shared event: file_id=%s channel=%s", file_id, channel_id)

            try:
                info_resp = client.files_info(file=file_id)
                file_meta: Dict[str, Any] = info_resp["file"]
                filename: str = file_meta.get("name", "")
                mimetype: str = file_meta.get("mimetype", "")

                is_pdf = mimetype == "application/pdf" or filename.lower().endswith(".pdf")
                if not is_pdf:
                    logger.debug("Ignoring non-PDF file: %s (%s)", filename, mimetype)
                    return

                logger.info("Downloading PDF: %s", filename)
                pdf_bytes = _download_slack_file(client, file_id)

                logger.info("Parsing PDF (%d bytes)", len(pdf_bytes))
                parsed = parse_quote_pdf(pdf_bytes)

                order_id = _save_order_to_db(parsed, channel_id, message_ts)
                logger.info("Order saved: id=%s proforma=%s", order_id, parsed["proforma_number"])

                _broadcast_new_order(order_id, parsed["client_name"], parsed["proforma_number"])

                item_count = len(parsed.get("items", []))
                say(
                    channel=channel_id,
                    text=(
                        f"✅ Pedido *#{parsed['proforma_number']}* de *{parsed['client_name']}* recibido. "
                        f"Items extraídos: {item_count}. Bodega fue notificada."
                    ),
                )

            except Exception as exc:
                logger.error("Error handling file_shared: %s", exc, exc_info=True)
                try:
                    client.chat_postMessage(
                        channel=channel_id,
                        text=f"⚠️ No pude procesar el PDF. Error: {str(exc)[:200]}",
                    )
                except Exception as slack_err:
                    logger.error("Failed to post error message to Slack: %s", slack_err)

        # ── Catch-all for other message subtypes ─────────────────────────
        @app.event("message")
        def handle_message_events(event: Dict[str, Any], logger: Any) -> None:
            pass  # intentional no-op

        # ── Start Socket Mode handler ─────────────────────────────────────
        handler = SocketModeHandler(
            app=app,
            app_token=settings.slack_app_token,
        )
        handler.start()  # blocks until stopped

    except Exception as exc:
        # Log and exit gracefully — FastAPI will keep running without the bot
        logger.error(
            "Slack bot failed to start (FastAPI continues running): %s",
            exc,
            exc_info=True,
        )
