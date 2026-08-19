"""102 重複判定・状態管理の単体テスト。

対応仕様: docs/システムフォルダ/102-重複判定状態管理-仕様書.md
対応テスト記録: docs/システムフォルダ/102-重複判定状態管理-テスト.md
"""
import json
from datetime import datetime, timedelta, timezone
from difflib import SequenceMatcher
from unittest.mock import patch

import pytest

from src import state_store as ss
from src.news_collector import Candidate


def _candidate(title="記事タイトル", url="https://example.com/articles/x"):
    return Candidate(title=title, url=url, source="出典", published_at="2026-08-19T00:00:00Z")


@pytest.fixture(autouse=True)
def isolated_state_file(tmp_path, monkeypatch):
    path = tmp_path / "delivered.json"
    monkeypatch.setattr(ss, "STATE_FILE_PATH", path)
    return path


def _write_state(path, records):
    path.write_text(json.dumps({"delivered": records}, ensure_ascii=False), encoding="utf-8")


# --- 条件網羅テスト(境界値) -------------------------------------------------

def test_record_exactly_at_retention_boundary_is_kept(isolated_state_file):
    now = datetime(2026, 8, 19, tzinfo=timezone.utc)
    boundary = now - timedelta(days=ss.RETENTION_DAYS)
    _write_state(
        isolated_state_file,
        [{"url": "https://old", "title": "古い記事", "delivered_at": boundary.strftime("%Y-%m-%dT%H:%M:%SZ")}],
    )
    ss.record_delivered([], now=now)
    saved = json.loads(isolated_state_file.read_text(encoding="utf-8"))
    assert any(r["url"] == "https://old" for r in saved["delivered"])


def test_record_older_than_retention_is_removed(isolated_state_file):
    now = datetime(2026, 8, 19, tzinfo=timezone.utc)
    too_old = now - timedelta(days=ss.RETENTION_DAYS + 1)
    _write_state(
        isolated_state_file,
        [{"url": "https://old", "title": "古い記事", "delivered_at": too_old.strftime("%Y-%m-%dT%H:%M:%SZ")}],
    )
    ss.record_delivered([], now=now)
    saved = json.loads(isolated_state_file.read_text(encoding="utf-8"))
    assert saved["delivered"] == []


def test_dissimilar_title_below_threshold_is_not_excluded(isolated_state_file):
    _write_state(isolated_state_file, [{"url": "https://a", "title": "AAAAAAAAAA", "delivered_at": "2026-08-19T00:00:00Z"}])
    candidate = _candidate(title="ZZZZZZZZZZ", url="https://b")  # 完全に異なる文字列 → 類似度0(閾値0.6未満)
    result = ss.filter_undelivered([candidate])
    assert result == [candidate]


_TITLE_BASE = "AI駆動開発の記事タイトル例文サンプル"  # 19文字


def _title_with_ratio_around_threshold(suffix_len: int) -> str:
    """末尾suffix_len文字を'X'で置き換え、_TITLE_BASEとの類似度を変化させる。"""
    return _TITLE_BASE[: len(_TITLE_BASE) - suffix_len] + "X" * suffix_len


def test_similarity_just_above_threshold_is_excluded(isolated_state_file):
    just_above = _title_with_ratio_around_threshold(7)
    assert SequenceMatcher(None, _TITLE_BASE, just_above).ratio() >= ss.SIMILARITY_THRESHOLD
    _write_state(isolated_state_file, [{"url": "https://a", "title": _TITLE_BASE, "delivered_at": "2026-08-19T00:00:00Z"}])
    candidate = _candidate(title=just_above, url="https://b")
    assert ss.filter_undelivered([candidate]) == []


def test_similarity_just_below_threshold_is_not_excluded(isolated_state_file):
    just_below = _title_with_ratio_around_threshold(8)
    assert SequenceMatcher(None, _TITLE_BASE, just_below).ratio() < ss.SIMILARITY_THRESHOLD
    _write_state(isolated_state_file, [{"url": "https://a", "title": _TITLE_BASE, "delivered_at": "2026-08-19T00:00:00Z"}])
    candidate = _candidate(title=just_below, url="https://b")
    assert ss.filter_undelivered([candidate]) == [candidate]


