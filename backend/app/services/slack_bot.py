"""
slack_bot.py
============
Bot de Slack para el sistema de bodega de Luxury Lights.

FLUJO:
  1. Alguien escribe "@yader enviá esto a bodega" y adjunta un PDF.
  2. El bot responde inmediatamente con un mensaje de "Analizando…".
  3. Descarga y parsea el PDF.
  4. Edita el mensaje a "✅ Análisis completo".
  5. Postea un resumen interactivo con los ítems agrupados por zona.
  6. El usuario puede:
     - ✅ "Confirmar y enviar a bodega" → cambia el pedido a "pending"
       y notifica a bodega.
     - ✏️ "Editar" → abre un modal de edición con nombre de cliente
       e ítems en formato texto.
  7. Al confirmar el modal, actualiza el pedido en Supabase y re-postea
     el resumen corregido.

REQUISITOS EN LA APP DE SLACK:
  - Socket Mode habilitado.
  - Scopes: app_mentions:read, chat:write, files:read, channels:history,
            groups:history, im:history, mpim:history.
  - Event subscriptions: app_mention, message.im.
"""

from __future__ import annotations

import json
import logging
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

import requests

from app.config import settings
from app.database import supabase
from app.services.pdf_parser import parse_quote_pdf

logger = logging.getLogger(__name__)


# ============================================================================
# Block builders
# ============================================================================

def _analyzing_blocks(filename: str) -> List[Dict]:
    """Mensaje inicial mientras se procesa el PDF."""
    return [
        {
            "type": "section",
            "text": {
                "type": "mrkdwn",
                "text": (
                    f"🔄 *Analizando cotización* `{filename}`\n"
                    "_Extrayendo ítems, zonas y cantidades…_"
                ),
            },
        }
    ]


def _analysis_done_blocks(filename: str, proforma: str, client_name: str, item_count: int) -> List[Dict]:
    """Reemplaza el mensaje de análisis cuando termina."""
    return [
        {
            "type": "section",
            "text": {
                "type": "mrkdwn",
                "text": (
                    f"✅ *Cotización analizada* `{filename}`\n"
                    f"Proforma *#{proforma}* · {client_name} · *{item_count} ítems*\n"
                    "_Revisá el resumen abajo antes de enviarlo a bodega._"
                ),
            },
        }
    ]


def _analysis_error_blocks(filename: str, error: str) -> List[Dict]:
    return [
        {
            "type": "section",
            "text": {
                "type": "mrkdwn",
                "text": f"❌ *Error al analizar* `{filename}`\n```{error[:300]}```",
            },
        }
    ]


