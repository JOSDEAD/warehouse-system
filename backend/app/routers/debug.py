"""
debug.py
========
Endpoint de debug para testear el parser de PDFs sin pasar por Slack.

POST /api/debug/parse-pdf
  - Acepta un PDF como form-data (campo: file)
  - Devuelve lo que el parser extrae: proforma_number, client_name, items[]
  - Útil para ajustar el parser antes de ponerlo en producción

⚠️  Este endpoint SOLO está disponible si DEBUG_MODE=true en el .env
"""

from __future__ import annotations

import logging
import os

from fastapi import APIRouter, HTTPException, UploadFile, File

from app.services.pdf_parser import parse_quote_pdf

logger = logging.getLogger(__name__)

router = APIRouter()


@router.post("/parse-pdf")
async def debug_parse_pdf(file: UploadFile = File(...)):
    """
    Sube un PDF y devuelve lo que el parser extrae.
    Útil para verificar que proforma_number, client_name e items
    se extraen correctamente antes de procesar pedidos reales.
    """
    debug_mode = os.getenv("DEBUG_MODE", "false").lower() == "true"
    if not debug_mode:
        raise HTTPException(
            status_code=403,
            detail="Debug endpoint disabled. Set DEBUG_MODE=true in environment to enable.",
        )

    if not file.filename or not file.filename.lower().endswith(".pdf"):
        raise HTTPException(status_code=400, detail="El archivo debe ser un PDF (.pdf)")

    pdf_bytes = await file.read()
    if not pdf_bytes:
        raise HTTPException(status_code=400, detail="El archivo está vacío")

    logger.info("Debug parse-pdf: filename=%s size=%d bytes", file.filename, len(pdf_bytes))

    try:
        result = parse_quote_pdf(pdf_bytes)
    except Exception as exc:
        raise HTTPException(status_code=422, detail=f"Error al parsear el PDF: {exc}")

    return {
        "filename": file.filename,
        "size_bytes": len(pdf_bytes),
        "parsed": result,
        "item_count": len(result.get("items", [])),
        "warnings": _build_warnings(result),
    }


def _build_warnings(result: dict) -> list[str]:
    warnings = []
    if result.get("proforma_number") == "UNKNOWN":
        warnings.append(
            "No se encontró número de proforma — revisar regex _PROFORMA_PATTERNS en pdf_parser.py"
        )
    if result.get("client_name") == "UNKNOWN":
        warnings.append(
            "No se encontró nombre de cliente — revisar regex _CLIENT_PATTERNS en pdf_parser.py"
        )
    if not result.get("items"):
        warnings.append(
            "No se extrajeron items — el PDF puede ser una imagen escaneada, "
            "o las columnas tienen nombres no reconocidos"
        )
    else:
        items_without_sku = [i for i in result["items"] if not i.get("sku")]
        if items_without_sku:
            warnings.append(
                f"{len(items_without_sku)} items sin SKU — la deducción de inventario "
                "no funcionará para esos items"
            )
        items_without_zone = [i for i in result["items"] if not i.get("zone")]
        if items_without_zone:
            warnings.append(
                f"{len(items_without_zone)} items sin zona — agregar columna 'zona' al PDF "
                "o mapearla manualmente"
            )
    return warnings
