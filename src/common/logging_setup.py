"""logging-rules.md に基づく構造化(JSON)ロギングの共通セットアップ。"""
import json
import logging
import re
import sys
from pathlib import Path

_CONFIG_PATH = Path(__file__).resolve().parents[2] / "logging-config.json"
_DEFAULT_LEVEL = "INFO"


def _load_config() -> dict:
    try:
        return json.loads(_CONFIG_PATH.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}


_CONFIG = _load_config()
_LEVEL = str(_CONFIG.get("default_level", _DEFAULT_LEVEL))
# logging-rules.md 1節: mask_fields に列挙されたフィールドは値そのものを出力しない。
# "field=value" / "field: value" のようにログメッセージ中に現れた値を伏せ字に置き換える。
_MASK_PATTERNS = [
    re.compile(rf"({re.escape(field)}\s*[:=]\s*)(\S+)", re.IGNORECASE)
    for field in _CONFIG.get("mask_fields", [])
]


def _mask(message: str) -> str:
    for pattern in _MASK_PATTERNS:
        message = pattern.sub(r"\1***", message)
    return message


class _JsonFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        payload = {
            "time": self.formatTime(record, "%Y-%m-%dT%H:%M:%S%z"),
            "level": record.levelname,
            "component": record.name,
            "message": _mask(record.getMessage()),
        }
        return json.dumps(payload, ensure_ascii=False)


def get_logger(component: str) -> logging.Logger:
    """コンポーネント名(例: "news_collector")を指定してロガーを取得する。"""
    logger = logging.getLogger(component)
    if not logger.handlers:
        handler = logging.StreamHandler(stream=sys.stdout)
        handler.setFormatter(_JsonFormatter())
        logger.addHandler(handler)
        logger.setLevel(_LEVEL)
        logger.propagate = False
    return logger
