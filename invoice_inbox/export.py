"""Экспорт реестра в XLSX и JSON."""

from __future__ import annotations

import json
from pathlib import Path

from openpyxl import Workbook
from openpyxl.styles import Alignment, Font, PatternFill
from openpyxl.utils import get_column_letter

from .validate import Invoice

COLUMNS = [
    ("Файл", "source", 34),
    ("Тип", "doc_type", 20),
    ("Номер", "number", 14),
    ("Дата", "date", 12),
    ("Поставщик", "seller", 34),
    ("ИНН", "seller_inn", 14),
    ("КПП", "seller_kpp", 12),
    ("Покупатель", "buyer", 30),
    ("Без НДС, ₽", "amount_net", 14),
    ("НДС, ₽", "vat", 12),
    ("Итого, ₽", "amount_total", 14),
    ("Уверенность OCR", "confidence", 17),
    ("Статус", "status", 18),
    ("Замечания", "issues_text", 60),
]

HEADER_FILL = PatternFill("solid", fgColor="1F2937")
HEADER_FONT = Font(color="FFFFFF", bold=True)
REVIEW_FILL = PatternFill("solid", fgColor="FEF3C7")
MONEY_FORMAT = "# ##0.00 ₽"


def _row(invoice: Invoice) -> dict[str, object]:
    return {
        "source": invoice.source,
        "doc_type": invoice.doc_type,
        "number": invoice.number,
        "date": invoice.date.strftime("%d.%m.%Y") if invoice.date else None,
        "seller": invoice.seller,
        "seller_inn": invoice.seller_inn,
        "seller_kpp": invoice.seller_kpp,
        "buyer": invoice.buyer,
        "amount_net": invoice.amount_net,
        "vat": invoice.vat,
        "amount_total": invoice.amount_total,
        "confidence": invoice.confidence,
        "status": "проверить" if invoice.needs_review else "ок",
        "issues_text": "; ".join(invoice.issues),
    }


def to_json(invoices: list[Invoice], path: Path) -> Path:
    payload = [dict(_row(inv), raw_text=None, issues=inv.issues) for inv in invoices]
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2, default=str), encoding="utf-8")
    return path


def to_xlsx(invoices: list[Invoice], path: Path) -> Path:
    wb = Workbook()
    ws = wb.active
    ws.title = "Реестр"

    for col, (title, _key, width) in enumerate(COLUMNS, start=1):
        cell = ws.cell(row=1, column=col, value=title)
        cell.fill = HEADER_FILL
        cell.font = HEADER_FONT
        cell.alignment = Alignment(horizontal="center", vertical="center", wrap_text=True)
        ws.column_dimensions[get_column_letter(col)].width = width

    for row_idx, invoice in enumerate(invoices, start=2):
        data = _row(invoice)
        for col, (_title, key, _width) in enumerate(COLUMNS, start=1):
            value = data[key]
            cell = ws.cell(row=row_idx, column=col, value=value)
            if key in {"amount_net", "vat", "amount_total"} and value is not None:
                cell.number_format = MONEY_FORMAT
            if key == "confidence" and value is not None:
                cell.number_format = "0%"
            if invoice.needs_review:
                cell.fill = REVIEW_FILL

    ws.freeze_panes = "A2"
    ws.auto_filter.ref = f"A1:{get_column_letter(len(COLUMNS))}{len(invoices) + 1}"

    summary = wb.create_sheet("Сводка")
    total_sum = sum(inv.amount_total for inv in invoices if inv.amount_total is not None)
    review_count = sum(1 for inv in invoices if inv.needs_review)
    rows = [
        ("Документов обработано", len(invoices)),
        ("Прошли все проверки", len(invoices) - review_count),
        ("Требуют проверки человеком", review_count),
        ("Сумма итого, ₽", round(total_sum, 2)),
    ]
    for idx, (label, value) in enumerate(rows, start=1):
        summary.cell(row=idx, column=1, value=label).font = Font(bold=True)
        cell = summary.cell(row=idx, column=2, value=value)
        if label.startswith("Сумма"):
            cell.number_format = MONEY_FORMAT
    summary.column_dimensions["A"].width = 34
    summary.column_dimensions["B"].width = 18

    if review_count:
        problems = wb.create_sheet("Проблемы")
        problems.append(["Файл", "Замечание"])
        for invoice in invoices:
            for issue in invoice.issues:
                problems.append([invoice.source, issue])
        for col, width in (("A", 34), ("B", 70)):
            problems.column_dimensions[col].width = width
        for cell in problems[1]:
            cell.font = HEADER_FONT
            cell.fill = HEADER_FILL

    wb.save(path)
    return path
