"""Генерация демонстрационных документов в samples/.

Запуск: python -m scripts.make_samples
Создаёт два PDF с текстовым слоем и один «скан» (PNG) без текстового слоя,
чтобы пример показывал оба пути: pdftotext и OCR.
"""

from __future__ import annotations

from pathlib import Path

from PIL import Image, ImageDraw, ImageFont
from reportlab.lib.pagesizes import A4
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.pdfgen import canvas

from invoice_inbox.validate import INN10_WEIGHTS

SAMPLES = Path(__file__).resolve().parent.parent / "samples"
FONT_PATH = "/System/Library/Fonts/Supplemental/Arial Unicode.ttf"
FALLBACK_FONT = "/System/Library/Fonts/Supplemental/Arial.ttf"


def make_inn(base9: str) -> str:
    """Достроить контрольную цифру ИНН юрлица."""
    total = sum(int(d) * w for d, w in zip(base9, INN10_WEIGHTS, strict=False))
    return base9 + str(total % 11 % 10)


def _font() -> str:
    return FONT_PATH if Path(FONT_PATH).exists() else FALLBACK_FONT


def draw_invoice(path: Path, lines: list[tuple[str, int]]) -> None:
    pdfmetrics.registerFont(TTFont("RU", _font()))
    c = canvas.Canvas(str(path), pagesize=A4)
    y = 800
    for text, size in lines:
        c.setFont("RU", size)
        c.drawString(60, y, text)
        y -= size + 14
    c.save()


def main() -> None:
    SAMPLES.mkdir(parents=True, exist_ok=True)
    inn_a = make_inn("770123456")
    inn_b = make_inn("500987654")

    draw_invoice(
        SAMPLES / "invoice-142.pdf",
        [
            ("Счёт на оплату № 142 от 12.11.2026", 18),
            ("Поставщик: ООО «Ромашка»  ИНН " + inn_a + "  КПП 770101001", 12),
            ("Покупатель: ООО «Вектор»  ИНН " + inn_b, 12),
            ("Сумма без НДС: 40 000,00", 12),
            ("НДС 20%: 8 000,00", 12),
            ("Итого к оплате: 48 000,00", 14),
        ],
    )

    draw_invoice(
        SAMPLES / "invoice-88.pdf",
        [
            ("Счёт-фактура № 88 от 03 ноября 2026", 18),
            ("Продавец: ИП Соколов Дмитрий  ИНН " + make_inn("770987654"), 12),
            ("Покупатель: ООО «Тембр»", 12),
            ("Стоимость без НДС: 12 000,00", 12),
            ("НДС 20%: 2 400,00", 12),
            ("Всего к оплате: 14 400,00", 14),
        ],
    )

    # «Скан»: картинка без текстового слоя, с намеренно битым ИНН
    img = Image.new("RGB", (1400, 700), "white")
    draw = ImageDraw.Draw(img)
    font = ImageFont.truetype(_font(), 34)
    font_big = ImageFont.truetype(_font(), 42)
    rows = [
        ("Счёт на оплату № 503 от 20.11.2026", font_big, 40),
        ("Поставщик: ООО «Камертон-Сервис»  ИНН 7707083894", font, 160),
        ("Покупатель: ООО «Октава»", font, 230),
        ("Сумма без НДС: 5 000,00", font, 300),
        ("НДС 20%: 1 000,00", font, 370),
        ("Итого к оплате: 6 200,00", font, 440),
    ]
    for text, fnt, y in rows:
        draw.text((60, y), text, fill="black", font=fnt)
    img.save(SAMPLES / "scan-503.png")

    print(f"Готово: {SAMPLES}")
    for item in sorted(SAMPLES.iterdir()):
        print(f"  {item.name} ({item.stat().st_size} B)")


if __name__ == "__main__":
    main()
