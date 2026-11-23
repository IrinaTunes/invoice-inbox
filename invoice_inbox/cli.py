"""CLI: python -m invoice_inbox <папка> -o реестр.xlsx"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from .export import to_json, to_xlsx
from .extract import ExtractionError, extract_text, iter_documents
from .parse import parse_invoice
from .validate import Invoice


def build_registry(root: Path, lang: str = "rus+eng") -> tuple[list[Invoice], list[str]]:
    """Разобрать все документы папки. Возвращает счета и список фатальных ошибок по файлам."""
    invoices: list[Invoice] = []
    broken: list[str] = []

    for path in iter_documents(root):
        rel = str(path.relative_to(root))
        try:
            text, confidence = extract_text(path, lang=lang)
        except ExtractionError as exc:
            broken.append(f"{rel}: {exc}")
            failed = Invoice(source=rel, doc_type="Не распознан", confidence=0.0)
            failed.validate()
            invoices.append(failed)
            continue
        invoices.append(parse_invoice(text, source=rel, confidence=confidence))

    return invoices, broken


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="invoice_inbox",
        description="Сканы счетов → реестр XLSX с проверкой ИНН и сумм",
    )
    parser.add_argument("root", type=Path, help="папка с PDF/сканами/текстом")
    parser.add_argument("-o", "--out", type=Path, default=Path("registry.xlsx"), help="файл реестра")
    parser.add_argument("--json", dest="json_out", type=Path, default=None, help="дополнительно сохранить JSON")
    parser.add_argument("--lang", default="rus+eng", help="языки tesseract (по умолчанию rus+eng)")
    args = parser.parse_args(argv)

    if not args.root.is_dir():
        print(f"нет такой папки: {args.root}", file=sys.stderr)
        return 2

    invoices, broken = build_registry(args.root, lang=args.lang)
    if not invoices:
        print("в папке нет поддерживаемых документов (.pdf/.png/.jpg/.txt)", file=sys.stderr)
        return 2

    args.out.parent.mkdir(parents=True, exist_ok=True)
    to_xlsx(invoices, args.out)
    if args.json_out:
        args.json_out.parent.mkdir(parents=True, exist_ok=True)
        to_json(invoices, args.json_out)

    review = [inv for inv in invoices if inv.needs_review]
    total = sum(inv.amount_total for inv in invoices if inv.amount_total is not None)

    print(f"Обработано документов: {len(invoices)}")
    print(f"Прошли проверки:        {len(invoices) - len(review)}")
    print(f"Требуют проверки:       {len(review)}")
    if invoices:
        print(f"Сумма итого:            {total:,.2f} ₽".replace(",", " "))
    print(f"Реестр: {args.out}")
    if args.json_out:
        print(f"JSON:   {args.json_out}")

    if review:
        print("\nТребуют внимания:")
        for inv in review:
            print(f"  • {inv.source}: {'; '.join(inv.issues)}")
    if broken:
        print("\nНе удалось извлечь текст:")
        for item in broken:
            print(f"  ✗ {item}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