def _summary_blocks(
    order_id: str,
    proforma: str,
    client_name: str,
    items: List[Dict],
    confirmed: bool = False,
) -> List[Dict]:
    """
    Resumen interactivo del pedido con ítems agrupados por zona.
    Incluye botones de Confirmar y Editar (o badge de "Enviado" si ya fue confirmado).
    """
    # ── Header ────────────────────────────────────────────────────────────
    blocks: List[Dict] = [
        {
            "type": "header",
            "text": {
                "type": "plain_text",
                "text": f"📋 Cotización #{proforma}  —  Revisión",
                "emoji": True,
            },
        },
        {
            "type": "section",
            "fields": [
                {"type": "mrkdwn", "text": f"*Cliente*\n{client_name}"},
                {"type": "mrkdwn", "text": f"*Total ítems*\n{len(items)}"},
            ],
        },
        {"type": "divider"},
    ]

    # ── Ítems agrupados por zona ───────────────────────────────────────────
    # Preservar orden de aparición de zonas
    zones: Dict[str, List[Dict]] = {}
    for item in items:
        zone = item.get("zone") or "— Sin zona —"
        zones.setdefault(zone, []).append(item)

    for zone_name, zone_items in zones.items():
        blocks.append({
            "type": "section",
            "text": {"type": "mrkdwn", "text": f"*📍 {zone_name}*"},
        })

        # Agrupar ítems de la zona en un solo bloque de texto para ahorra espacio
        lines = []
        for item in zone_items:
            qty = item.get("quantity", 1)
            # Mostrar cantidad como int si es entero
            qty_str = str(int(qty)) if qty == int(qty) else str(qty)
            unit = item.get("unit", "unidad")
            lines.append(f"  • {item['description']}  ×  *{qty_str}* {unit}")

        blocks.append({
            "type": "section",
            "text": {"type": "mrkdwn", "text": "\n".join(lines)},
        })
        blocks.append({"type": "divider"})

    # ── Botones de acción ─────────────────────────────────────────────────
    if confirmed:
        blocks.append({
            "type": "section",
            "text": {
                "type": "mrkdwn",
                "text": "✅ *Pedido enviado a bodega.* La bodega fue notificada.",
            },
        })
    else:
        blocks.append({
            "type": "actions",
            "elements": [
                {
                    "type": "button",
                    "text": {"type": "plain_text", "text": "✅ Confirmar — Enviar a bodega", "emoji": True},
                    "style": "primary",
                    "action_id": "confirm_order",
                    "value": order_id,
                    "confirm": {
                        "title": {"type": "plain_text", "text": "¿Confirmar pedido?"},
                        "text": {
                            "type": "mrkdwn",
                            "text": (
                                f"Se enviará la cotización *#{proforma}* de "
                                f"*{client_name}* a bodega para preparación."
                            ),
                        },
                        "confirm": {"type": "plain_text", "text": "Sí, enviar"},
                        "deny": {"type": "plain_text", "text": "Cancelar"},
                    },
                },
                {
                    "type": "button",
                    "text": {"type": "plain_text", "text": "✏️ Editar", "emoji": True},
                    "action_id": "edit_order",
                    "value": order_id,
                },
            ],
        })

    return blocks


def _edit_modal(order_id: str, client_name: str, items: List[Dict]) -> Dict:
    """
    Modal de edición.
    Los ítems se muestran como texto plano: zona | descripción | cantidad
    Una línea por ítem.
    """
    items_lines = []
    for item in items:
        zone = item.get("zone") or ""
        desc = item.get("description", "")
        qty = item.get("quantity", 1)
        qty_str = str(int(qty)) if qty == int(qty) else str(qty)
        items_lines.append(f"{zone} | {desc} | {qty_str}")

    items_text = "\n".join(items_lines)

    return {
        "type": "modal",
        "callback_id": "edit_order_submit",
        "title": {"type": "plain_text", "text": "Editar pedido"},
        "submit": {"type": "plain_text", "text": "✅ Guardar y re-revisar"},
        "close": {"type": "plain_text", "text": "Cancelar"},
        "private_metadata": order_id,
        "blocks": [
            {
                "type": "input",
                "block_id": "client_block",
                "label": {"type": "plain_text", "text": "Nombre del cliente"},
                "element": {
                    "type": "plain_text_input",
                    "action_id": "client_input",
                    "initial_value": client_name,
                    "placeholder": {"type": "plain_text", "text": "Ej: Juan Pérez"},
                },
            },
            {
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": (
                        "*Ítems* — formato: `zona | descripción | cantidad`\n"
                        "Una línea por ítem. Si no tiene zona dejá vacío: `| descripción | cantidad`"
                    ),
                },
            },
            {
                "type": "input",
                "block_id": "items_block",
                "label": {"type": "plain_text", "text": "Ítems del pedido"},
                "element": {
                    "type": "plain_text_input",
                    "action_id": "items_input",
                    "multiline": True,
                    "initial_value": items_text,
                    "placeholder": {
                        "type": "plain_text",
                        "text": "ArrFachTer | Perfil Esquinero 2020v | 30\n | COB 110v IP67 (3000k) | 29",
                    },
                },
            },
        ],
    }


# ============================================================================
# Database helpers
# ============================================================================

