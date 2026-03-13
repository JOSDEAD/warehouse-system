from pydantic import BaseModel, Field
from typing import Optional, List
from datetime import datetime


class OrderItem(BaseModel):
    sku: Optional[str] = None
    description: str
    quantity: float
    unit: str = "unidad"
    zone: str = ""


class OrderCreate(BaseModel):
    proforma_number: str
    client_name: str
    items: List[OrderItem]
    slack_channel_id: str
    slack_message_ts: str
    raw_text: str = ""


class OrderItemResponse(BaseModel):
    id: Optional[str] = None
    order_id: Optional[str] = None
    sku: Optional[str] = None
    description: str
    quantity: float
    unit: str
    zone: str
    created_at: Optional[datetime] = None


class OrderResponse(BaseModel):
    id: str
    proforma_number: str
    client_name: str
    status: str
    slack_channel_id: str
    slack_message_ts: str
    raw_text: Optional[str] = None
    created_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    completed_by: Optional[str] = None
    checked_items: List[str] = []
    items: List[OrderItemResponse] = []


class OrderStatusUpdate(BaseModel):
    status: str = Field(..., pattern="^(in_progress|completed)$")
    completed_by: Optional[str] = None


class OrderProgressUpdate(BaseModel):
    checked_items: List[str]


class InventoryItem(BaseModel):
    id: str
    sku: str
    name: str
    variety: Optional[str] = None
    quantity: float
    unit: str = "unidad"
    min_stock: float = 0
    updated_at: Optional[datetime] = None


class InventoryCreate(BaseModel):
    sku: str
    name: str
    variety: Optional[str] = None
    quantity: float = 0
    unit: str = "unidad"
    min_stock: float = 0


class InventoryUpdate(BaseModel):
    quantity: Optional[float] = None
    name: Optional[str] = None
    variety: Optional[str] = None
    min_stock: Optional[float] = None
    unit: Optional[str] = None
