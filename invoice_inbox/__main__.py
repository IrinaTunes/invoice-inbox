"""Точка входа: python -m invoice_inbox <папка> -o реестр.xlsx"""

from .cli import main

if __name__ == "__main__":
    raise SystemExit(main())
