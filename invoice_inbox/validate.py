"""Валидация реквизитов: ИНН по контрольной сумме, сверка сумм, даты."""

from __future__ import annotations

import datetime as dt
import re
from dataclasses import dataclass, field

INN10_WEIGHTS = (2, 4, 10, 3, 5, 9, 4, 6, 8)
INN12_WEIGHTS_11 = (7, 2, 4, 10, 3, 5, 9, 4, 6, 8)
INN12_WEIGHTS_12 = (3, 7, 2, 4, 10, 3, 5, 9, 4, 6, 8)


def _checksum(digits: str, weights: tuple[int, ...]) -> int:
    total = sum(int(d) * w for d, w in zip(digits, weights, strict=False))
    return total % 11 % 10


def is_valid_inn(inn: str | None) -> bool:
    """Проверка ИНН юрлица (10 цифр) и ИП/физлица (12 цифр) по контрольной сумме."""
    if not inn:
        return False
    value = re.sub(r"\D", "", inn)
    if len(value) == 10:
        return _checksum(value, INN10_WEIGHTS) == int(value[9])
    if len(value) == 12:
        ok11 = _checksum(value, INN12_WEIGHTS_11) == int(value[10])
        ok12 = _checksum(value, INN12_WEIGHTS_12) == int(value[11])
        return ok11 and ok12
    return False


def is_valid_kpp(kpp: str | None) -> bool:
    """КПП: 9 символов, первые 4 — цифры, 5–6 — латиница или цифры."""
    if not kpp:
        return False
    value = kpp.strip().upper()
    return bool(re.fullmatch(r"\d{4}[0-9A-Z]{2}\d{3}", value))


@dataclass
class Invoice:
    """Один документ из реестра."""

    source: str = ""
    doc_type: str = ""
    number: str | None = None
    date: dt.date | None = None
    seller: str | None = None
    seller_inn: str | None = None
    seller_kpp: str | None = None
    buyer: str | None = None
    amount_net: float | None = None       # без НДС
    vat: float | None = None
    amount_total: float | None = None
    currency: str = "RUB"
    confidence: float | None = None       # средняя уверенность OCR
    issues: list[str] = field(default_factory=list)
    raw_text: str = ""

    @property
    def needs_review(self) -> bool:
        return bool(self.issues)

    def validate(self, *, max_age_days: int = 3650) -> list[str]:
        """Вернуть список проблем. Пустой список = документ прошёл все проверки."""
        issues: list[str] = []

        if not self.number:
            issues.append("не найден номер документа")
        if self.date is None:
            issues.append("не найдена дата")
        elif self.date > dt.date.today():
            issues.append("дата в будущем")
        elif (dt.date.today() - self.date).days > max_age_days:
            issues.append("дата старше допустимого срока")

        if not self.seller:
            issues.append("не найден продавец")
        if not self.seller_inn:
            issues.append("не найден ИНН продавца")
        elif not is_valid_inn(self.seller_inn):
            issues.append(f"ИНН {self.seller_inn} не проходит контрольную сумму")
        if self.seller_kpp and not is_valid_kpp(self.seller_kpp):
            issues.append(f"КПП {self.seller_kpp} имеет неверный формат")

        if self.amount_total is None:
            issues.append("не найдена итоговая сумма")
        else:
            parts = [v for v in (self.amount_net, self.vat) if v is not None]
            if len(parts) == 2 and abs(sum(parts) - self.amount_total) > 0.01:
                issues.append(
                    f"итог {self.amount_total:.2f} ≠ без НДС {self.amount_net:.2f} + НДС {self.vat:.2f}"
                )

        if self.confidence is not None and self.confidence < 0.75:
            issues.append(f"низкая уверенность OCR ({self.confidence:.0%}) — проверить вручную")

        self.issues = issues
        return issues
