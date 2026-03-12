from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.routers import orders, inventory, ws
from app.services.slack_bot import start_slack_bot
import threading
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI(title="Warehouse System API", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(orders.router, prefix="/api/orders", tags=["orders"])
app.include_router(inventory.router, prefix="/api/inventory", tags=["inventory"])
app.include_router(ws.router, tags=["websocket"])


@app.on_event("startup")
async def startup_event():
    logger.info("Starting Slack bot in background thread...")
    thread = threading.Thread(target=start_slack_bot, daemon=True)
    thread.start()
    logger.info("Warehouse System started successfully")


@app.get("/health")
async def health():
    return {"status": "ok"}
