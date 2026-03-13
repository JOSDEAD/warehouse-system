"""
pdf_parser.py
=============
Parser específico para cotizaciones de Alegra (Luxury Lights).

Estructura conocida del PDF:
- Las columnas son texto posicionado, NO tablas HTML con bordes.
  extract_tables() solo captura el cuadro de "Total" al pie.
- Columnas (coordenadas X aproximadas en puntos):
    Referencia    :   0 – 102
    Descripción   : 103 – 335
    Precio        : 336 – 392
    Cantidad      : 393 – 448
    Descuento     : 449 – 528
    Total         : 529 +
- La columna "Referencia" (zona) solo aparece en el PRIMER ítem de cada
  grupo. Los ítems siguientes tienen esa celda vacía y heredan la última
  referencia vista (zone inheritance).
- El nombre del cliente aparece en ALL CAPS antes de "Cedula" / "Tel".
- El número de cotización aparece como "Cotización NNNN" en el encabezado.
"""

from __future__ import annotations

import io
import logging
import re
from typing import Any, Dict, List, Optional, Tuple

import pdfplumber

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Column X-boundaries  (puntos PDF, ~1/72 pulgada)
# Ajustados a las coordenadas reales de las cotizaciones de Luxury Lights
# ---------------------------------------------------------------------------
_COLS: Dict[str, Tuple[float, float]] = {
    "reference":   (0.0,   102.0),
    "description": (103.0, 335.0),
    "price":       (336.0, 392.0),
    "quantity":    (393.0, 448.0),
    "discount":    (449.0, 528.0),
    "total":       (529.0, 9999.0),
}

# Palabras que indican el encabezado de la tabla de ítems
_HEADER_KEYWORDS = {"referencia", "producto", "servicio", "descripci", "cantidad", "precio"}

# Palabras que indican filas de totales / pie de tabla → parar el parsing
_FOOTER_KEYWORDS = {"subtotal", "descuento", "iva", "igv", "total", "observaci", "nota", "términos"}

# Y máxima del bloque de cliente en el encabezado del PDF (puntos)
# El cliente aparece entre y≈130 y y≈190 en las cotizaciones de Alegra
_CLIENT_Y_MAX = 195.0
_CLIENT_Y_MIN = 120.0


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _normalize(text: str) -> str:
    return re.sub(r"\s+", " ", text.lower().strip())


def _is_header_row(row_text: str) -> bool:
    n = _normalize(row_text)
    return any(kw in n for kw in _HEADER_KEYWORDS)


def _is_footer_row(row_text: str) -> bool:
    n = _normalize(row_text)
    return any(kw in n for kw in _FOOTER_KEYWORDS)


def _col_for_word(x0: float) -> Optional[str]:
    """Return the column name for a word starting at x0, or None if outside all cols."""
    for col_name, (x_min, x_max) in _COLS.items():
        if x_min <= x0 < x_max:
            return col_name
    return None


def _group_words_into_rows(
    words: List[Dict], row_tolerance: float = 3.0
) -> List[Tuple[float, List[Dict]]]:
    """
    Group words by vertical position (top).
    Returns sorted list of (y_bucket, [words]) tuples.
    """
    buckets: Dict[float, List[Dict]] = {}
    for word in words:
        y = round(word["top"] / row_tolerance) * row_tolerance
        buckets.setdefault(y, []).append(word)
    return sorted(buckets.items())


def _row_cells(row_words: List[Dict]) -> Dict[str, str]:
    """
    Map a list of words to column values using X-position boundaries.
    Words in the same column are joined with a space.
    """
    cols: Dict[str, List[str]] = {c: [] for c in _COLS}
    for word in sorted(row_words, key=lambda w: w["x0"]):
        col = _col_for_word(word["x0"])
        if col:
            cols[col].append(word["text"])
    return {c: " ".join(v).strip() for c, v in cols.items()}


def _safe_float(value: str) -> Optional[float]:
    cleaned = re.sub(r"[^\d.,\-]", "", value).replace(",", ".")
    # Handle "1.234.56" style (thousands dot + decimal dot)
    parts = cleaned.split(".")
    if len(parts) > 2:
        cleaned = "".join(parts[:-1]) + "." + parts[-1]
    try:
        return float(cleaned)
    except ValueError:
        return None


# ---------------------------------------------------------------------------
# Client & proforma extraction from raw text
# ---------------------------------------------------------------------------

def _find_proforma_number(text: str) -> str:
    """
    Look for patterns like:
      "Cotización 3385", "Proforma N° 2024-001", "Cotización No. 100"
    """
    patterns = [
        r"cotizaci[oó]n\s+(?:n[°º]\.?\s*)?(\d+)",
        r"proforma\s+(?:n[°º]\.?\s*)?(\w[\w\-/]*)",
        r"(?:n[°º]|no\.)\s*(\d{2,})",
    ]
    for pattern in patterns:
        m = re.search(pattern, text, re.IGNORECASE)
        if m:
            return m.group(1).strip()
    return "UNKNOWN"