def _save_draft_order(
    parsed: Dict[str, Any],
    channel_id: str,
    thread_ts: str,
    filename: str,
) -> str:
    """Guarda el pedido con status='draft' en Supabase. Retorna el order UUID."""
    now_iso = datetime.now(timezone.utc).isoformat()

    order_payload = {
        "proforma_number": parsed["proforma_number"],
        "client_name": parsed["client_name"],
        "status": "draft",
        "slack_channel_id": channel_id,
        "slack_message_ts": thread_ts,   # TS del mensaje raíz del hilo
        "slack_thread_ts": thread_ts,    # mismo — para postear replies en el hilo
        "raw_text": filename,
        "created_at": now_iso,
        "updated_at": now_iso,
    }
    order_result = supabase.table("orders").insert(order_payload).execute()
    if not order_result.data:
        raise RuntimeError("Supabase no devolvió datos al insertar el pedido")

    order_id: str = order_result.data[0]["id"]

    if parsed.get("items"):
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
            for item in parsed["items"]
        ]
        supabase.table("order_items").insert(items_payload).execute()

    return order_id


def _confirm_order(order_id: str) -> Dict[str, Any]:
    """Cambia el status de draft → pending y retorna el pedido actualizado."""
    now_iso = datetime.now(timezone.utc).isoformat()
    supabase.table("orders").update({"status": "pending", "updated_at": now_iso}).eq("id", order_id).execute()
    result = supabase.table("orders").select("*").eq("id", order_id).single().execute()
    return result.data or {}


def _load_order_with_items(order_id: str) -> Optional[Dict[str, Any]]:
    order_result = supabase.table("orders").select("*").eq("id", order_id).single().execute()
    if not order_result.data:
        return None
    order = order_result.data
    items_result = supabase.table("order_items").select("*").eq("order_id", order_id).execute()
    order["items"] = items_result.data or []
    return order


def _replace_order_items(order_id: str, new_client: str, new_items: List[Dict]) -> None:
    """Actualiza cliente e ítems de un pedido (borra y re-inserta los ítems)."""
    now_iso = datetime.now(timezone.utc).isoformat()
    supabase.table("orders").update(
        {"client_name": new_client, "updated_at": now_iso}
    ).eq("id", order_id).execute()

    supabase.table("order_items").delete().eq("order_id", order_id).execute()

    if new_items:
        supabase.table("order_items").insert([
            {
                "order_id": order_id,
                "sku": item.get("sku"),
                "description": item["description"],
                "quantity": item["quantity"],
                "unit": item.get("unit", "unidad"),
                "zone": item.get("zone", ""),
                "created_at": now_iso,
            }
            for item in new_items
        ]).execute()


# ============================================================================
# Slack helpers
# ============================================================================

def _download_slack_file(client: Any, file_id: str) -> bytes:
    info_resp = client.files_info(file=file_id)
    file_info: Dict[str, Any] = info_resp["file"]
    url = file_info.get("url_private_download") or file_info.get("url_private", "")
    if not url:
        raise ValueError(f"Sin URL de descarga para file_id={file_id}")
    resp = requests.get(url, headers={"Authorization": f"Bearer {settings.slack_bot_token}"}, timeout=30)
    resp.raise_for_status()
    return resp.content


def _broadcast_new_order(order_id: str, client_name: str, proforma_number: str) -> None:
    """Notifica a los clientes WebSocket conectados (daemon de audio)."""
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
        logger.warning("WebSocket broadcast falló: %s", exc)


def _parse_items_text(items_text: str) -> List[Dict]:
    """
    Parsea el texto del modal de edición.
    Formato: zona | descripción | cantidad  (una línea por ítem)
    """
    items: List[Dict] = []
    for raw_line in items_text.strip().splitlines():
        line = raw_line.strip()
        if not line:
            continue
        parts = [p.strip() for p in line.split("|")]
        if len(parts) >= 3:
            zone, description, qty_str = parts[0], parts[1], parts[2]
        elif len(parts) == 2:
            zone, description, qty_str = "", parts[0], parts[1]
        elif len(parts) == 1:
            zone, description, qty_str = "", parts[0], "1"
        else:
            continue

        if not description:
            continue

        # Parse quantity
        cleaned_qty = qty_str.replace(",", ".").strip()
        try:
            qty = float(cleaned_qty)
        except ValueError:
            qty = 1.0

        items.append({
            "zone": zone,
            "description": description,
            "quantity": qty,
            "unit": "unidad",
            "sku": None,
        })
    return items


# ============================================================================
# Main entry point
# ============================================================================

