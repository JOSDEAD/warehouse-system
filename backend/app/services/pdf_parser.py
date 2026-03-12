"""
pdf_parser.py
=============
Robust PDF quote / proforma invoice parser built on pdfplumber.

Strategy
--------
1. Open the PDF from raw bytes.
2. Extract the full plain text (all pages concatenated).
3. Use regex patterns to locate the proforma number and client name from the text.
4. Extract tables from every page and try to map their columns to the expected
   fields (description, quantity, unit, zone, SKU).
5. If no usable table is found, fall back to line-by-line parsing of the text.

Returns a dict:
{
    "proforma_number": str,
    "client_name":     str,
    "items": [
        {
            "sku":         str | None,
            "description": str,
            "quantity":    float,
            "unit":        str,
            "zone":        str,
        },
        ...
    ],
}
"""

from __future__ import annotations

import io
import logging
import re
from typing import Any, Dict, List, Optional

import pdfplumber

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Regex helpers
# ---------------------------------------------------------------------------

_PROFORMA_PATTERNS = [
    # "Proforma N° 2024-001", "Cotización #42", "No. 100", etc.
    r"(?:proforma|cotizaci[oó]n|n[uú]mero|n[°º]|no\.|#)\s*[:\-]?\s*([A-Z0-9\-/]+)",
    # bare leading number like "001"
    r"^(\d{3,})\s",
]

_CLIENT_PATTERNS = [
    # "Cliente: Acme Corp", "Customer: John", "Para: María", "Señor: …", "Sra.: …"
    r"(?:cliente|customer|para|se[ñn]or(?:a)?|sra?\.?)\s*[:\-]?\s*(.+)",
    # "Atención: Nombre"
    r"aten(?:ci[oó]n)?\s*[:\-]?\s*(.+)",
]

# Column keyword groups for flexible header matching
_COL_DESCRIPTION = {"descripci", "description", "item", "producto", "detalle", "concepto", "articulo", "artículo"}
_COL_QUANTITY    = {"cantidad", "qty", "cant", "quantity", "ctd", "ctdad"}
_COL_UNIT        = {"unidad", "unit", "um", "u/m", "medida"}
_COL_ZONE        = {"zona", "zone", "ubicaci", "area", "área", "sector"}
_COL_SKU         = {"sku", "c[oó]digo", "codigo", "ref", "referencia", "code", "clave"}


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _normalize(text: str) -> str:
    """Lower-case, strip, collapse whitespace."""
    return re.sub(r"\s+", " ", text.lower().strip())


def _matches_keywords(header: str, keywords: set) -> bool:
    h = _normalize(header)
    return any(kw in h for kw in keywords)


def _extract_text(pdf: pdfplumber.PDF) -> str:
    parts: list[str] = []
    for page in pdf.pages:
        text = page.extract_text()
        if text:
            parts.append(text)
    return "\n".join(parts)


def _find_proforma_number(text: str) -> str:
    for pattern in _PROFORMA_PATTERNS:
        for line in text.splitlines():
            m = re.search(pattern, line, re.IGNORECASE)
            if m:
                candidate = m.group(1).strip()
                if candidate:
                    return candidate
    return "UNKNOWN"


def _find_client_name(text: str) -> str:
    for pattern in _CLIENT_PATTERNS:
        for line in text.splitlines():
            m = re.search(pattern, line, re.IGNORECASE)
            if m:
                candidate = m.group(1).strip()
                # Reject obviously bad matches (e.g., very long lines that
                # happen to contain the keyword)
                if candidate and len(candidate) < 120:
                    # Remove trailing punctuation
                    candidate = re.sub(r"[:\-]+$", "", candidate).strip()
                    if candidate:
                        return candidate
    return "UNKNOWN"


def _map_columns(headers: List[Optional[str]]) -> Dict[str, int]:
    """
    Given a list of header strings (some may be None), return a mapping
    {field_name: column_index}.
    """
    mapping: Dict[str, int] = {}
    for idx, header in enumerate(headers):
        if header is None:
            continue
        if "description" not in mapping and _matches_keywords(header, _COL_DESCRIPTION):
            mapping["description"] = idx
        if "quantity" not in mapping and _matches_keywords(header, _COL_QUANTITY):
            mapping["quantity"] = idx
        if "unit" not in mapping and _matches_keywords(header, _COL_UNIT):
            mapping["unit"] = idx
        if "zone" not in mapping and _matches_keywords(header, _COL_ZONE):
            mapping["zone"] = idx
        if "sku" not in mapping and _matches_keywords(header, _COL_SKU):
            mapping["sku"] = idx
    return mapping


def _safe_float(value: Any) -> Optional[float]:
    if value is None:
        return None
    cleaned = re.sub(r"[^\d.,\-]", "", str(value)).replace(",", ".")
    try:
        return float(cleaned)
    except ValueError:
        return None


