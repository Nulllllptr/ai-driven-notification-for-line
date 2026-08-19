"""101 ニュース収集の単体テスト。

対応仕様: docs/システムフォルダ/101-ニュース収集-仕様書.md
対応テスト記録: docs/システムフォルダ/101-ニュース収集-テスト.md
"""
from datetime import datetime, timedelta, timezone
from unittest.mock import Mock, patch

import pytest
import requests

from src import news_collector as nc


def _entry(title="title", link="https://example.com/articles/x", published_at=None):
    published_at = published_at or datetime.now(timezone.utc)
    return {
        "title": title,
        "link": link,
        "published_parsed": published_at.timetuple(),
    }


def _feed(entries, bozo=False):
    feed = Mock()
    feed.bozo = bozo
    feed.entries = entries
    return feed


@pytest.fixture(autouse=True)
def single_feed(monkeypatch):
    """FEEDSを1件に固定し、呼び出し回数をテストごとに読みやすくする。"""
    monkeypatch.setattr(nc, "FEEDS", [{"name": "TestFeed", "url": "https://example.com/feed"}])


def _mock_response(status_code=200, content=b"<rss></rss>"):
    resp = Mock()
    resp.status_code = status_code
    resp.content = content
    return resp


# --- 条件網羅テスト(境界値) -------------------------------------------------

def test_article_within_lookback_window_is_included():
    now = datetime(2026, 8, 19, tzinfo=timezone.utc)
    published_at = now - timedelta(days=nc.LOOKBACK_DAYS)  # ちょうど境界
    entry = _entry(published_at=published_at)
    with patch.object(nc.requests, "get", return_value=_mock_response()), \
         patch.object(nc.feedparser, "parse", return_value=_feed([entry])):
        result = nc.collect_candidates(now=now)
    assert len(result) == 1


def test_article_older_than_lookback_window_is_excluded():
    now = datetime(2026, 8, 19, tzinfo=timezone.utc)
    published_at = now - timedelta(days=nc.LOOKBACK_DAYS + 1)
    entry = _entry(published_at=published_at)
    with patch.object(nc.requests, "get", return_value=_mock_response()), \
         patch.object(nc.feedparser, "parse", return_value=_feed([entry])):
        result = nc.collect_candidates(now=now)
    assert result == []


def test_entry_without_link_is_skipped():
    entry = _entry()
    del entry["link"]
    with patch.object(nc.requests, "get", return_value=_mock_response()), \
         patch.object(nc.feedparser, "parse", return_value=_feed([entry])):
        result = nc.collect_candidates()
    assert result == []


# --- 機能要件テスト(仕様書7節のAC-1〜AC-6に対応) -----------------------------

def test_ac1_collects_from_each_feed(monkeypatch):
    monkeypatch.setattr(
        nc,
        "FEEDS",
        [
            {"name": "FeedA", "url": "https://a.example.com/feed"},
            {"name": "FeedB", "url": "https://b.example.com/feed"},
        ],
    )
    entry_a = _entry(link="https://a.example.com/articles/1")
    entry_b = _entry(link="https://b.example.com/articles/1")
    with patch.object(nc.requests, "get", return_value=_mock_response()) as mock_get, \
         patch.object(nc.feedparser, "parse", side_effect=[_feed([entry_a]), _feed([entry_b])]):
        result = nc.collect_candidates()
    assert mock_get.call_count == 2
    assert {c.url for c in result} == {entry_a["link"], entry_b["link"]}
    assert {c.source for c in result} == {"FeedA", "FeedB"}


def test_ac2_filters_out_articles_older_than_six_months():
    now = datetime(2026, 8, 19, tzinfo=timezone.utc)
    old_entry = _entry(published_at=now - timedelta(days=200))
    with patch.object(nc.requests, "get", return_value=_mock_response()), \
         patch.object(nc.feedparser, "parse", return_value=_feed([old_entry])):
        result = nc.collect_candidates(now=now)
    assert result == []


def test_ac3_deduplicates_same_url_within_feed():
    entry1 = _entry(link="https://example.com/articles/same", title="A")
    entry2 = _entry(link="https://example.com/articles/same", title="A(重複)")
    with patch.object(nc.requests, "get", return_value=_mock_response()), \
         patch.object(nc.feedparser, "parse", return_value=_feed([entry1, entry2])):
        result = nc.collect_candidates()
    assert len(result) == 1


def test_ac3_deduplicates_same_url_across_different_feeds(monkeypatch):
    """同一記事が複数フィードでヒットした場合の統合(仕様書4節)を検証する。"""
    monkeypatch.setattr(
        nc,
        "FEEDS",
        [
            {"name": "FeedA", "url": "https://a.example.com/feed"},
            {"name": "FeedB", "url": "https://b.example.com/feed"},
        ],
    )
    shared_entry = _entry(link="https://shared.example.com/articles/x")
    with patch.object(nc.requests, "get", return_value=_mock_response()), \
         patch.object(
             nc.feedparser,
             "parse",
             side_effect=[_feed([shared_entry]), _feed([shared_entry])],
         ):
        result = nc.collect_candidates()
    assert len(result) == 1


