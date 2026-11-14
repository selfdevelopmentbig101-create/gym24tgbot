"""Logging: readable lines to the console and a rotating file in logs/."""
import logging
from logging.handlers import RotatingFileHandler
from pathlib import Path


def setup_logging(level: str = "INFO") -> None:
    Path("logs").mkdir(exist_ok=True)
    fmt = logging.Formatter("%(asctime)s | %(levelname)-7s | %(name)s | %(message)s")

    console = logging.StreamHandler()
    console.setFormatter(fmt)

    # 5 files x 2 MB, so logs never fill the disk.
    file_handler = RotatingFileHandler(
        "logs/bot.log", maxBytes=2_000_000, backupCount=5, encoding="utf-8"
    )
    file_handler.setFormatter(fmt)

    root = logging.getLogger()
    root.setLevel(level)
    root.handlers = [console, file_handler]

    # aiogram's per-update logs are noisy at INFO.
    logging.getLogger("aiogram.event").setLevel(logging.WARNING)
