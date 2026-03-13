import logging
from datetime import datetime, timezone
from typing import Optional

from fastapi import APIRouter, HTTPException, Query

from app.database import supabase
from app.models import InventoryItem, InventoryCreate, InventoryUpdate

logger = logging.getLogger(__name__)

router = APIRouter()


def _row_to_model(row: dict) -> InventoryItem:
    return InventoryItem(
        id=row["id"],
        sku=row["sku"],
        name=row["name"],
        variety=row.get("variety"),
        quantity=float(row.get("quantity", 0)),
        unit=row.get("unit", "unidad"),
        min_stock=float(row.get("min_stock", 0)),
        updated_at=row.get("updated_at"),
    )


@router.get("/low-stock", response_model=list[InventoryItem])
async def get_low_stock():
    """Return inventory items where quantity is at or below min_stock."""
    try:
        result = supabase.table("inventory").select("*").execute()
        all_items = result.data or []
        low = [
            _row_to_model(item)
            for item in all_items
            if float(item.get("quantity", 0)) <= float(item.get("min_stock", 0))
        ]
        return low
    except Exception as exc:
        logger.error("Error fetching low-stock items: %s", exc)
        raise HTTPException(status_code=500, detail="Failed to fetch low-stock items")


@router.get("", response_model=list[InventoryItem])
async def list_inventory(
    search: Optional[str] = Query(default=None, description="Search by name, sku, or variety"),
):
    """List all inventory items with optional search filtering."""
    try:
        result = supabase.table("inventory").select("*").order("name").execute()
        items = result.data or []

        if search:
            search_lower = search.lower()
            items = [
                item for item in items
                if search_lower in item.get("name", "").lower()
                or search_lower in item.get("sku", "").lower()
                or search_lower in (item.get("variety") or "").lower()
            ]

        return [_row_to_model(item) for item in items]
    except Exception as exc:
        logger.error("Error listing inventory: %s", exc)
        raise HTTPException(status_code=500, detail="Failed to fetch inventory")


@router.get("/{item_id}", response_model=InventoryItem)
async def get_inventory_item(item_id: str):
    """Get a single inventory item by ID."""
    try:
        result = (
            supabase.table("inventory").select("*").eq("id", item_id).single().execute()
        )
        if not result.data:
            raise HTTPException(status_code=404, detail="Inventory item not found")
        return _row_to_model(result.data)
    except HTTPException:
        raise
    except Exception as exc:
        logger.error("Error fetching inventory item %s: %s", item_id, exc)
        raise HTTPException(status_code=500, detail="Failed to fetch inventory item")


@router.post("", response_model=InventoryItem, status_code=201)
async def create_inventory_item(body: InventoryCreate):
    """Create a new inventory item."""
    try:
        existing = supabase.table("inventory").select("id").eq("sku", body.sku).execute()
        if existing.data:
            raise HTTPException(
                status_code=409, detail=f"Inventory item with SKU '{body.sku}' already exists"
            )

        now_iso = datetime.now(timezone.utc).isoformat()
        payload = {
            "sku": body.sku,
            "name": body.name,
            "variety": body.variety,
            "quantity": body.quantity,
            "unit": body.unit,
            "min_stock": body.min_stock,
            "updated_at": now_iso,
        }
        result = supabase.table("inventory").insert(payload).execute()
        if not result.data:
            raise HTTPException(status_code=500, detail="Failed to create inventory item")
        return _row_to_model(result.data[0])
    except HTTPException:
        raise
    except Exception as exc:
        logger.error("Error creating inventory item: %s", exc)
        raise HTTPException(status_code=500, detail="Failed to create inventory item")


@router.put("/{item_id}", response_model=InventoryItem)
async def update_inventory_item(item_id: str, body: InventoryUpdate):
    """Update an inventory item. Only supplied fields are modified."""
    try:
        existing_result = (
            supabase.table("inventory").select("*").eq("id", item_id).single().execute()
        )
        if not existing_result.data:
            raise HTTPException(status_code=404, detail="Inventory item not found")

        update_payload: dict = {"updated_at": datetime.now(timezone.utc).isoformat()}

        if body.quantity is not None:
            update_payload["quantity"] = body.quantity
        if body.name is not None:
            update_payload["name"] = body.name
        if body.variety is not None:
            update_payload["variety"] = body.variety
        if body.min_stock is not None:
            update_payload["min_stock"] = body.min_stock
        if body.unit is not None:
            update_payload["unit"] = body.unit

        result = (
            supabase.table("inventory").update(update_payload).eq("id", item_id).execute()
        )
        if not result.data:
            raise HTTPException(status_code=500, detail="Failed to update inventory item")
        return _row_to_model(result.data[0])
    except HTTPException:
        raise
    except Exception as exc:
        logger.error("Error updating inventory item %s: %s", item_id, exc)
        raise HTTPException(status_code=500, detail="Failed to update inventory item")
