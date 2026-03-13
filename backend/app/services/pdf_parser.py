"""
pdf_parser.py
=============
Parser de cotizaciones Alegra (Luxury Lights) usando OpenAI GPT-4o-mini.

Flujo:
  1. Extraer texto crudo con pdfplumber
  2. Enviar texto a GPT-4o-mini con prompt estructurado
  3. Retornar JSON normalizado con proforma_number, client_name e items
"""

from __future__ import annotations

import io
import json
import logging
import re
from typing import Any, Dict, List

import pdfplumber
from openai import OpenAI

from app.config import settings

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# OpenAI client (lazy)
# ---------------------------------------------------------------------------

_openai_client: OpenAI | None = None


def _get_openai_client() -> OpenAI:
    global _openai_client
    if _openai_client is None:
        _openai_client = OpenAI(api_key=settings.openai_api_key)
    return _openai_client


# ---------------------------------------------------------------------------
# Prompt
# ---------------------------------------------------------------------------

_SYSTEM_PROMPT = """Eres un asistente experto en extraer información de cotizaciones (proformas) de iluminación de Luxury Lights generadas por Alegra.

Tu tarea es analizar el texto de una cotización PDF y devolver un JSON con esta estructura EXACTA:

{
  "proforma_number": "NNNN",
  "client_name": "NOMBRE DEL CLIENTE",
  "items": [
    {
      "zone": "ZONA O REFERENCIA",
      "description": "Descripción del producto",
      "quantity": 2
    }
  ]
}

Reglas importantes:
- proforma_number: es el número de cotización (ej: "3385"). Solo el número, sin "Cotización No." ni texto extra.
- client_name: nombre completo del cliente. Suele aparecer en mayúsculas en el encabezado. NO incluyas "Cedula", "Tel", "Email" ni datos de la empresa Luxury Lights.
- items: cada línea de producto en la cotización.
  - zone: la referencia o zona a la que pertenece el ítem (ej: "SALA", "CUARTO 1", "BAÑO"). Los ítems sin zona explícita heredan la última zona vista en el documento. Si no hay zona, usa "GENERAL".
  - description: descripción del producto tal como aparece en el PDF.
  - quantity: número entero o decimal de unidades. Si no aparece claramente, usa 1.
- Devuelve SOLO el JSON, sin texto adicional ni bloques de código markdown.
- Si no puedes determinar un campo, usa "DESCONOCIDO" para strings y 1 para quantity.
"""

_USER_PROMPT_TEMPLATE = """Aquí está el texto extraído de la cotización PDF:

---
{pdf_text}
---

Extrae la información y devuelve el JSON."""


# ---------------------------------------------------------------------------
# Text extraction
# ---------------------------------------------------------------------------

def _extract_text_from_pdf(pdf_bytes: bytes) -> str:
    """Extrae texto de todas las páginas del PDF usando pdfplumber."""
    pages_text: List[str] = []
    with pdfplumber.open(io.BytesIO(pdf_bytes)) as pdf:
        for page in pdf.pages:
            text = page.extract_text()
            if text:
                pages_text.append(text)

    full_text = "\n\n--- PÁGINA SIGUIENTE ---\n\n".join(pages_text)
    return full_text


# ---------------------------------------------------------------------------
# OpenAI extraction
# ---------------------------------------------------------------------------

def _extract_with_openai(pdf_text: str) -> Dict[str, Any]:
    """Envía el texto del PDF a GPT-4o-mini y retorna el JSON parseado."""
    client = _get_openai_client()

    user_message = _USER_PROMPT_TEMPLATE.format(pdf_text=pdf_text)

    logger.info("Enviando PDF a OpenAI GPT-4o-mini (%d chars)...", len(pdf_text))

    response = client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[
            {"role": "system", "content": _SYSTEM_PROMPT},
            {"role": "user", "content": user_message},
        ],
        response_format={"type": "json_object"},
        temperature=0,
        max_tokens=4096,
    )

    raw_json = response.choices[0].message.content
    logger.debug("Respuesta OpenAI: %s", raw_json[:500] if raw_json else "(vacío)")

    if not raw_json:
        raise RuntimeError("OpenAI devolvió respuesta vacía")

    return json.loads(raw_json)


# ---------------------------------------------------------------------------
# Normalize & validate output
# ---------------------------------------------------------------------------

def _normalize_result(raw: Dict[str, Any]) -> Dict[str, Any]:
    """Normaliza y valida la respuesta de OpenAI al formato esperado."""

    proforma = str(raw.get("proforma_number") or "DESCONOCIDO").strip()
    client = str(raw.get("client_name") or "DESCONOCIDO").strip()

    raw_items = raw.get("items") or []
    items: List[Dict[str, Any]] = []

    for item in raw_items:
        if not isinstance(item, dict):
            continue

        description = str(item.get("description") or "").strip()
        if not description:
            continue

        zone = str(item.get("zone") or "GENERAL").strip()
        if not zone:
            zone = "GENERAL"

        # Normalizar quantity
        qty_raw = item.get("quantity", 1)
        try:
            quantity = float(qty_raw)
            if quantity <= 0:
                quantity = 1.0
        except (TypeError, ValueError):
            # Intentar extraer número de string
            match = re.search(r"[\d.,]+", str(qty_raw))
            if match:
                try:
                    quantity = float(match.group().replace(",", "."))
                except ValueError:
                    quantity = 1.0
            else:
                quantity = 1.0

        items.append({
            "sku": None,
            "description": description,
            "quantity": quantity,
            "unit": "unidad",
            "zone": zone,
        })

    return {
        "proforma_number": proforma,
        "client_name": client,
        "items": items,
    }


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def parse_quote_pdf(pdf_bytes: bytes) -> Dict[str, Any]:
    """
    Parsea una cotización PDF de Luxury Lights / Alegra usando GPT-4o-mini.

    Returns
    -------
    {
        "proforma_number": str,
        "client_name":     str,
        "items": [
            {"sku": None, "description": str, "quantity": float,
             "unit": str, "zone": str},
            ...
        ]
    }
    """
    result: Dict[str, Any] = {
        "proforma_number": "DESCONOCIDO",
        "client_name": "DESCONOCIDO",
        "items": [],
    }

    try:
        # 1. Extraer texto con pdfplumber
        pdf_text = _extract_text_from_pdf(pdf_bytes)

        if not pdf_text.strip():
            logger.warning("PDF no tiene texto extraíble (posiblemente imagen escaneada)")
            return result

        # 2. Enviar a OpenAI
        raw = _extract_with_openai(pdf_text)

        # 3. Normalizar
        result = _normalize_result(raw)

    except Exception as exc:
        logger.error("Error parseando PDF: %s", exc, exc_info=True)
        raise RuntimeError(f"No se pudo parsear el PDF: {exc}") from exc

    logger.info(
        "PDF parseado ✓ → proforma=%s | cliente=%s | items=%d",
        result["proforma_number"],
        result["client_name"],
        len(result["items"]),
    )
    return result
