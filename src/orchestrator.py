"""105 オーケストレーター: 101→102→103→104を順に呼び出すエントリポイント。

仕様: docs/システムフォルダ/105-オーケストレーター-仕様書.md
GitHub Actions workflowから `python -m src.orchestrator` として起動される。
"""
import sys

from src.article_summarizer import SummarizationError, generate_articles
from src.common.logging_setup import get_logger
from src.line_notifier import LineNotificationError, send_articles
from src.news_collector import CollectionError, collect_candidates
from src.state_store import StateStoreError, filter_undelivered, record_delivered

logger = get_logger("orchestrator")


def run() -> int:
    """パイプライン全体を実行する。成功時0、失敗時1を返す(仕様書 AC-1〜AC-5)。"""
    try:
        candidates = collect_candidates()
        undelivered = filter_undelivered(candidates)
        articles = generate_articles(undelivered)
    except (CollectionError, StateStoreError, SummarizationError) as exc:
        logger.error("pipeline failed before delivery: %s", exc)
        return 1

    if not articles:
        logger.info("no articles to deliver today")
        return 0

    try:
        send_articles(articles)
    except LineNotificationError as exc:
        logger.error("LINE delivery failed: %s", exc)
        return 1

    try:
        record_delivered([{"url": article["url"], "title": article["title"]} for article in articles])
    except StateStoreError as exc:
        logger.error("delivery succeeded but recording state failed: %s", exc)
        return 1

    logger.info("delivered %d articles", len(articles))
    return 0


if __name__ == "__main__":
    sys.exit(run())
