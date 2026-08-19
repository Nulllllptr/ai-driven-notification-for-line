"""104 LINE配信の単体テスト。

対応仕様: docs/システムフォルダ/104-LINE配信-仕様書.md
対応テスト記録: docs/システムフォルダ/104-LINE配信-テスト.md
"""
from datetime import datetime
from unittest.mock import Mock, patch

import pytest
import requests

from src import line_notifier as ln


def _article(title="タイトル", summary="要約", url="https://example.com/a", source="Zenn"):
    return {"title": title, "summary": summary, "url": url, "source": source}


def _mock_response(status_code=200, text="{}"):
    resp = Mock()
    resp.status_code = status_code
    resp.text = text
    return resp


@pytest.fixture(autouse=True)
def env_credentials(monkeypatch):
    monkeypatch.setenv("LINE_CHANNEL_ACCESS_TOKEN", "test-token")
    monkeypatch.setenv("LINE_USER_ID", "test-user-id")


@pytest.fixture(autouse=True)
def no_sleep(monkeypatch):
    monkeypatch.setattr(ln.time, "sleep", lambda _seconds: None)


# --- 条件網羅テスト ---------------------------------------------------------

def test_message_includes_all_articles_and_date():
    now = datetime(2026, 8, 19)
    text = ln._format_message([_article(title="A記事"), _article(title="B記事")], now=now)
    assert "2026-08-19" in text
    assert "A記事" in text
    assert "B記事" in text


def test_missing_channel_token_raises_error(monkeypatch):
    monkeypatch.delenv("LINE_CHANNEL_ACCESS_TOKEN", raising=False)
    with pytest.raises(ln.LineNotificationError):
        ln.send_articles([_article()])


def test_missing_user_id_raises_error(monkeypatch):
    monkeypatch.delenv("LINE_USER_ID", raising=False)
    with patch.object(ln.requests, "post") as mock_post:
        with pytest.raises(ln.LineNotificationError):
            ln.send_articles([_article()])
    mock_post.assert_not_called()


# --- 機能要件テスト(仕様書7節のAC-1〜AC-5に対応) -----------------------------

def test_ac1_sends_single_push_request_with_articles():
    with patch.object(ln.requests, "post", return_value=_mock_response()) as mock_post:
        ln.send_articles([_article(title="記事1"), _article(title="記事2")])
    mock_post.assert_called_once()
    call = mock_post.call_args
    assert call.args[0] == ln.PUSH_ENDPOINT
    assert call.kwargs["json"]["to"] == "test-user-id"
    assert call.kwargs["headers"]["Authorization"] == "Bearer test-token"
    messages = call.kwargs["json"]["messages"]
    assert len(messages) == 1
    assert messages[0]["type"] == "text"
    assert "記事1" in messages[0]["text"] and "記事2" in messages[0]["text"]


def test_ac2_empty_articles_skips_send():
    with patch.object(ln.requests, "post") as mock_post:
        ln.send_articles([])
    mock_post.assert_not_called()


def test_ac3_missing_credentials_raises_before_request(monkeypatch):
    monkeypatch.delenv("LINE_CHANNEL_ACCESS_TOKEN", raising=False)
    with patch.object(ln.requests, "post") as mock_post:
        with pytest.raises(ln.LineNotificationError):
            ln.send_articles([_article()])
    mock_post.assert_not_called()


def test_ac4_retries_once_on_500_then_succeeds():
    with patch.object(
        ln.requests, "post", side_effect=[_mock_response(status_code=500), _mock_response(status_code=200)]
    ) as mock_post:
        ln.send_articles([_article()])
    assert mock_post.call_count == 2


def test_ac4_retries_once_on_network_error_then_succeeds():
    with patch.object(
        ln.requests, "post", side_effect=[requests.Timeout("timeout"), _mock_response(status_code=200)]
    ) as mock_post:
        ln.send_articles([_article()])
    assert mock_post.call_count == 2


def test_ac5_raises_after_retry_exhausted():
    with patch.object(ln.requests, "post", return_value=_mock_response(status_code=500)) as mock_post:
        with pytest.raises(ln.LineNotificationError):
            ln.send_articles([_article()])
    assert mock_post.call_count == 2  # 初回 + 1回のリトライ


def test_mask_token_redacts_bearer_value():
    masked = ln._mask_token("request failed: Authorization: Bearer secret-token-123 rejected")
    assert "secret-token-123" not in masked
    assert "Bearer ***" in masked


def test_ac5_non_retryable_400_does_not_retry():
    with patch.object(ln.requests, "post", return_value=_mock_response(status_code=400, text="bad request")) as mock_post:
        with pytest.raises(ln.LineNotificationError):
            ln.send_articles([_article()])
    assert mock_post.call_count == 1