# --- 機能要件テスト(仕様書7節のAC-1〜AC-6に対応) -----------------------------

def test_ac1_excludes_matching_url(isolated_state_file):
    _write_state(isolated_state_file, [{"url": "https://a", "title": "既配信タイトル", "delivered_at": "2026-08-19T00:00:00Z"}])
    candidate = _candidate(title="別のタイトル", url="https://a")
    assert ss.filter_undelivered([candidate]) == []


def test_ac2_excludes_similar_title(isolated_state_file):
    _write_state(
        isolated_state_file,
        [{"url": "https://a", "title": "AI駆動開発の最新動向まとめ2026", "delivered_at": "2026-08-19T00:00:00Z"}],
    )
    candidate = _candidate(title="AI駆動開発の最新動向まとめ2026年8月版", url="https://b")
    assert ss.filter_undelivered([candidate]) == []


def test_ac3_record_delivered_adds_entry(isolated_state_file):
    now = datetime(2026, 8, 19, tzinfo=timezone.utc)
    ss.record_delivered([{"url": "https://a", "title": "記事A"}], now=now)
    saved = json.loads(isolated_state_file.read_text(encoding="utf-8"))
    assert saved["delivered"] == [{"url": "https://a", "title": "記事A", "delivered_at": "2026-08-19T00:00:00Z"}]


def test_ac4_record_delivered_purges_old_entries_before_saving(isolated_state_file):
    now = datetime(2026, 8, 19, tzinfo=timezone.utc)
    too_old = now - timedelta(days=ss.RETENTION_DAYS + 10)
    _write_state(
        isolated_state_file,
        [{"url": "https://old", "title": "古い記事", "delivered_at": too_old.strftime("%Y-%m-%dT%H:%M:%SZ")}],
    )
    ss.record_delivered([{"url": "https://new", "title": "新しい記事"}], now=now)
    saved = json.loads(isolated_state_file.read_text(encoding="utf-8"))
    urls = {r["url"] for r in saved["delivered"]}
    assert urls == {"https://new"}


def test_ac5_missing_state_file_starts_empty(isolated_state_file):
    assert not isolated_state_file.exists()
    candidate = _candidate()
    assert ss.filter_undelivered([candidate]) == [candidate]
    ss.record_delivered([{"url": "https://a", "title": "A"}])
    assert isolated_state_file.exists()


def test_ac6_corrupt_json_raises_error(isolated_state_file):
    isolated_state_file.write_text("{not valid json", encoding="utf-8")
    with pytest.raises(ss.StateStoreError):
        ss.filter_undelivered([_candidate()])


def test_ac6_unexpected_structure_raises_error(isolated_state_file):
    isolated_state_file.write_text(json.dumps({"unexpected": []}), encoding="utf-8")
    with pytest.raises(ss.StateStoreError):
        ss.filter_undelivered([_candidate()])


def test_ac6_record_missing_required_field_raises_error(isolated_state_file):
    _write_state(isolated_state_file, [{"url": "https://a", "title": "タイトルのみでdelivered_atがない"}])
    with pytest.raises(ss.StateStoreError):
        ss.filter_undelivered([_candidate()])


def test_unparsable_delivered_at_raises_state_store_error(isolated_state_file):
    """record_delivered内のdatetime.fromisoformatがValueErrorを送出するケースをStateStoreErrorに包む。"""
    _write_state(
        isolated_state_file,
        [{"url": "https://a", "title": "A", "delivered_at": "not-a-valid-datetime"}],
    )
    with pytest.raises(ss.StateStoreError):
        ss.record_delivered([{"url": "https://b", "title": "B"}])


def test_atomic_write_os_error_raises_state_store_error(isolated_state_file):
    """_atomic_write内のOSErrorをStateStoreErrorに包む。"""
    with patch.object(ss.os, "replace", side_effect=OSError("disk full")):
        with pytest.raises(ss.StateStoreError):
            ss.record_delivered([{"url": "https://a", "title": "A"}])
