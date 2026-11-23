import datetime as dt
from pathlib import Path

from openpyxl import load_workbook

from invoice_inbox.export import to_json, to_xlsx
from invoice_inbox.validate import Invoice


def _invoices() -> list[Invoice]:
    ok = Invoice(
        source="invoice-142.pdf",
        doc_type="Счёт на оплату",
        number="142",
        date=dt.date(2026, 11, 12),
        seller="ООО «Ромашка»",
        seller_inn="7707083893",
        amount_net=40000.0,
        vat=8000.0,
        amount_total=48000.0,
        confidence=1.0,
    )
    ok.validate()

    bad = Invoice(
        source="scan-503.png",
        doc_type="Счёт на оплату",
        number="503",
        date=dt.date(2026, 11, 20),
        seller="ООО «Камертон-Сервис»",
        seller_inn="7707083894",
        amount_net=5000.0,
        vat=1000.0,
        amount_total=6200.0,
        confidence=0.62,
    )
    bad.validate()
    return [ok, bad]


def test_xlsx_has_rows_sheets_and_flags(tmp_path: Path) -> None:
    path = tmp_path / "registry.xlsx"
    to_xlsx(_invoices(), path)
    assert path.exists()

    wb = load_workbook(path)
    assert wb.sheetnames[:1] == ["Реестр"]
    assert "Сводка" in wb.sheetnames
    assert "Проблемы" in wb.sheetnames

    sheet = wb["Реестр"]
    assert sheet.max_row == 3  # заголовок + 2 документа
    assert sheet["A2"].value == "invoice-142.pdf"
    assert sheet["C2"].value == "142"
    assert sheet["K2"].value == 48000.0
    assert sheet["M2"].value == "ок"
    assert sheet["M3"].value == "проверить"
    assert "контрольную сумму" in sheet["N3"].value

    summary_sheet = wb["Сводка"]
    summary = {row[0].value: row[1].value for row in summary_sheet.iter_rows(min_row=1, max_row=4, max_col=2)}
    assert summary["Документов обработано"] == 2
    assert summary["Требуют проверки человеком"] == 1


def test_json_is_valid_and_keeps_issues(tmp_path: Path) -> None:
    import json

    path = tmp_path / "registry.json"
    to_json(_invoices(), path)
    data = json.loads(path.read_text(encoding="utf-8"))
    assert len(data) == 2
    assert data[1]["status"] == "проверить"
    assert data[1]["issues"]
