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
  status: 'pending' | 'in_progress' | 'completed';
  created_at: string;
  completed_at: string | null;
  completed_by: string | null;
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

export type OrderStatus = 'pending' | 'in_progress' | 'completed';

export type FilterStatus = 'all' | OrderStatus;
