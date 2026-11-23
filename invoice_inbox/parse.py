"""Парсинг текста счёта в структуру Invoice.

Правила держим в одном месте: набор регулярных выражений под типовые российские
формы счетов. Всё, что не распозналось, остаётся None и попадает в issues —
никаких выдуманных значений.
"""

from __future__ import annotations

import datetime as dt
import re

from .validate import Invoice

MONEY = r"(\d{1,3}(?:[ \u00a0]\d{3})*(?:[.,]\d{2})?|\d+(?:[.,]\d{2})?)"

DOC_TYPES = (
    ("счёт-фактура", "Счёт-фактура"),
    ("счет-фактура", "Счёт-фактура"),
    ("упд", "УПД"),
    ("счёт на оплату", "Счёт на оплату"),
    ("счет на оплату", "Счёт на оплату"),
    ("товарная накладная", "Товарная накладная"),
    ("акт", "Акт"),
)

MONTHS = {
    "января": 1, "февраля": 2, "марта": 3, "апреля": 4, "мая": 5, "июня": 6,
    "июля": 7, "августа": 8, "сентября": 9, "октября": 10, "ноября": 11, "декабря": 12,
}


def to_amount(raw: str | None) -> float | None:
    """'48 000,50' -> 48000.5. Возвращает None, если строки нет."""
    if not raw:
        return None
    cleaned = raw.replace("\u00a0", "").replace(" ", "").replace(",", ".")
    try:
        return round(float(cleaned), 2)
    except ValueError:
        return None


def _search(text: str, pattern: str, flags: int = re.IGNORECASE | re.MULTILINE) -> str | None:
    match = re.search(pattern, text, flags)
    if not match:
        return None
    value = match.group(1).strip()
    return value or None


def find_doc_type(text: str) -> str:
    low = text.lower()
    for needle, title in DOC_TYPES:
        if needle in low:
            return title
    return "Документ"


def find_number(text: str) -> str | None:
    return _search(text, r"(?:счёт|счет|акт|упд)[^\n]{0,40}?№\s*([0-9A-Za-zА-Яа-я/\-]+)")


def find_date(text: str) -> dt.date | None:
    match = re.search(r"\bот\s+(\d{2})[.\-/](\d{2})[.\-/](\d{4})", text)
    if match:
        day, month, year = (int(g) for g in match.groups())
        try:
            return dt.date(year, month, day)
        except ValueError:
            return None

    match = re.search(r"\bот\s+(\d{1,2})\s+([а-яё]+)\s+(\d{4})", text, re.IGNORECASE)
    if match:
        day, month_name, year = match.groups()
        month = MONTHS.get(month_name.lower())
        if month:
            try:
                return dt.date(int(year), month, int(day))
            except ValueError:
                return None
    return None


def find_inn_kpp(text: str) -> tuple[str | None, str | None]:
    match = re.search(r"ИНН[\s:]*(\d{10}|\d{12})", text)
    inn = match.group(1) if match else None
    match_kpp = re.search(r"КПП[\s:]*([0-9A-Za-z]{9})", text)
    kpp = match_kpp.group(1).upper() if match_kpp else None
    return inn, kpp


def find_party(text: str, markers: tuple[str, ...]) -> str | None:
    for marker in markers:
        match = re.search(rf"{marker}\s*[:\-]?\s*(.+)", text, re.IGNORECASE)
        if not match:
            continue
        value = match.group(1).strip()
        # отрезаем ИНН/КПП, которые часто стоят в той же строке
        value = re.split(r"\s*(?:ИНН|КПП)\b", value, maxsplit=1, flags=re.IGNORECASE)[0].strip(" ,;")
        if value:
            return value
    return None


def _money_in(line: str) -> float | None:
    """Сумма из строки: берём последнее «денежное» число.

    В строке «НДС 20%: 8 000,00» первым числом идёт ставка, а не сумма,
    поэтому кандидаты фильтруются по разделителю тысяч или копейкам.
    """
    candidates = [match.group(0) for match in re.finditer(MONEY, line)]
    if not candidates:
        return None
    money_like = [c for c in candidates if re.search(r"[ \u00a0]\d{3}|[.,]\d{2}$", c)]
    return to_amount(money_like[-1] if money_like else candidates[-1])


def find_amounts(text: str) -> tuple[float | None, float | None, float | None]:
    """Вернуть (без НДС, НДС, итого), разбирая документ построчно.

    Построчный разбор надёжнее одного регулярного выражения: в строке
    «Сумма без НДС: 40 000,00» слово «НДС» тоже присутствует, и общий шаблон
    легко принимает сумму без НДС за сам НДС.
    """
    net = vat = total = None

    for line in text.splitlines():
        low = line.lower()
        if not re.search(r"\d", line):
            continue

        if re.search(r"без\s+ндс", low):
            net = _money_in(line) if net is None else net
            continue
        if re.search(r"\bндс\b|в\s+т\.ч\.?\s*ндс", low):
            vat = _money_in(line) if vat is None else vat
            continue
        if re.search(r"итого|всего\s+к\s+оплате|к\s+оплате|к\s+перечислению", low):
            total = _money_in(line) if total is None else total

    if total is None:
        total = net
    return net, vat, total


def parse_invoice(text: str, source: str = "", confidence: float | None = None) -> Invoice:
    inn, kpp = find_inn_kpp(text)
    net, vat, total = find_amounts(text)
    invoice = Invoice(
        source=source,
        doc_type=find_doc_type(text),
        number=find_number(text),
        date=find_date(text),
        seller=find_party(text, ("поставщик", "продавец")),
        seller_inn=inn,
        seller_kpp=kpp,
        buyer=find_party(text, ("покупатель", "заказчик", "плательщик")),
        amount_net=net,
        vat=vat,
        amount_total=total,
        confidence=confidence,
        raw_text=text,
    )
    invoice.validate()
    return invoice
