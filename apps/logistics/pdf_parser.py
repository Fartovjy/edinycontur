"""
PDF parsers for logistics request creation.

parse_order_pdf   — «Заказ клиента» (existing format)
parse_invoice_pdf — «Счёт-проформа / Proforma Invoice» (Biovet-K format)
parse_pdf_auto    — auto-detect format and dispatch to the right parser
"""

import re
from datetime import date

import pdfplumber

MONTH_MAP = {
    "января": 1, "февраля": 2, "марта": 3, "апреля": 4,
    "мая": 5, "июня": 6, "июля": 7, "августа": 8,
    "сентября": 9, "октября": 10, "ноября": 11, "декабря": 12,
}

_LEGAL_FORMS_RE = re.compile(
    r'^(ООО|ЗАО|ОАО|ПАО|АО|ИП|ГУП|МУП|НКО|ФГУП|СХПК|СПК|КФХ)\s*["\']?',
    re.IGNORECASE,
)

# Trailing slash (column separator artifact) — strip from any name
_TRAILING_SLASH_RE = re.compile(r'\s*/\s*$')


def _strip_slash(s: str) -> str:
    return _TRAILING_SLASH_RE.sub("", s).strip()


def _parse_кому_cell(text: str, result: dict) -> None:
    """
    Parse the merged КОМУ/SENT TO cell that contains all recipient fields:
        Company Name, ФИО/Contact Person, Address
    Fields are separated by ' /' (space + slash).
    """
    # Company name: from 'Company Name:' to the first ' /'
    # Cell format: «Company Name: АО "ФАБ\nРИКА" /\nФИО/ Contact…»
    m = re.search(r"Company Name:\s*(.+?)\s*/", text, re.DOTALL)
    if m:
        raw = re.sub(r"\s+", " ", m.group(1)).strip()
        result["client_name_raw"] = raw
        clean = _LEGAL_FORMS_RE.sub("", raw).strip().strip("\"'")
        result["client_name"] = clean if clean else raw

    # Contact person: from 'Contact Person:' to ' /'
    m = re.search(r"Contact Person:\s*(.+?)\s*/", text, re.DOTALL)
    if m:
        result["client_contact"] = re.sub(r"\s+", " ", m.group(1)).strip()

    # Address: from 'Address:' to ' /' (may span two lines)
    m = re.search(r"Адрес/\s*Address:\s*(.+?)\s*/", text, re.DOTALL)
    if m:
        result["client_address"] = re.sub(r"\s+", " ", m.group(1)).strip()


def _parse_date_slash(s: str):
    """Parse DD/MM/YYYY → date."""
    m = re.match(r"(\d{1,2})/(\d{1,2})/(\d{4})", s.strip())
    if m:
        try:
            return date(int(m.group(3)), int(m.group(2)), int(m.group(1)))
        except ValueError:
            pass
    return None


def _parse_date(day_s, month_s, year_s):
    try:
        month = MONTH_MAP.get(month_s.strip().lower(), 0)
        if month:
            return date(int(year_s), month, int(day_s))
    except (ValueError, TypeError):
        pass
    return None


def _build_cargo_description(items):
    lines = []
    for item in items:
        line = f"{item['num']}. {item['name']}"
        if item.get("qty"):
            line += f" — {item['qty']}"
        lines.append(line)
    return "\n".join(lines)


# ══════════════════════════════════════════════════════════════════════════
# Parser 1 — «Заказ клиента»
# ══════════════════════════════════════════════════════════════════════════

def parse_order_pdf(file_obj) -> dict:
    """
    Parse a «Заказ клиента» PDF.

    pdfplumber extract_text() produces lines where the left column (labels)
    and the right column (values) are interleaved — the value line comes
    BEFORE its label line.  Example:
        'ООО "ЗАОКСКОЕ", ИНН 7126019531 ...'   ← value of Грузополучатель
        'Грузополучатель:'                       ← label
        'строение 1, тел.: +7(916)6408233'       ← value continuation / phone

    The items table has 6 columns:
        №  |  name  |  qty  |  unit  |  price  |  total
    """
    result = {
        "order_number": "",
        "order_date": None,
        "client_name": "",
        "client_name_raw": "",
        "client_phone": "",
        "client_contact": "",
        "client_address": "",
        "items": [],
        "cargo_description": "",
        "cargo_places_count": 1,
        "cargo_weight_kg": None,
    }

    with pdfplumber.open(file_obj) as pdf:
        full_text = "\n".join(page.extract_text() or "" for page in pdf.pages)
        lines = full_text.split("\n")

        # ── Заголовок: № и дата ──────────────────────────────────────────
        m = re.search(
            r"Заказ клиента\s*№\s*(\d+)\s+от\s+(\d+)\s+(\w+)\s+(\d{4})",
            full_text,
        )
        if m:
            result["order_number"] = m.group(1)
            result["order_date"] = _parse_date(m.group(2), m.group(3), m.group(4))

        # ── Грузополучатель ───────────────────────────────────────────────
        for i, line in enumerate(lines):
            if line.strip() == "Грузополучатель:":
                value_line = lines[i - 1].strip() if i > 0 else ""
                cont_line  = lines[i + 1].strip() if i + 1 < len(lines) else ""

                m2 = re.match(r"^(.+?),\s*ИНН", value_line)
                if m2:
                    raw = m2.group(1).strip()
                    result["client_name_raw"] = raw
                    clean = _LEGAL_FORMS_RE.sub("", raw).strip().strip("\"'")
                    result["client_name"] = clean if clean else raw

                pm = re.search(r"тел[.:]+\s*([\+\d\(\)\-\s]{7,})", cont_line)
                if pm:
                    result["client_phone"] = pm.group(1).strip().rstrip(",")
                break

        # ── Адрес доставки ────────────────────────────────────────────────
        m = re.search(r"Адрес доставки:\s*(.+?)(?:\n|$)", full_text)
        if m:
            result["client_address"] = m.group(1).strip()

        # ── Таблица товаров ───────────────────────────────────────────────
        for page in pdf.pages:
            for table in page.extract_tables():
                for row in table:
                    if not row:
                        continue
                    cell0 = str(row[0] or "").strip()
                    if not re.match(r"^\d+$", cell0):
                        continue
                    name = _strip_slash(str(row[1] or "").strip().replace("\n", " "))
                    qty_raw  = str(row[2] or "").strip().replace("\n", " ")
                    unit_raw = str(row[3] or "").strip().replace("\n", " ") if len(row) > 3 else ""
                    qty_parts = [p for p in [qty_raw, unit_raw] if p]
                    qty = " ".join(qty_parts)
                    if name:
                        result["items"].append({"num": cell0, "name": name, "qty": qty})

        if result["items"]:
            result["cargo_description"] = _build_cargo_description(result["items"])
            result["cargo_places_count"] = len(result["items"])

    return result