def test_ac4_skips_failed_feed_and_continues(monkeypatch):
    monkeypatch.setattr(
        nc,
        "FEEDS",
        [
            {"name": "FailFeed", "url": "https://fail.example.com/feed"},
            {"name": "OkFeed", "url": "https://ok.example.com/feed"},
        ],
    )
    ok_entry = _entry(link="https://ok.example.com/articles/1")
    with patch.object(
        nc.requests, "get", side_effect=[requests.Timeout("timeout"), _mock_response()]
    ), patch.object(nc.feedparser, "parse", return_value=_feed([ok_entry])):
        result = nc.collect_candidates()
    assert [c.url for c in result] == [ok_entry["link"]]


def test_ac5_raises_when_all_feeds_fail():
    with patch.object(nc.requests, "get", side_effect=requests.Timeout("timeout")):
        with pytest.raises(nc.CollectionError):
            nc.collect_candidates()


def test_ac6_skips_entry_with_unparsable_pubdate():
    entry = _entry()
    entry["published_parsed"] = None
    with patch.object(nc.requests, "get", return_value=_mock_response()), \
         patch.object(nc.feedparser, "parse", return_value=_feed([entry])):
        result = nc.collect_candidates()
    assert result == []


def test_non_200_response_is_treated_as_failure_and_skipped(monkeypatch):
    monkeypatch.setattr(
        nc,
        "FEEDS",
        [
            {"name": "BadStatusFeed", "url": "https://bad.example.com/feed"},
            {"name": "OkFeed", "url": "https://ok.example.com/feed"},
        ],
    )
    ok_entry = _entry(link="https://ok.example.com/articles/1")
    with patch.object(
        nc.requests, "get", side_effect=[_mock_response(status_code=500), _mock_response()]
    ), patch.object(nc.feedparser, "parse", return_value=_feed([ok_entry])):
        result = nc.collect_candidates()
    assert [c.url for c in result] == [ok_entry["link"]]


def test_malformed_xml_bozo_flag_with_no_entries_is_treated_as_failure():
    with patch.object(nc.requests, "get", return_value=_mock_response()), \
         patch.object(nc.feedparser, "parse", return_value=_feed([], bozo=True)):
        with pytest.raises(nc.CollectionError):
            nc.collect_candidates()


def test_bozo_flag_with_entries_present_is_not_treated_as_failure():
    """bozo=Trueでもentriesが取れていれば使う(文字コード宣言不整合等の軽微な逸脱を許容)。"""
    entry = _entry()
    with patch.object(nc.requests, "get", return_value=_mock_response()), \
         patch.object(nc.feedparser, "parse", return_value=_feed([entry], bozo=True)):
        result = nc.collect_candidates()
    assert len(result) == 1


def test_ac4_one_feed_malformed_xml_others_continue(monkeypatch):
    monkeypatch.setattr(
        nc,
        "FEEDS",
        [
            {"name": "MalformedFeed", "url": "https://bad.example.com/feed"},
            {"name": "OkFeed", "url": "https://ok.example.com/feed"},
        ],
    )
    ok_entry = _entry(link="https://ok.example.com/articles/1")
    with patch.object(nc.requests, "get", return_value=_mock_response()), \
         patch.object(
             nc.feedparser,
             "parse",
             side_effect=[_feed([], bozo=True), _feed([ok_entry])],
         ):
        result = nc.collect_candidates()
    assert [c.url for c in result] == [ok_entry["link"]]


def test_naive_now_is_treated_as_utc():
    naive_now = datetime(2026, 8, 19)  # tzinfoなし
    published_at = datetime(2026, 8, 18, tzinfo=timezone.utc)
    entry = _entry(published_at=published_at)
    with patch.object(nc.requests, "get", return_value=_mock_response()), \
         patch.object(nc.feedparser, "parse", return_value=_feed([entry])):
        result = nc.collect_candidates(now=naive_now)
    assert len(result) == 1


def test_source_is_the_configured_feed_name(monkeypatch):
    monkeypatch.setattr(nc, "FEEDS", [{"name": "Zenn(AIトピック)", "url": "https://zenn.dev/topics/ai/feed"}])
    entry = _entry()
    with patch.object(nc.requests, "get", return_value=_mock_response()), \
         patch.object(nc.feedparser, "parse", return_value=_feed([entry])):
        result = nc.collect_candidates()
    assert result[0].source == "Zenn(AIトピック)"
