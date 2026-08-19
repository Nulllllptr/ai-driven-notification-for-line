"""105 オーケストレーターの単体テスト。

対応仕様: docs/システムフォルダ/105-オーケストレーター-仕様書.md
対応テスト記録: docs/システムフォルダ/105-オーケストレーター-テスト.md
"""
from unittest.mock import Mock, patch

from src import orchestrator as orch
from src.article_summarizer import SummarizationError
from src.line_notifier import LineNotificationError
from src.news_collector import CollectionError
from src.state_store import StateStoreError

_ARTICLE = {"title": "T", "summary": "S", "url": "https://example.com/a", "source": "Zenn"}


def _patched(**overrides):
    defaults = dict(
        collect_candidates=lambda: ["candidate"],
        filter_undelivered=lambda candidates: candidates,
        generate_articles=lambda undelivered: [_ARTICLE, _ARTICLE],
        send_articles=lambda articles: None,
        record_delivered=lambda articles: None,
    )
    defaults.update(overrides)
    return [patch.object(orch, name, Mock(side_effect=fn)) for name, fn in defaults.items()]


# --- 条件網羅テスト(境界値) -------------------------------------------------

def test_single_article_is_still_delivered():
    """「3件未満でも送信する」方針(改訂履歴参照)を確認する境界ケース。"""
    patches = _patched(generate_articles=lambda undelivered: [_ARTICLE])
    with patches[0], patches[1], patches[2], patches[3] as mock_send, patches[4] as mock_record:
        result = orch.run()
    assert result == 0
    mock_send.assert_called_once_with([_ARTICLE])
    mock_record.assert_called_once()


# --- 機能要件テスト(仕様書7節のAC-1〜AC-5に対応) -----------------------------

def test_ac1_full_pipeline_success_returns_zero():
    patches = _patched()
    with patches[0], patches[1], patches[2], patches[3] as mock_send, patches[4] as mock_record:
        result = orch.run()
    assert result == 0
    mock_send.assert_called_once_with([_ARTICLE, _ARTICLE])
    mock_record.assert_called_once_with(
        [{"url": _ARTICLE["url"], "title": _ARTICLE["title"]}, {"url": _ARTICLE["url"], "title": _ARTICLE["title"]}]
    )


def test_ac2_zero_articles_skips_send_and_record():
    patches = _patched(generate_articles=lambda undelivered: [])
    with patches[0], patches[1], patches[2], patches[3] as mock_send, patches[4] as mock_record:
        result = orch.run()
    assert result == 0
    mock_send.assert_not_called()
    mock_record.assert_not_called()


def test_ac3_record_delivered_called_with_url_and_title_only():
    patches = _patched(generate_articles=lambda undelivered: [_ARTICLE])
    with patches[0], patches[1], patches[2], patches[3], patches[4] as mock_record:
        orch.run()
    mock_record.assert_called_once_with([{"url": _ARTICLE["url"], "title": _ARTICLE["title"]}])


def test_ac4_collection_error_stops_pipeline_early():
    def raise_collection_error():
        raise CollectionError("boom")

    patches = _patched(collect_candidates=raise_collection_error)
    with patches[0], patches[1] as mock_filter, patches[2] as mock_generate, patches[3] as mock_send, patches[4] as mock_record:
        result = orch.run()
    assert result == 1
    mock_filter.assert_not_called()
    mock_generate.assert_not_called()
    mock_send.assert_not_called()
    mock_record.assert_not_called()


def test_ac4_state_store_error_during_filter_stops_pipeline():
    def raise_state_error(candidates):
        raise StateStoreError("boom")

    patches = _patched(filter_undelivered=raise_state_error)
    with patches[0], patches[1], patches[2] as mock_generate, patches[3] as mock_send, patches[4]:
        result = orch.run()
    assert result == 1
    mock_generate.assert_not_called()
    mock_send.assert_not_called()


def test_ac4_summarization_error_stops_pipeline():
    def raise_summarization_error(undelivered):
        raise SummarizationError("boom")

    patches = _patched(generate_articles=raise_summarization_error)
    with patches[0], patches[1], patches[2], patches[3] as mock_send, patches[4]:
        result = orch.run()
    assert result == 1
    mock_send.assert_not_called()


def test_ac4_line_notification_error_skips_record():
    def raise_line_error(articles):
        raise LineNotificationError("boom")

    patches = _patched(send_articles=raise_line_error)
    with patches[0], patches[1], patches[2], patches[3], patches[4] as mock_record:
        result = orch.run()
    assert result == 1
    mock_record.assert_not_called()


def test_ac5_record_delivered_failure_returns_one():
    def raise_state_error(articles):
        raise StateStoreError("boom")

    patches = _patched(record_delivered=raise_state_error)
    with patches[0], patches[1], patches[2], patches[3] as mock_send, patches[4]:
        result = orch.run()
    assert result == 1
    mock_send.assert_called_once()
