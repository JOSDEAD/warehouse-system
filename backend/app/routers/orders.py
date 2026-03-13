import logging
from datetime import datetime, timezone
from typing import Optional

from fastapi import APIRouter, HTTPException, Query

from app.database import supabase
from app.models import OrderCreate, OrderResponse, OrderItemResponse, OrderStatusUpdate
from app.services import notifier

logger = logging.getLogger(__name__)

router = APIRouter()


def _build_order_response(order: dict, items: list) -> OrderResponse:
    """Construct an OrderResponse from raw Supabase dicts."""
    item_responses = [
        OrderItemResponse(
            id=item.get("id"),
            order_id=item.get("order_id"),
            sku=item.get("sku"),
            description=item.get("description", ""),
            quantity=float(item.get("quantity", 0)),
            unit=item.get("unit", "unidad"),
            zone=item.get("zone", ""),
            created_at=item.get("created_at"),
        )
        for item in items
    ]
    return OrderResponse(
        id=order["id"],
        proforma_number=order["proforma_number"],
        client_name=order["client_name"],
        status=order["status"],
        slack_channel_id=order.get("slack_channel_id", ""),
        slack_message_ts=order.get("slack_message_ts", ""),
        raw_text=order.get("raw_text"),
        created_at=order.get("created_at"),
        completed_at=order.get("completed_at"),
        completed_by=order.get("completed_by"),
        items=item_responses,
    )


@router.get("/pending-count")
async def get_pending_count():
    """Return count of orders with status 'pending' — used by the audio daemon."""
    try:
        result = (
            supabase.table("orders")
            .select("id", count="exact")
            .eq("status", "pending")
            .execute()
        )
        count = result.count if result.count is not None else len(result.data)
        return {"count": count}
    except Exception as exc:
        logger.error("Error fetching pending count: %s", exc)
        raise HTTPException(status_code=500, detail="Failed to fetch pending count")


@router.get("", response_model=list[OrderResponse])
async def list_orders(
    status: Optional[str] = Query(default="all", description="pending | in_progress | completed | all"),
    search: Optional[str] = Query(default=None, description="Search in proforma_number and client_name"),
):
    """List all orders with their items. Supports filtering by status and search."""
    try:
        query = supabase.table("orders").select("*").order("created_at", desc=True)

        if status and status != "all":
            if status not in ("pending", "in_progress", "completed"):
                raise HTTPException(status_code=400, detail="Invalid status value")
            query = query.eq("status", status)

        result = query.execute()
        orders = result.data or []

        if search:
            search_lower = search.lower()
            orders = [
                o for o in orders
                if search_lower in o.get("proforma_number", "").lower()
                or search_lower in o.get("client_name", "").lower()
            ]

        if not orders:
            return []

        order_ids = [o["id"] for o in orders]
        items_result = (
            supabase.table("order_items")
            .select("*")
            .in_("order_id", order_ids)
            .execute()
        )
        items_by_order: dict[str, list] = {}
        for item in items_result.data or []:
            items_by_order.setdefault(item["order_id"], []).append(item)

        return [
            _build_order_response(order, items_by_order.get(order["id"], []))
            for order in orders
        ]
    except HTTPException:
        raise
    except Exception as exc:
        logger.error("Error listing orders: %s", exc)
        raise HTTPException(status_code=500, detail="Failed to fetch orders")


@router.get("/{order_id}", response_model=OrderResponse)
async def get_order(order_id: str):
    """Get a single order with all its items."""
    try:
        result = supabase.table("orders").select("*").eq("id", order_id).single().execute()
        order = result.data
        if not order:
            raise HTTPException(status_code=404, detail="Order not found")

        items_result = (
            supabase.table("order_items")
            .select("*")
            .eq("order_id", order_id)
            .execute()
        )
        return _build_order_response(order, items_result.data or [])
    except HTTPException:
        raise
    except Exception as exc:
        logger.error("Error fetching order %s: %s", order_id, exc)
        raise HTTPException(status_code=500, detail="Failed to fetch order")