def start_slack_bot() -> None:
    """
    Inicia el bot en Socket Mode.  Blocking — correr en daemon thread.

    ⚠️  La App se inicializa AQUÍ (no a nivel de módulo) para evitar
    que un token inválido crashee FastAPI antes de que pueda arrancar.
    """
    logger.info("Starting Slack bot in Socket Mode...")

    try:
        from slack_bolt import App
        from slack_bolt.adapter.socket_mode import SocketModeHandler

        app = App(
            token=settings.slack_bot_token,
            signing_secret=settings.slack_signing_secret,
        )

        # ── @mention con PDF adjunto ──────────────────────────────────────
        @app.event("app_mention")
        def handle_mention(event: Dict, client: Any, say: Any) -> None:
            channel_id: str = event.get("channel", "")
            thread_ts: str = event.get("ts", "")  # usamos el TS del mention como thread root
            files: List[Dict] = event.get("files", [])

            # Filtrar solo PDFs
            pdf_files = [
                f for f in files
                if f.get("mimetype") == "application/pdf"
                or (f.get("name") or "").lower().endswith(".pdf")
            ]

            if not pdf_files:
                client.chat_postMessage(
                    channel=channel_id,
                    thread_ts=thread_ts,
                    text=(
                        "Adjuntá un PDF de cotización al mensaje y te lo proceso. 📎\n"
                        "Ej: _@yader enviá esto a bodega_ + archivo PDF"
                    ),
                )
                return

            file_meta = pdf_files[0]
            filename: str = file_meta.get("name", "cotización.pdf")

            # Respuesta inmediata: "Analizando…"
            try:
                msg = client.chat_postMessage(
                    channel=channel_id,
                    thread_ts=thread_ts,
                    text=f"🔄 Analizando `{filename}`…",
                    blocks=_analyzing_blocks(filename),
                )
                analyzing_ts: str = msg["ts"]
            except Exception as exc:
                logger.error("No se pudo postear mensaje de análisis: %s", exc)
                return

            try:
                # Descargar y parsear el PDF
                pdf_bytes = _download_slack_file(client, file_meta["id"])
                logger.info("PDF descargado: %s (%d bytes)", filename, len(pdf_bytes))

                parsed = parse_quote_pdf(pdf_bytes)
                logger.info(
                    "PDF parseado → proforma=%s | cliente=%s | items=%d",
                    parsed["proforma_number"], parsed["client_name"], len(parsed["items"]),
                )

                # Guardar en Supabase como borrador
                order_id = _save_draft_order(parsed, channel_id, thread_ts, filename)
                logger.info("Borrador guardado: order_id=%s", order_id)

                # Actualizar mensaje de análisis a "Completado"
                client.chat_update(
                    channel=channel_id,
                    ts=analyzing_ts,
                    text=f"✅ Cotización `{filename}` analizada",
                    blocks=_analysis_done_blocks(
                        filename,
                        parsed["proforma_number"],
                        parsed["client_name"],
                        len(parsed["items"]),
                    ),
                )

                # Postear resumen interactivo
                client.chat_postMessage(
                    channel=channel_id,
                    thread_ts=thread_ts,
                    text=f"Cotización #{parsed['proforma_number']} — revisá y confirmá",
                    blocks=_summary_blocks(
                        order_id,
                        parsed["proforma_number"],
                        parsed["client_name"],
                        parsed["items"],
                    ),
                )

            except Exception as exc:
                logger.error("Error procesando PDF %s: %s", filename, exc, exc_info=True)
                try:
                    client.chat_update(
                        channel=channel_id,
                        ts=analyzing_ts,
                        text=f"❌ Error al analizar `{filename}`",
                        blocks=_analysis_error_blocks(filename, str(exc)),
                    )
                except Exception:
                    pass

        # ── Botón: Confirmar ──────────────────────────────────────────────
        @app.action("confirm_order")
        def handle_confirm(ack: Any, body: Dict, client: Any) -> None:
            ack()

            order_id: str = body["actions"][0]["value"]
            channel_id: str = body["container"]["channel_id"]
            message_ts: str = body["container"]["message_ts"]

            try:
                order = _confirm_order(order_id)
                if not order:
                    raise RuntimeError(f"Pedido {order_id} no encontrado")

                # Notificar bodega (WebSocket + audio daemon)
                _broadcast_new_order(
                    order_id,
                    order.get("client_name", ""),
                    order.get("proforma_number", ""),
                )

                # Cargar ítems para actualizar el resumen
                full_order = _load_order_with_items(order_id)
                items = full_order.get("items", []) if full_order else []

                # Actualizar el mensaje del resumen a "Enviado"
                client.chat_update(
                    channel=channel_id,
                    ts=message_ts,
                    text=f"✅ Pedido #{order['proforma_number']} enviado a bodega",
                    blocks=_summary_blocks(
                        order_id,
                        order.get("proforma_number", ""),
                        order.get("client_name", ""),
                        items,
                        confirmed=True,
                    ),
                )

                logger.info(
                    "Pedido confirmado y enviado a bodega: order_id=%s proforma=%s",
                    order_id, order.get("proforma_number"),
                )

            except Exception as exc:
                logger.error("Error confirmando pedido %s: %s", order_id, exc, exc_info=True)
                client.chat_postMessage(
                    channel=channel_id,
                    thread_ts=message_ts,
                    text=f"⚠️ Error al confirmar el pedido: {str(exc)[:200]}",
                )

        # ── Botón: Editar → abre modal ────────────────────────────────────
        @app.action("edit_order")
        def handle_edit(ack: Any, body: Dict, client: Any) -> None:
            ack()

            order_id: str = body["actions"][0]["value"]
            trigger_id: str = body["trigger_id"]

            try:
                full_order = _load_order_with_items(order_id)
                if not full_order:
                    raise RuntimeError(f"Pedido {order_id} no encontrado en BD")

                client.views_open(
                    trigger_id=trigger_id,
                    view=_edit_modal(
                        order_id,
                        full_order.get("client_name", ""),
                        full_order.get("items", []),
                    ),
                )

            except Exception as exc:
                logger.error("Error abriendo modal de edición: %s", exc, exc_info=True)

        # ── Modal de edición: submit ──────────────────────────────────────
        @app.view("edit_order_submit")
        def handle_edit_submit(ack: Any, body: Dict, client: Any, view: Dict) -> None:
            ack()

            order_id: str = view["private_metadata"]
            values = view["state"]["values"]

            new_client: str = (
                values.get("client_block", {})
                .get("client_input", {})
                .get("value", "")
                .strip()
            )
            items_text: str = (
                values.get("items_block", {})
                .get("items_input", {})
                .get("value", "")
            )

            new_items = _parse_items_text(items_text)

            try:
                _replace_order_items(order_id, new_client, new_items)
                logger.info(
                    "Pedido actualizado vía modal: order_id=%s cliente=%s items=%d",
                    order_id, new_client, len(new_items),
                )

                # Recuperar datos actualizados del pedido (proforma, canal, etc.)
                full_order = _load_order_with_items(order_id)
                if not full_order:
                    return

                # Re-postear resumen actualizado en el mismo canal/hilo
                client.chat_postMessage(
                    channel=full_order["slack_channel_id"],
                    thread_ts=full_order.get("slack_thread_ts") or full_order.get("slack_message_ts"),
                    text=f"Pedido #{full_order['proforma_number']} actualizado — re-revisá",
                    blocks=_summary_blocks(
                        order_id,
                        full_order["proforma_number"],
                        new_client,
                        new_items,
                    ),
                )

            except Exception as exc:
                logger.error("Error guardando edición del pedido: %s", exc, exc_info=True)

        # ── Catch-all para eventos de mensaje que no manejamos ────────────
        @app.event("message")
        def handle_message_events(event: Dict, logger: Any) -> None:
            pass  # no-op intencional

        # ── Iniciar Socket Mode ───────────────────────────────────────────
        handler = SocketModeHandler(app=app, app_token=settings.slack_app_token)
        handler.start()  # bloquea hasta que el bot se detenga

    except Exception as exc:
        logger.error(
            "Slack bot falló al iniciar (FastAPI continúa): %s",
            exc,
            exc_info=True,
        )
