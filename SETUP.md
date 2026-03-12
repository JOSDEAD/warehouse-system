# 🏭 Warehouse System - Guía de Instalación

## Estructura del proyecto

```
warehouse-system/
├── backend/          ← FastAPI + Slack Bot + PDF Parser
├── frontend/         ← Next.js UI para bodega
├── audio-daemon/     ← Programa Python para el sonido en bodega
├── nginx/            ← Reverse proxy config
├── docker-compose.yml
└── supabase_schema.sql
```

---

## PASO 1: Supabase

1. Crear cuenta en https://supabase.com (gratis)
2. Crear nuevo proyecto
3. Ir a **SQL Editor** y ejecutar el contenido de `supabase_schema.sql`
4. En **Database > Replication**, habilitar realtime para las tablas `orders` e `inventory`
5. Copiar **Project URL** y **anon key** desde Settings > API

---

## PASO 2: Slack App

1. Ir a https://api.slack.com/apps → **Create New App** → From Scratch
2. Nombre: "Bodega Bot", workspace: el tuyo
3. En **Socket Mode**: activar y crear App-Level Token con scope `connections:write` → guardar como `SLACK_APP_TOKEN`
4. En **OAuth & Permissions** → Bot Token Scopes, agregar:
   - `files:read`
   - `channels:history`
   - `chat:write`
   - `groups:history`
5. Instalar app en workspace → guardar `SLACK_BOT_TOKEN`
6. En **Event Subscriptions** → Enable Events → Subscribe to Bot Events:
   - `message.channels`
   - `message.groups`
   - `file_shared`
7. En **Basic Information** → copiar `SLACK_SIGNING_SECRET`
8. Invitar el bot al canal de pedidos: `/invite @BodegaBot`

---

## PASO 3: VPS (Hetzner recomendado)

```bash
# 1. Conectar al VPS
ssh root@TU_IP_VPS

# 2. Instalar Docker
curl -fsSL https://get.docker.com | sh
apt install docker-compose-plugin -y

# 3. Clonar/subir el proyecto
git clone https://github.com/tu-repo/warehouse-system.git
# O subir con scp:
# scp -r ./warehouse-system root@TU_IP:/root/

cd warehouse-system

# 4. Configurar variables de entorno
cp backend/.env.example backend/.env
nano backend/.env   # llenar con tus credenciales

cp frontend/.env.local.example frontend/.env.local
nano frontend/.env.local   # llenar con tus URLs

# 5. Levantar todo
docker compose up -d --build

# 6. Ver logs
docker compose logs -f backend
docker compose logs -f frontend
```

---

## PASO 4: Importar inventario desde Excel

```python
# Script de importación incluido en backend/scripts/import_excel.py
# Ejecutar una sola vez:
cd backend
pip install openpyxl
python scripts/import_excel.py --file "../inventario.xlsx"
```

El script espera columnas: SKU, Nombre/Producto, Variedad, Cantidad, Unidad, Stock_Minimo

---

## PASO 5: Audio Daemon en PC de Bodega

```bash
# Opción A: Correr directamente con Python
cd audio-daemon
pip install -r requirements.txt
cp .env.example .env
nano .env   # poner VPS_HOST=http://TU_IP:8000
python daemon.py

# Opción B: Compilar como ejecutable
# Windows:
build_windows.bat

# Mac:
chmod +x build_mac.sh && ./build_mac.sh

# Linux:
chmod +x build_linux.sh && ./build_linux.sh
```

**Importante:** Colocar el archivo de sonido en `audio-daemon/sounds/nuevo_pedido.mp3`

---

## PASO 6: Abrir la UI de bodega

Abrir en el navegador del Raspberry Pi / PC de bodega:
```
http://TU_IP_VPS:3000
```

O si tienes dominio configurado:
```
https://bodega.tuempresa.com
```

---

## Flujo de uso

1. 📧 Proveedor envía PDF al canal de Slack
2. 🤖 Bot descarga y parsea el PDF automáticamente
3. 🔔 Daemon en bodega reproduce "Nuevo pedido a preparar" cada 60 segundos
4. 📋 Bodeguero ve el pedido en la pantalla con todos los items
5. ✅ Bodeguero marca el pedido como completado (ingresa su nombre)
6. 💬 Bot envía mensaje al canal de Slack: "Pedido listo para despacho"
7. 📦 Inventario se rebaja automáticamente

---

## Mantenimiento

```bash
# Ver estado de los servicios
docker compose ps

# Reiniciar un servicio
docker compose restart backend

# Ver logs en tiempo real
docker compose logs -f

# Actualizar después de cambios
docker compose up -d --build backend
```

---

## Puertos usados

| Puerto | Servicio |
|--------|----------|
| 80     | Nginx (HTTP) |
| 443    | Nginx (HTTPS, cuando configures SSL) |
| 8000   | Backend API (interno) |
| 3000   | Frontend (interno) |
