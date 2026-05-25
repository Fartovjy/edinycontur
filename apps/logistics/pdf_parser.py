"""
Parser for "Заказ клиента" PDF documents.

pdfplumber extract_text() produces lines where the left column (labels)
and the right column (values) are interleaved — the value line comes
BEFORE its label line.  Example:

    'ООО "ЗАОКСКОЕ", ИНН 7126019531 ...'   ← value of Грузополучатель
    'Грузополучатель:'                       ← label
    'строение 1, тел.: +7(916)6408233'       ← value continuation / phone

The items table has 6 columns:
    №  |  name  |  qty  |  unit  |  price  |  total
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


def _parse_date(day_s, month_s, year_s):
    try:
        month = MONTH_MAP.get(month_s.strip().lower(), 0)
        if month:
            return date(int(year_s), month, int(day_s))
    except (ValueError, TypeError):
        pass
    return None


def parse_order_pdf(file_obj) -> dict:
    """
    Parse a PDF file-like object.
    Returns a dict with keys:
        order_number, order_date,
        client_name, client_name_raw, client_phone, client_address,
        items, cargo_description, cargo_places_count
    """
    result = {
        "order_number": "",
        "order_date": None,
        "client_name": "",
        "client_name_raw": "",
        "client_phone": "",
        "client_address": "",
        "items": [],
        "cargo_description": "",
        "cargo_places_count": 1,
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

        # ── Грузополучатель: значение идёт ПЕРЕД лейблом ─────────────────
        # Структура extracted text (из-за двух колонок PDF):
        #   line[i-1]: 'ООО "ЗАОКСКОЕ", ИНН ...'
        #   line[i]  : 'Грузополучатель:'
        #   line[i+1]: 'строение 1, тел.: ...'
        for i, line in enumerate(lines):
            if line.strip() == "Грузополучатель:":
                # Значение (первая часть) — на строке выше
                value_line = lines[i - 1].strip() if i > 0 else ""
                # Телефон — на строке ниже (продолжение значения)
                cont_line = lines[i + 1].strip() if i + 1 < len(lines) else ""

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
        # Колонки: № | name | qty | unit | price | total
        # qty + unit объединяем в одну строку количества
        for page in pdf.pages:
            for table in page.extract_tables():
                for row in table:
                    if not row:
                        continue
                    cell0 = str(row[0] or "").strip()
                    if not re.match(r"^\d+$", cell0):
                        continue
                    name = str(row[1] or "").strip().replace("\n", " ")
                    qty_raw = str(row[2] or "").strip().replace("\n", " ")
                    unit_raw = str(row[3] or "").strip().replace("\n", " ") if len(row) > 3 else ""
                    # Собираем читаемое количество
                    qty_parts = [p for p in [qty_raw, unit_raw] if p]
                    qty = " ".join(qty_parts)
                    if name:
                        result["items"].append(
                            {"num": cell0, "name": name, "qty": qty}
                        )

        # ── Описание груза ────────────────────────────────────────────────
        if result["items"]:
            lines_out = []
            for item in result["items"]:
                line = f"{item['num']}. {item['name']}"
                if item["qty"]:
                    line += f" — {item['qty']}"
                lines_out.append(line)
            result["cargo_description"] = "\n".join(lines_out)
            result["cargo_places_count"] = len(result["items"])

    return result
