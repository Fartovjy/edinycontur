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
    Parse a Biovet-K «Счёт-проформа» PDF.

    Extracts from the КОМУ / SENT TO section:
        company name, contact person, address,
        number of pieces, gross weight
    Extracts from the header:
        invoice number, date
    Extracts cargo rows from the table (strips trailing '/').
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

        # ── Номер и дата документа ────────────────────────────────────────
        # «СЧЕТ-ПРОФОРМА / PROFORMA INVOICE № 462/2026 Дата/Date: 19/05/2026»
        m = re.search(
            r"(?:INVOICE|ИНВОЙС|ПРОФОРМА)[^\n]*№\s*([\w/\-]+)\s+Дата/Date:\s*(\d{2}/\d{2}/\d{4})",
            full_text, re.IGNORECASE,
        )
        if m:
            result["order_number"] = m.group(1).strip()
            result["order_date"] = _parse_date_slash(m.group(2))

        # ── Находим начало раздела КОМУ ───────────────────────────────────
        sent_to_pos = full_text.find("КОМУ / SENT TO")
        if sent_to_pos == -1:
            sent_to_pos = full_text.find("SENT TO")
        кому = full_text[sent_to_pos:] if sent_to_pos != -1 else full_text

        # Схлопываем переносы строк в пробелы, чтобы многострочные поля
        # (название компании, адрес) извлекались корректно.
        кому_flat = re.sub(r"[ \t]*\n[ \t]*", " ", кому)
        full_text_flat = re.sub(r"[ \t]*\n[ \t]*", " ", full_text)

        # ── Компания-получатель ───────────────────────────────────────────
        # «Компания/Company Name: АО "ПТИЦЕФАБРИКА ВЕРХНЕВОЛЖСКАЯ" /»
        m = re.search(r"Компания/Company Name:\s*(.+?)\s*/", кому_flat)
        if m:
            raw = re.sub(r"\s+", " ", m.group(1)).strip()
            result["client_name_raw"] = raw
            clean = _LEGAL_FORMS_RE.sub("", raw).strip().strip("\"'")
            result["client_name"] = clean if clean else raw

        # ── Контактное лицо ───────────────────────────────────────────────
        # «ФИО/ Contact Person: Заднепровского Валерия Владимировича /»
        m = re.search(r"ФИО/\s*Contact Person:\s*(.+?)\s*/", кому_flat)
        if m:
            result["client_contact"] = m.group(1).strip()

        # ── Адрес ─────────────────────────────────────────────────────────
        # «Адрес/ Address: 170554, Тверская область, ... зд. 72 /»
        # Правая колонка добавляет числа (вес) в строку — чистим их.
        m = re.search(r"Адрес/\s*Address:\s*(.+?)\s*/", кому_flat)
        if m:
            addr = re.sub(r"\s+", " ", m.group(1)).strip()
            # Убираем «хвостовые» числа из правой колонки (вес): «... зд. 72 3 345»
            addr = re.sub(r"(\s+\d[\d\s]{2,})$", "", addr).strip()
            result["client_address"] = addr

        # ── Количество мест ───────────────────────────────────────────────
        m = re.search(r"Number of pieces\s*:\s*(\d[\d\s]*)", full_text_flat)
        if m:
            try:
                result["cargo_places_count"] = int(m.group(1).replace(" ", "").rstrip())
            except ValueError:
                pass

        # ── Вес брутто ────────────────────────────────────────────────────
        m = re.search(r"Gross Weight\s*,\s*kg\s*:\s*(\d[\d\s,]*)", full_text_flat)
        if m:
            try:
                val = m.group(1).replace(" ", "").replace(",", ".").strip()
                result["cargo_weight_kg"] = float(val)
            except ValueError:
                pass

        # ── Таблица товаров ───────────────────────────────────────────────
        # Колонки: № | описание товара | HS Code | кол-во | цена | итого
        for page in pdf.pages:
            for table in page.extract_tables():
                for row in table:
                    if not row:
                        continue
                    cell0 = str(row[0] or "").strip()
                    if not re.match(r"^\d+$", cell0):
                        continue
                    name = _strip_slash(str(row[1] or "").strip().replace("\n", " "))
                    # qty — колонка 3 (после HS Code)
                    qty = ""
                    if len(row) > 3:
                        qty = str(row[3] or "").strip().replace("\n", " ")
                    if not qty and len(row) > 2:
                        qty = str(row[2] or "").strip().replace("\n", " ")
                    if name:
                        result["items"].append({"num": cell0, "name": name, "qty": qty})

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