def _find_client_name_from_words(all_words: List[Dict]) -> str:
    """
    In Alegra PDFs the client block is in the header area (y ≈ 120–195).
    The client name is an ALL-CAPS line that comes before the Cedula / Tel line.
    Strategy:
      1. Collect words in the client Y band.
      2. Group into rows.
      3. Return the first row that is mostly uppercase and long enough.
    """
    client_words = [
        w for w in all_words
        if _CLIENT_Y_MIN <= w["top"] <= _CLIENT_Y_MAX
    ]
    if not client_words:
        return "UNKNOWN"

    rows = _group_words_into_rows(client_words, row_tolerance=3.0)
    for _, row_words in rows:
        text = " ".join(w["text"] for w in sorted(row_words, key=lambda w: w["x0"]))
        text = text.strip()
        # Skip obvious non-names
        low = text.lower()
        if any(kw in low for kw in ("cedula", "tel", "correo", "email", "@", "ruc", "nit")):
            continue
        # Must look like a proper name (mostly alpha, at least 5 chars)
        alpha_ratio = sum(c.isalpha() or c == " " for c in text) / max(len(text), 1)
        if alpha_ratio > 0.7 and len(text) >= 5:
            return text
    return "UNKNOWN"


def _find_client_from_text(text: str) -> str:
    """
    Fallback: regex over raw text for known labels.
    """
    patterns = [
        r"(?:cliente|customer|para|se[ñn]or(?:a)?|sra?\.?)\s*[:\-]?\s*(.+)",
        r"aten(?:ci[oó]n)?\s*[:\-]?\s*(.+)",
        r"nombre\s*[:\-]?\s*(.+)",
    ]
    for pattern in patterns:
        for line in text.splitlines():
            m = re.search(pattern, line, re.IGNORECASE)
            if m:
                candidate = m.group(1).strip()
                if candidate and len(candidate) < 120:
                    return re.sub(r"[:\-]+$", "", candidate).strip()
    return "UNKNOWN"


# ---------------------------------------------------------------------------
# Main item extraction  (position-based, zone-inheritance)
# ---------------------------------------------------------------------------

def _extract_items(pdf: pdfplumber.PDF) -> List[Dict[str, Any]]:
    """
    Extract line items from ALL pages using word X-positions.
    Implements zone inheritance: empty reference cell → use last seen reference.
    """
    items: List[Dict[str, Any]] = []
    current_zone: str = ""
    in_items_section = False

    for page_num, page in enumerate(pdf.pages, start=1):
        words = page.extract_words(keep_blank_chars=False, x_tolerance=3, y_tolerance=3)
        rows = _group_words_into_rows(words, row_tolerance=2.5)

        for y, row_words in rows:
            row_text = " ".join(w["text"] for w in row_words)

            # Detect header row
            if not in_items_section:
                if _is_header_row(row_text):
                    in_items_section = True
                    logger.debug("Page %d: header row found at y=%.1f", page_num, y)
                continue

            # Detect footer / totals block → stop
            if _is_footer_row(row_text):
                logger.debug("Page %d: footer row at y=%.1f — stopping", page_num, y)
                in_items_section = False
                break  # Stop for this page; next page resets

            cells = _row_cells(row_words)
            description = cells.get("description", "").strip()
            if not description:
                continue  # skip blank rows

            # Zone inheritance
            ref = cells.get("reference", "").strip()
            if ref:
                current_zone = ref
            # else: keep current_zone from previous row

            # Parse quantity
            qty_str = cells.get("quantity", "")
            quantity = _safe_float(qty_str) if qty_str else None
            if quantity is None:
                # Try to find a number anywhere in row as fallback
                for cell_val in cells.values():
                    q = _safe_float(cell_val)
                    if q is not None and 0 < q < 10_000:
                        quantity = q
                        break
            if quantity is None:
                quantity = 1.0

            items.append({
                "sku": None,        # Alegra PDFs don't have SKU column
                "description": description,
                "quantity": quantity,
                "unit": "unidad",
                "zone": current_zone,
            })
            logger.debug(
                "  item: zone=%r desc=%r qty=%s",
                current_zone, description[:40], quantity
            )

        # After page 1+, the header won't repeat on each page in Alegra PDFs.
        # Re-enable item parsing at start of continuation pages.
        if page_num > 1 and not in_items_section:
            in_items_section = True

    return items


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def parse_quote_pdf(pdf_bytes: bytes) -> Dict[str, Any]:
    """
    Parse a Luxury Lights / Alegra PDF cotización.

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
        "proforma_number": "UNKNOWN",
        "client_name": "UNKNOWN",
        "items": [],
    }

    try:
        with pdfplumber.open(io.BytesIO(pdf_bytes)) as pdf:
            # ── Extract full text for header fields ──────────────────────────
            full_text_parts = []
            all_words: List[Dict] = []
            for page in pdf.pages:
                t = page.extract_text()
                if t:
                    full_text_parts.append(t)
                all_words.extend(page.extract_words(x_tolerance=3, y_tolerance=3))

            full_text = "\n".join(full_text_parts)

            if not full_text.strip():
                logger.warning("PDF produced no extractable text — posiblemente imagen escaneada")
                return result

            # ── Proforma number ───────────────────────────────────────────────
            result["proforma_number"] = _find_proforma_number(full_text)

            # ── Client name: try word-position first, then regex fallback ─────
            client = _find_client_name_from_words(all_words)
            if client == "UNKNOWN":
                client = _find_client_from_text(full_text)
            result["client_name"] = client

            # ── Line items (position-based with zone inheritance) ─────────────
            result["items"] = _extract_items(pdf)

    except Exception as exc:
        logger.error("PDF parsing failed: %s", exc, exc_info=True)
        raise RuntimeError(f"Could not parse PDF: {exc}") from exc

    logger.info(
        "Parsed PDF → proforma=%s | client=%s | items=%d",
        result["proforma_number"],
        result["client_name"],
        len(result["items"]),
    )
    return result
