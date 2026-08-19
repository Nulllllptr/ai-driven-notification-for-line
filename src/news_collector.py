"""101 ニュース収集: パブリッシャー直RSS/AtomからAI駆動開発関連の候補記事を集める。

仕様: docs/システムフォルダ/101-ニュース収集-仕様書.md
"""
import calendar
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone

import feedparser
import requests

from src.common.logging_setup import get_logger

logger = get_logger("news_collector")

REQUEST_TIMEOUT_SECONDS = 10
LOOKBACK_DAYS = 183  # 約6ヶ月(ADR-0002)

FEEDS = [
    {"name": "Publickey", "url": "https://www.publickey1.jp/atom.xml"},
    {"name": "Qiita(生成AIタグ)", "url": "https://qiita.com/tags/生成AI/feed"},
    {"name": "Zenn(AIトピック)", "url": "https://zenn.dev/topics/ai/feed"},
    {"name": "TechCrunch(AIカテゴリ)", "url": "https://techcrunch.com/category/artificial-intelligence/feed/"},
    {"name": "Ars Technica(AIタグ)", "url": "https://arstechnica.com/tag/ai/feed/"},
]


class CollectionError(Exception):
    """全ての検索クエリの取得に失敗したときに送出する(仕様書 AC-5)。"""


@dataclass
class Candidate:
    title: str
    url: str
    source: str
    published_at: str


def _parse_published_at(feed_entry) -> datetime | None:
    parsed = feed_entry.get("published_parsed") or feed_entry.get("updated_parsed")
    if not parsed:
        return None
    return datetime.fromtimestamp(calendar.timegm(parsed), tz=timezone.utc)


def _fetch_one(feed_config: dict) -> list:
    response = requests.get(feed_config["url"], timeout=REQUEST_TIMEOUT_SECONDS)
    if response.status_code != 200:
        raise CollectionError(f"unexpected status {response.status_code} for feed={feed_config['name']!r}")
    feed = feedparser.parse(response.content)
    if feed.bozo and not feed.entries:
        # bozo=True は文字エンコーディング宣言の不整合等、軽微なXML逸脱でも立つ。
        # entriesが取れていれば実用上使えるため、entriesが空の場合のみ失敗扱いにする。
        raise CollectionError(f"malformed feed for feed={feed_config['name']!r}")
    return feed.entries


def collect_candidates(now: datetime | None = None) -> list[Candidate]:
    """設定済みのフィード一覧からAI駆動開発関連の候補記事を収集する。

    戻り値は published_at が新しい順とは限らない、url で重複排除済みの一覧。
    全フィードが失敗した場合は CollectionError を送出する(呼び出し元の105が最終catchする)。
    now は tz-aware datetime を渡すこと(未指定時はUTC現在時刻、naiveが渡された場合もUTCとして扱う)。
    """
    now = now or datetime.now(timezone.utc)
    if now.tzinfo is None:
        now = now.replace(tzinfo=timezone.utc)
    cutoff = now - timedelta(days=LOOKBACK_DAYS)

    results: dict[str, Candidate] = {}
    failure_count = 0

    for feed_config in FEEDS:
        try:
            entries = _fetch_one(feed_config)
        except (requests.RequestException, CollectionError) as exc:
            logger.warning("feed failed, skipping: feed=%s error=%s", feed_config["name"], exc)
            failure_count += 1
            continue

        for entry in entries:
            link = entry.get("link")
            if not link:
                continue
            published_at = _parse_published_at(entry)
            if published_at is None:
                logger.warning("unparsable pubDate, skipping entry: title=%s", entry.get("title"))
                continue
            if published_at < cutoff:
                continue
            if link in results:
                continue
            results[link] = Candidate(
                title=entry.get("title", ""),
                url=link,
                source=feed_config["name"],
                published_at=published_at.strftime("%Y-%m-%dT%H:%M:%SZ"),
            )

    if failure_count == len(FEEDS):
        raise CollectionError("all feeds failed")

    logger.info("collected %d candidates (%d/%d feeds failed)", len(results), failure_count, len(FEEDS))
    return list(results.values())
