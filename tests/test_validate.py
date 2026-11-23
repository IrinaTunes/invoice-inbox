import datetime as dt

import pytest

from invoice_inbox.validate import Invoice, is_valid_inn, is_valid_kpp


@pytest.mark.parametrize(
    "inn",
    [
        "7707083893",    # ПАО Сбербанк, 10 цифр
        "500100732259",  # ИП, 12 цифр
    ],
)
def test_valid_inn(inn: str) -> None:
    assert is_valid_inn(inn) is True


@pytest.mark.parametrize(
    "inn",
    [
        "7707083894",   # последняя цифра изменена
        "500100732250",  # изменена контрольная цифра 12-значного
        "12345",        # неверная длина
        "",
        None,
    ],
)
def test_invalid_inn(inn: str | None) -> None:
    assert is_valid_inn(inn) is False


def test_inn_ignores_separators() -> None:
    assert is_valid_inn("7707 083 893") is True


@pytest.mark.parametrize("kpp", ["770101001", "500101001", "7701AB001"])
def test_valid_kpp(kpp: str) -> None:
    assert is_valid_kpp(kpp) is True


@pytest.mark.parametrize("kpp", ["77010100", "7701010011", "7701-01001", ""])
def test_invalid_kpp(kpp: str) -> None:
    assert is_valid_kpp(kpp) is False


def _invoice(**kwargs: object) -> Invoice:
    base = dict(
        source="invoice.pdf",
        doc_type="Счёт на оплату",
        number="142",
        date=dt.date.today() - dt.timedelta(days=3),
        seller="ООО «Ромашка»",
        seller_inn="7707083893",
        amount_net=40000.0,
        vat=8000.0,
        amount_total=48000.0,
        confidence=1.0,
    )
    base.update(kwargs)
    return Invoice(**base)  # type: ignore[arg-type]


def test_valid_invoice_has_no_issues() -> None:
    invoice = _invoice()
    assert invoice.validate() == []
    assert invoice.needs_review is False


def test_sum_mismatch_is_flagged() -> None:
    invoice = _invoice(amount_total=48200.0)
    issues = invoice.validate()
    assert any("итог" in issue for issue in issues)
    assert invoice.needs_review is True


def test_bad_inn_is_flagged() -> None:
    invoice = _invoice(seller_inn="7707083894")
    issues = invoice.validate()
    assert any("контрольную сумму" in issue for issue in issues)


def test_future_date_is_flagged() -> None:
    invoice = _invoice(date=dt.date.today() + dt.timedelta(days=10))
    assert any("будущем" in issue for issue in invoice.validate())


def test_low_ocr_confidence_is_flagged() -> None:
    invoice = _invoice(confidence=0.42)
    assert any("уверенность" in issue for issue in invoice.validate())


def test_missing_amount_is_flagged() -> None:
    invoice = _invoice(amount_net=None, vat=None, amount_total=None)
    assert any("итоговая сумма" in issue for issue in invoice.validate())
