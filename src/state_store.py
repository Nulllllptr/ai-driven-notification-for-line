"""102 重複判定・状態管理: 配信済み記事の記録と、候補記事からの重複除外。

仕様: docs/システムフォルダ/102-重複判定状態管理-仕様書.md
"""
import json
import os
import tempfile
from datetime import datetime, timedelta, timezone
from difflib import SequenceMatcher
from pathlib import Path

from src.common.logging_setup import get_logger
from src.news_collector import Candidate

logger = get_logger("state_store")

STATE_FILE_PATH = Path(__file__).resolve().parents[1] / "data" / "delivered.json"
SIMILARITY_THRESHOLD = 0.6
RETENTION_DAYS = 183  # 約6ヶ月


class StateStoreError(Exception):
    """状態ファイルが壊れている・想定外の構造の場合に送出する(仕様書 AC-6)。"""


def _load_state() -> list[dict]:
    if not STATE_FILE_PATH.exists():
        return []
    try:
        data = json.loads(STATE_FILE_PATH.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise StateStoreError(f"corrupt state file: {STATE_FILE_PATH}") from exc
    if not isinstance(data, dict) or not isinstance(data.get("delivered"), list):
        raise StateStoreError(f"unexpected state file structure: {STATE_FILE_PATH}")
    for record in data["delivered"]:
        if not isinstance(record, dict) or not all(
            isinstance(record.get(key), str) for key in ("url", "title", "delivered_at")
        ):
            raise StateStoreError(f"unexpected delivered record structure: {record!r}")
    return data["delivered"]


def _is_similar_title(title: str, delivered_titles: list[str]) -> bool:
    return any(
        SequenceMatcher(None, title, other).ratio() >= SIMILARITY_THRESHOLD
        for other in delivered_titles
    )


def filter_undelivered(candidates: list[Candidate]) -> list[Candidate]:
    """101の候補から、状態ファイル記録済み(url一致・タイトル類似)を除外する。"""
    delivered = _load_state()
    delivered_urls = {record["url"] for record in delivered}
    delivered_titles = [record["title"] for record in delivered]

    result = [
        candidate
        for candidate in candidates
        if candidate.url not in delivered_urls
        and not _is_similar_title(candidate.title, delivered_titles)
    ]

    logger.info("filtered %d/%d candidates as undelivered", len(result), len(candidates))
    return result


def record_delivered(articles: list[dict], now: datetime | None = None) -> None:
    """配信確定した記事(url・title)を状態ファイルへ追記し、6ヶ月より古い記録を取り除く。"""
    now = now or datetime.now(timezone.utc)
    cutoff = now - timedelta(days=RETENTION_DAYS)

    delivered = _load_state()
    try:
        kept = [
            record
            for record in delivered
            if datetime.fromisoformat(record["delivered_at"].replace("Z", "+00:00")) >= cutoff
        ]
    except ValueError as exc:
        raise StateStoreError(f"unparsable delivered_at in state file: {exc}") from exc

    for article in articles:
        kept.append(
            {
                "url": article["url"],
                "title": article["title"],
                "delivered_at": now.strftime("%Y-%m-%dT%H:%M:%SZ"),
            }
        )

    STATE_FILE_PATH.parent.mkdir(parents=True, exist_ok=True)
    try:
        _atomic_write(STATE_FILE_PATH, json.dumps({"delivered": kept}, ensure_ascii=False, indent=2))
    except OSError as exc:
        raise StateStoreError(f"failed to write state file: {exc}") from exc
    logger.info("recorded %d delivered articles, %d total retained", len(articles), len(kept))


def _atomic_write(path: Path, content: str) -> None:
    """書き込み中断時に不完全なJSONが残らないよう、一時ファイル経由で置き換える。"""
    fd, tmp_name = tempfile.mkstemp(dir=path.parent, prefix=f".{path.name}.", suffix=".tmp")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as tmp_file:
            tmp_file.write(content)
        os.replace(tmp_name, path)
    except BaseException:
        os.unlink(tmp_name)
        raise
