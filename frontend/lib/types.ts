export interface OrderItem {
  id: string;
  sku: string;
  description: string;
  quantity: number;
  unit: string;
  zone: string;
}

export interface Order {
  id: string;
  proforma_number: string;
  client_name: string;
  status: OrderStatus;
  created_at: string;
  completed_at: string | null;
  completed_by: string | null;
  checked_items: string[];
  items: OrderItem[];
}

export interface InventoryItem {
  id: string;
  sku: string;
  name: string;
  variety: string;
  quantity: number;
  unit: string;
  min_stock: number;
  updated_at: string;
}

export interface NewInventoryItem {
  sku: string;
  name: string;
  variety: string;
  quantity: number;
  unit: string;
  min_stock: number;
}

export type OrderStatus = 'draft' | 'pending' | 'in_progress' | 'completed';

export type FilterStatus = 'all' | OrderStatus;
