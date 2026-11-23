"""Сквозной тест на реальных файлах из samples/ (нужны pdftotext и tesseract)."""

import shutil
from pathlib import Path

import pytest

from invoice_inbox.cli import build_registry
from invoice_inbox.extract import extract_text

SAMPLES = Path(__file__).resolve().parent.parent / "samples"

pytestmark = pytest.mark.skipif(
    not SAMPLES.is_dir() or shutil.which("tesseract") is None or shutil.which("pdftotext") is None,
    reason="нужны samples/ и CLI-утилиты poppler/tesseract",
)


def test_registry_reads_all_sample_documents() -> None:
    invoices, broken = build_registry(SAMPLES)
    assert broken == []
    assert len(invoices) == 3

    by_source = {inv.source: inv for inv in invoices}
    assert set(by_source) == {"invoice-142.pdf", "invoice-88.pdf", "scan-503.png"}

    clean = by_source["invoice-142.pdf"]
    assert clean.amount_total == 48000.0
    assert clean.needs_review is False

    scanned = by_source["scan-503.png"]
    # Битый ИНН и расхождение итога в демо-скане должны быть пойманы
    assert scanned.seller_inn == "7707083894"
    assert scanned.needs_review is True
    assert any("контрольную сумму" in issue for issue in scanned.issues)
    assert scanned.confidence is not None and scanned.confidence > 0.5


def test_pdf_text_layer_is_used_before_ocr() -> None:
    text, confidence = extract_text(SAMPLES / "invoice-142.pdf")
    assert "Счёт на оплату" in text
    assert confidence == 1.0


def test_png_goes_through_ocr() -> None:
    text, confidence = extract_text(SAMPLES / "scan-503.png")
    assert "503" in text
    assert confidence is not None and confidence < 1.0
