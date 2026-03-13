"""
notifier.py
===========
Sends a Slack message to the warehouse notification channel when an order
is marked as completed.
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from app.config import settings

logger = logging.getLogger(__name__)


def _get_slack_client():
    """Lazy init — evita crash al importar si el token es inválido."""
    from slack_sdk import WebClient
    return WebClient(token=settings.slack_bot_token)


def _calc_prep_minutes(order: Dict[str, Any]) -> Optional[int]:
    """Return elapsed minutes between created_at and completed_at, or None."""
    try:
        created_raw = order.get("created_at")
        completed_raw = order.get("completed_at")
        if not created_raw or not completed_raw:
            return None

        def _parse(ts: Any) -> datetime:
            if isinstance(ts, datetime):
                return ts
            # ISO string — handle with or without timezone info
            s = str(ts)
            # Python's fromisoformat doesn't handle trailing 'Z' before 3.11
            s = s.replace("Z", "+00:00")
            return datetime.fromisoformat(s)

        created_dt = _parse(created_raw)
        completed_dt = _parse(completed_raw)

        # Make both timezone-aware for safe subtraction
        if created_dt.tzinfo is None:
            created_dt = created_dt.replace(tzinfo=timezone.utc)
        if completed_dt.tzinfo is None:
            completed_dt = completed_dt.replace(tzinfo=timezone.utc)

        delta = completed_dt - created_dt
        return max(0, int(delta.total_seconds() / 60))
    except Exception as exc:
        logger.warning("Could not calculate prep time: %s", exc)
        return None


async def send_order_completed(
    order: Dict[str, Any],
    items: Optional[List[Dict[str, Any]]] = None,
) -> None:
    """
    Post a Slack message to the notification channel announcing that an order
    is ready for dispatch.

    Parameters
    ----------
    order : dict
        Raw order row from Supabase (must include proforma_number, client_name,
        completed_by, created_at, completed_at).
    items : list[dict] | None
        Order items rows (used to compute the item count).
    """
    proforma_number = order.get("proforma_number", "N/A")
    client_name = order.get("client_name", "N/A")
    completed_by = order.get("completed_by") or "N/A"
    item_count = len(items) if items is not None else 0

    prep_minutes = _calc_prep_minutes(order)
    prep_str = f"{prep_minutes} min" if prep_minutes is not None else "N/A"

    message = (
        f"*Pedido listo para despacho*\n"
        f"Proforma: #{proforma_number}\n"
        f"Cliente: {client_name}\n"
        f"Items: {item_count}\n"
        f"Preparado en: {prep_str}\n"
        f"Por: {completed_by}"
    )

    try:
        from slack_sdk.errors import SlackApiError

        client = _get_slack_client()
        response = client.chat_postMessage(
            channel=settings.slack_notify_channel,
            text=message,
            # Also supply blocks for richer formatting in modern Slack clients
            blocks=[
                {
                    "type": "section",
                    "text": {
                        "type": "mrkdwn",
                        "text": message,
                    },
                }
            ],
        )
        logger.info(
            "Slack notification sent for proforma #%s — ts=%s",
            proforma_number,
            response.get("ts"),
        )
    except SlackApiError as exc:
        logger.error(
            "Slack API error while sending completion notification: %s — %s",
            exc.response["error"],
            exc,
        )
        # Don't re-raise — Slack failure must not block order completion
    except Exception as exc:
        logger.error("Unexpected error sending Slack notification: %s", exc, exc_info=True)
        # Don't re-raise — Slack failure must not block order completion