def _parse_table(table: List[List[Optional[str]]]) -> Optional[List[Dict]]:
    """
    Attempt to parse a pdfplumber table into a list of item dicts.
    Returns None if the table does not look like a line-item table.
    """
    if not table or len(table) < 2:
        return None

    # Identify the header row: first row that has recognizable column keywords
    header_idx: Optional[int] = None
    col_map: Dict[str, int] = {}

    for i, row in enumerate(table):
        candidate_map = _map_columns([str(cell) if cell else "" for cell in row])
        if "description" in candidate_map or "quantity" in candidate_map:
            header_idx = i
            col_map = candidate_map
            break

    if header_idx is None or "description" not in col_map:
        return None

    items: List[Dict] = []
    for row in table[header_idx + 1:]:
        if not row or all(cell is None or str(cell).strip() == "" for cell in row):
            continue

        def get_cell(field: str) -> str:
            idx = col_map.get(field)
            if idx is None or idx >= len(row):
                return ""
            return str(row[idx]).strip() if row[idx] is not None else ""

        description = get_cell("description")
        if not description:
            continue

        # Skip rows that look like sub-headers or totals
        desc_lower = description.lower()
        if any(kw in desc_lower for kw in ("total", "subtotal", "descuento", "iva", "igv", "tax")):
            continue

        raw_qty = get_cell("quantity")
        quantity = _safe_float(raw_qty) if raw_qty else None
        if quantity is None:
            # Try to find a number anywhere in the row
            for cell in row:
                if cell:
                    q = _safe_float(str(cell))
                    if q is not None and q > 0:
                        quantity = q
                        break
        if quantity is None:
            quantity = 1.0

        items.append(
            {
                "sku": get_cell("sku") or None,
                "description": description,
                "quantity": quantity,
                "unit": get_cell("unit") or "unidad",
                "zone": get_cell("zone") or "",
            }
        )

    return items if items else None


# ---------------------------------------------------------------------------
# Fallback: line-by-line parsing
# ---------------------------------------------------------------------------

# Patterns that hint at a product line:
# "SKU001 - Some product - 5 cajas"
# "• Description | 10 | piezas"
_LINE_ITEM_PATTERNS = [
    # SKU - Description - Qty Unit
    re.compile(
        r"(?P<sku>[A-Z0-9\-]{2,20})\s+[\-|]\s+(?P<desc>.+?)\s+[\-|]\s+(?P<qty>\d+[.,]?\d*)\s*(?P<unit>\w+)?",
        re.IGNORECASE,
    ),
    # Qty x Description
    re.compile(
        r"(?P<qty>\d+[.,]?\d*)\s*x\s+(?P<desc>.{3,80})",
        re.IGNORECASE,
    ),
    # Numbered list: "1. Description 10 u"
    re.compile(
        r"^\s*\d+[\.\)]\s+(?P<desc>.{3,80}?)\s+(?P<qty>\d+[.,]?\d*)\s*(?P<unit>[a-zA-Z]{1,10})?\s*$",
        re.IGNORECASE,
    ),
]


def _fallback_line_parse(text: str) -> List[Dict]:
    items: List[Dict] = []
    for line in text.splitlines():
        line = line.strip()
        if not line or len(line) < 5:
            continue
        for pattern in _LINE_ITEM_PATTERNS:
            m = pattern.search(line)
            if m:
                groups = m.groupdict()
                qty = _safe_float(groups.get("qty", "1")) or 1.0
                items.append(
                    {
                        "sku": groups.get("sku"),
                        "description": groups.get("desc", line).strip(),
                        "quantity": qty,
                        "unit": (groups.get("unit") or "unidad").strip(),
                        "zone": "",
                    }
                )
                break
    return items


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def parse_quote_pdf(pdf_bytes: bytes) -> Dict[str, Any]:
    """
    Parse a PDF quote / proforma and return extracted structured data.

    Parameters
    ----------
    pdf_bytes : bytes
        Raw bytes of the PDF file.

    Returns
    -------
    dict with keys: proforma_number, client_name, items
    """
    result: Dict[str, Any] = {
        "proforma_number": "UNKNOWN",
        "client_name": "UNKNOWN",
        "items": [],
    }

    try:
        with pdfplumber.open(io.BytesIO(pdf_bytes)) as pdf:
            full_text = _extract_text(pdf)

            if not full_text.strip():
                logger.warning("PDF produced no extractable text — possibly scanned image")
                return result

            result["proforma_number"] = _find_proforma_number(full_text)
            result["client_name"] = _find_client_name(full_text)

            # Try every table on every page
            all_items: List[Dict] = []
            for page_num, page in enumerate(pdf.pages, start=1):
                tables = page.extract_tables()
                for tbl_idx, table in enumerate(tables):
                    parsed = _parse_table(table)
                    if parsed:
                        logger.info(
                            "Parsed %d items from page %d, table %d",
                            len(parsed), page_num, tbl_idx,
                        )
                        all_items.extend(parsed)

            if all_items:
                result["items"] = all_items
            else:
                logger.info("No structured tables found — falling back to line parsing")
                result["items"] = _fallback_line_parse(full_text)

    except Exception as exc:
        logger.error("PDF parsing failed: %s", exc, exc_info=True)
        raise RuntimeError(f"Could not parse PDF: {exc}") from exc

    logger.info(
        "Parsed PDF: proforma=%s, client=%s, items=%d",
        result["proforma_number"],
        result["client_name"],
        len(result["items"]),
    )
    return result
