-- ============================================================
-- WAREHOUSE SYSTEM - Supabase Schema
-- Ejecutar en: Supabase Dashboard > SQL Editor
-- ============================================================

-- Habilitar UUID
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";

-- ============================================================
-- TABLA: orders
-- ============================================================
CREATE TABLE orders (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    proforma_number TEXT,
    client_name TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'pending'
        CHECK (status IN ('pending', 'in_progress', 'completed')),
    slack_channel_id TEXT,
    slack_message_ts TEXT,
    raw_text TEXT,          -- texto completo del PDF por si se necesita
    created_at TIMESTAMPTZ DEFAULT NOW(),
    completed_at TIMESTAMPTZ,
    completed_by TEXT       -- nombre del bodeguero que completó
);

-- ============================================================
-- TABLA: order_items
-- ============================================================
CREATE TABLE order_items (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    order_id UUID NOT NULL REFERENCES orders(id) ON DELETE CASCADE,
    sku TEXT,
    description TEXT NOT NULL,
    quantity NUMERIC(10, 2) NOT NULL,
    unit TEXT DEFAULT 'unidad',
    zone TEXT DEFAULT '',
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- ============================================================
-- TABLA: inventory
-- ============================================================
CREATE TABLE inventory (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    sku TEXT UNIQUE NOT NULL,
    name TEXT NOT NULL,
    variety TEXT DEFAULT '',
    quantity NUMERIC(10, 2) NOT NULL DEFAULT 0,
    unit TEXT DEFAULT 'unidad',
    min_stock NUMERIC(10, 2) DEFAULT 5,
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

-- ============================================================
-- TABLA: inventory_movements (historial de movimientos)
-- ============================================================
CREATE TABLE inventory_movements (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    inventory_id UUID NOT NULL REFERENCES inventory(id),
    order_id UUID REFERENCES orders(id),
    movement_type TEXT CHECK (movement_type IN ('entry', 'exit', 'adjustment')),
    quantity_before NUMERIC(10, 2),
    quantity_change NUMERIC(10, 2),
    quantity_after NUMERIC(10, 2),
    note TEXT,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- ============================================================
-- TRIGGER: actualizar updated_at en inventory
-- ============================================================
CREATE OR REPLACE FUNCTION update_inventory_timestamp()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER inventory_updated_at
    BEFORE UPDATE ON inventory
    FOR EACH ROW
    EXECUTE FUNCTION update_inventory_timestamp();

-- ============================================================
-- TRIGGER: registrar movimiento al actualizar inventario
-- ============================================================
CREATE OR REPLACE FUNCTION log_inventory_movement()
RETURNS TRIGGER AS $$
BEGIN
    IF OLD.quantity != NEW.quantity THEN
        INSERT INTO inventory_movements (
            inventory_id,
            movement_type,
            quantity_before,
            quantity_change,
            quantity_after
        ) VALUES (
            NEW.id,
            CASE WHEN NEW.quantity > OLD.quantity THEN 'entry' ELSE 'exit' END,
            OLD.quantity,
            NEW.quantity - OLD.quantity,
            NEW.quantity
        );
    END IF;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER inventory_movement_log
    AFTER UPDATE ON inventory
    FOR EACH ROW
    EXECUTE FUNCTION log_inventory_movement();

-- ============================================================
-- ÍNDICES para performance
-- ============================================================
CREATE INDEX idx_orders_status ON orders(status);
CREATE INDEX idx_orders_created_at ON orders(created_at DESC);
CREATE INDEX idx_order_items_order_id ON order_items(order_id);
CREATE INDEX idx_inventory_sku ON inventory(sku);

-- ============================================================
-- HABILITAR REALTIME (para live updates en el frontend)
-- Ejecutar por separado en Supabase Dashboard > Database > Replication
-- ============================================================
-- ALTER PUBLICATION supabase_realtime ADD TABLE orders;
-- ALTER PUBLICATION supabase_realtime ADD TABLE inventory;

-- ============================================================
-- DATOS DE EJEMPLO (opcional, para probar)
-- ============================================================
INSERT INTO inventory (sku, name, variety, quantity, unit, min_stock) VALUES
    ('SKU-001', 'Cemento', 'Gris 50kg', 142, 'saco', 10),
    ('SKU-002', 'Varilla', '3/8"', 89, 'unidad', 20),
    ('SKU-003', 'Arena', 'Fina', 5, 'm3', 10),
    ('SKU-004', 'Block', '15x20x40', 500, 'unidad', 100),
    ('SKU-005', 'Pintura', 'Blanca 4L', 34, 'galón', 5);