# ══════════════════════════════════════════════════════════════════════════
# Parser 2 — «Счёт-проформа / Proforma Invoice»
# ══════════════════════════════════════════════════════════════════════════

def parse_invoice_pdf(file_obj) -> dict:
    """
    Parse a Biovet-K «Счёт-проформа» PDF using table extraction.

    The PDF has one wide table (17 cols) with:
      • row where col0 contains 'Company Name:' AND col9 contains 'Кол-во мест':
            col0 — merged КОМУ cell (company, contact, address)
            col14 — number of pieces
      • row where col9 contains 'Вес брутто' / 'Gross Weight':
            col14 — gross weight
      • rows where col0 is a digit:
            col1 — item description
            col9 — quantity (Количество вложений, шт)
    """
    result = {
        "order_number": "",
        "order_date": None,
        "client_name": "",
        "client_name_raw": "",
        "client_phone": "",
        "client_contact": "",
        "client_address": "",
        "items": [],
        "cargo_description": "",
        "cargo_places_count": 0,
        "cargo_weight_kg": None,
    }

    with pdfplumber.open(file_obj) as pdf:
        full_text = "\n".join(page.extract_text() or "" for page in pdf.pages)

        # ── Номер и дата документа (из текста, т.к. в таблице разбиты по ячейкам) ──
        m = re.search(
            r"(?:INVOICE|ИНВОЙС|ПРОФОРМА)[^\n]*№\s*([\w/\-]+)\s+Дата/Date:\s*(\d{2}/\d{2}/\d{4})",
            full_text, re.IGNORECASE,
        )
        if m:
            result["order_number"] = m.group(1).strip()
            result["order_date"] = _parse_date_slash(m.group(2))

        # ── Таблица: всё остальное ────────────────────────────────────────
        for page in pdf.pages:
            for table in page.extract_tables():
                if not table or not table[0] or len(table[0]) < 10:
                    continue
                for row in table:
                    if not row or len(row) < 10:
                        continue
                    c0  = str(row[0]  or "").strip()
                    c9  = str(row[9]  or "").strip()
                    c14 = str(row[14] or "").replace("\xa0", "").strip() if len(row) > 14 else ""

                    # ── КОМУ-ячейка: название, контакт, адрес, кол-во мест ─
                    if "Company Name:" in c0 and ("Кол-во мест" in c9 or "Number of pieces" in c9):
                        _parse_кому_cell(c0, result)
                        if c14:
                            try:
                                result["cargo_places_count"] = int(c14.replace(" ", ""))
                            except ValueError:
                                pass

                    # ── Строка веса брутто ────────────────────────────────
                    elif "Вес брутто" in c9 or "Gross Weight" in c9:
                        if c14:
                            try:
                                val = c14.replace(" ", "").replace(",", ".")
                                result["cargo_weight_kg"] = float(val)
                            except ValueError:
                                pass

                    # ── Строки товаров ────────────────────────────────────
                    elif re.match(r"^\d+$", c0) and len(row) > 1:
                        name = _strip_slash(str(row[1] or "").strip().replace("\n", " "))
                        qty  = c9   # col9 = «Количество вложений, шт / Quantity, pcs»
                        if name:
                            result["items"].append({"num": c0, "name": name, "qty": qty})

        if result["items"]:
            result["cargo_description"] = _build_cargo_description(result["items"])
            if not result["cargo_places_count"]:
                result["cargo_places_count"] = len(result["items"])

    return result


# ══════════════════════════════════════════════════════════════════════════
# Auto-detect dispatcher
# ══════════════════════════════════════════════════════════════════════════

def parse_pdf_auto(file_obj) -> dict:
    """
    Detect PDF format by content and call the right parser.
    Returns (parsed_dict, format_name).
    """
    # Peek at first page text to detect format
    file_obj.seek(0)
    with pdfplumber.open(file_obj) as pdf:
        first_text = pdf.pages[0].extract_text() or "" if pdf.pages else ""

    file_obj.seek(0)

    if re.search(r"PROFORMA INVOICE|СЧЕТ-ПРОФОРМА|PROFORMA", first_text, re.IGNORECASE):
        return parse_invoice_pdf(file_obj), "invoice"

    return parse_order_pdf(file_obj), "order"
