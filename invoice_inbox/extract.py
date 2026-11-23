"""Извлечение текста: текстовый слой PDF → pdftotext, иначе растр → tesseract."""

from __future__ import annotations

import csv
import shutil
import subprocess
import tempfile
from pathlib import Path

SUPPORTED_PDF = {".pdf"}
SUPPORTED_IMAGES = {".png", ".jpg", ".jpeg", ".tif", ".tiff"}
SUPPORTED_TEXT = {".txt"}


class ExtractionError(RuntimeError):
    """Текст извлечь не удалось — документ должен попасть в отчёт как проблемный."""


def _require(tool: str) -> None:
    if shutil.which(tool) is None:
        raise ExtractionError(
            f"не найден {tool}. macOS: brew install poppler tesseract tesseract-lang"
        )


def _run(cmd: list[str], timeout: int = 180) -> str:
    result = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)
    if result.returncode != 0:
        raise ExtractionError(f"{cmd[0]} завершился с кодом {result.returncode}: {result.stderr.strip()[:200]}")
    return result.stdout


def ocr_image(path: Path, lang: str = "rus+eng") -> tuple[str, float]:
    """OCR картинки. Возвращает текст и среднюю уверенность по словам."""
    _require("tesseract")
    with tempfile.TemporaryDirectory() as tmp:
        tsv = Path(tmp) / "out"
        _run(["tesseract", str(path), str(tsv), "-l", lang, "--psm", "6", "tsv"])

        lines: list[str] = []
        confidences: list[float] = []
        with open(f"{tsv}.tsv", encoding="utf-8", errors="ignore") as fh:
            reader = csv.DictReader(fh, delimiter="\t")
            current_line = None
            for row in reader:
                word = (row.get("text") or "").strip()
                if not word:
                    continue
                line_id = (row.get("block_num"), row.get("par_num"), row.get("line_num"))
                if line_id != current_line:
                    lines.append("")
                    current_line = line_id
                lines[-1] = f"{lines[-1]} {word}".strip()
                try:
                    conf = float(row.get("conf") or -1)
                except ValueError:
                    conf = -1
                if conf >= 0:
                    confidences.append(conf)

    text = "\n".join(line for line in lines if line).strip()
    confidence = round(sum(confidences) / len(confidences) / 100, 3) if confidences else None
    return text, confidence  # type: ignore[return-value]


def pdf_text_layer(path: Path) -> str:
    _require("pdftotext")
    return _run(["pdftotext", "-layout", str(path), "-"]).strip()


def pdf_to_image(path: Path, dpi: int = 300) -> Path:
    _require("pdftoppm")
    tmpdir = Path(tempfile.mkdtemp(prefix="invoice-inbox-"))
    _run(["pdftoppm", "-r", str(dpi), "-png", "-f", "1", "-l", "1", str(path), str(tmpdir / "page")])
    pages = sorted(tmpdir.glob("page*.png"))
    if not pages:
        raise ExtractionError(f"не удалось отрендерить PDF в изображение: {path.name}")
    return pages[0]


def extract_text(path: Path, lang: str = "rus+eng") -> tuple[str, float | None]:
    """Вернуть (текст, уверенность). Для PDF с текстовым слоем уверенность = 1.0."""
    suffix = path.suffix.lower()

    if suffix in SUPPORTED_TEXT:
        return path.read_text(encoding="utf-8", errors="ignore"), 1.0

    if suffix in SUPPORTED_IMAGES:
        text, conf = ocr_image(path, lang)
        if not text:
            raise ExtractionError(f"OCR не нашёл текста в {path.name}")
        return text, conf

    if suffix in SUPPORTED_PDF:
        try:
            text = pdf_text_layer(path)
        except ExtractionError:
            text = ""
        if text:
            return text, 1.0
        image = pdf_to_image(path)
        text, conf = ocr_image(image, lang)
        if not text:
            raise ExtractionError(f"пустой текст после OCR: {path.name}")
        return text, conf

    raise ExtractionError(f"неподдерживаемый формат: {suffix}")


def iter_documents(root: Path) -> list[Path]:
    allowed = SUPPORTED_PDF | SUPPORTED_IMAGES | SUPPORTED_TEXT
    return sorted(p for p in root.rglob("*") if p.is_file() and p.suffix.lower() in allowed)
