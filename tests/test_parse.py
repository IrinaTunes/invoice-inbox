from invoice_inbox.parse import find_amounts, parse_invoice, to_amount

SAMPLE = """Счёт на оплату № 142 от 12.11.2026
Поставщик: ООО «Ромашка»  ИНН 7707083893  КПП 770101001
Покупатель: ООО «Вектор»  ИНН 500100732259
Сумма без НДС: 40 000,00
НДС 20%: 8 000,00
Итого к оплате: 48 000,00
"""


def test_to_amount_handles_spaces_and_comma() -> None:
    assert to_amount("48 000,00") == 48000.0
    assert to_amount("48\u00a0000,50") == 48000.5
    assert to_amount("48000.00") == 48000.0
    assert to_amount("нет") is None


def test_amounts_do_not_confuse_vat_with_net() -> None:
    # Слово «НДС» есть и в строке «Сумма без НДС» — частая ловушка
    net, vat, total = find_amounts(SAMPLE)
    assert (net, vat, total) == (40000.0, 8000.0, 48000.0)


def test_vat_rate_is_not_taken_as_amount() -> None:
    net, vat, total = find_amounts("НДС 20%: 1 200,00\nИтого: 7 200,00\nСумма без НДС: 6 000,00")
    assert net == 6000.0
    assert vat == 1200.0
    assert total == 7200.0


def test_parse_invoice_fields() -> None:
    invoice = parse_invoice(SAMPLE, source="invoice-142.pdf", confidence=1.0)

    assert invoice.doc_type == "Счёт на оплату"
    assert invoice.number == "142"
    assert invoice.date is not None
    assert invoice.date.isoformat() == "2026-11-12"
    assert invoice.seller == "ООО «Ромашка»"
    assert invoice.seller_inn == "7707083893"
    assert invoice.seller_kpp == "770101001"
    assert invoice.buyer == "ООО «Вектор»"
    assert invoice.amount_total == 48000.0
    assert invoice.validate() == []


def test_month_name_date_is_parsed() -> None:
    invoice = parse_invoice("Счёт-фактура № 88 от 03 ноября 2026\nИтого: 1 000,00")
    assert invoice.date is not None
    assert invoice.date.isoformat() == "2026-11-03"


def test_unparsed_fields_are_reported_not_invented() -> None:
    invoice = parse_invoice("Какой-то текст без реквизитов")
    assert invoice.number is None
    assert invoice.seller_inn is None
    assert invoice.needs_review is True
    assert any("номер" in issue for issue in invoice.issues)