@router.patch("/{order_id}/status", response_model=OrderResponse)
async def update_order_status(order_id: str, body: OrderStatusUpdate):
    """
    Update the status of an order.
    When status becomes 'completed':
      - Deducts inventory for items that have a matching SKU
      - Records inventory movements
      - Sets completed_at timestamp
      - Sends a Slack notification
    """
    try:
        order_result = supabase.table("orders").select("*").eq("id", order_id).single().execute()
        order = order_result.data
        if not order:
            raise HTTPException(status_code=404, detail="Order not found")

        update_payload: dict = {"status": body.status}

        if body.status == "completed":
            now_iso = datetime.now(timezone.utc).isoformat()
            update_payload["completed_at"] = now_iso
            if body.completed_by:
                update_payload["completed_by"] = body.completed_by

            items_result = (
                supabase.table("order_items")
                .select("*")
                .eq("order_id", order_id)
                .execute()
            )
            order_items = items_result.data or []

            for item in order_items:
                sku = item.get("sku")
                if not sku:
                    logger.info(
                        "Order item '%s' has no SKU — skipping inventory deduction",
                        item.get("description"),
                    )
                    continue

                inv_result = (
                    supabase.table("inventory")
                    .select("*")
                    .eq("sku", sku)
                    .execute()
                )
                inv_items = inv_result.data or []
                if not inv_items:
                    logger.warning(
                        "SKU '%s' not found in inventory — skipping deduction for '%s'",
                        sku,
                        item.get("description"),
                    )
                    continue

                inv_item = inv_items[0]
                qty_to_deduct = float(item.get("quantity", 0))
                new_qty = max(0.0, float(inv_item.get("quantity", 0)) - qty_to_deduct)

                supabase.table("inventory").update(
                    {"quantity": new_qty, "updated_at": now_iso}
                ).eq("id", inv_item["id"]).execute()

                supabase.table("inventory_movements").insert(
                    {
                        "inventory_id": inv_item["id"],
                        "order_id": order_id,
                        "movement_type": "exit",
                        "quantity_before": float(inv_item.get("quantity", 0)),
                        "quantity_change": -qty_to_deduct,
                        "quantity_after": new_qty,
                        "note": f"Pedido #{order.get('proforma_number', order_id)}: {item.get('description', '')}",
                    }
                ).execute()

        supabase.table("orders").update(update_payload).eq("id", order_id).execute()

        updated_result = supabase.table("orders").select("*").eq("id", order_id).single().execute()
        updated_order = updated_result.data

        items_result = (
            supabase.table("order_items").select("*").eq("order_id", order_id).execute()
        )
        order_items = items_result.data or []

        if body.status == "completed":
            try:
                await notifier.send_order_completed(updated_order, order_items)
            except Exception as notify_exc:
                logger.error("Failed to send Slack notification for order %s: %s", order_id, notify_exc)

        return _build_order_response(updated_order, order_items)
    except HTTPException:
        raise
    except Exception as exc:
        logger.error("Error updating order status %s: %s", order_id, exc)
        raise HTTPException(status_code=500, detail="Failed to update order status")


@router.delete("/{order_id}")
async def delete_order(order_id: str):
    """Delete an order and its items."""
    try:
        order_result = supabase.table("orders").select("id").eq("id", order_id).single().execute()
        if not order_result.data:
            raise HTTPException(status_code=404, detail="Order not found")

        supabase.table("order_items").delete().eq("order_id", order_id).execute()
        supabase.table("orders").delete().eq("id", order_id).execute()

        return {"message": f"Order {order_id} deleted successfully"}
    except HTTPException:
        raise
    except Exception as exc:
        logger.error("Error deleting order %s: %s", order_id, exc)
        raise HTTPException(status_code=500, detail="Failed to delete order")
