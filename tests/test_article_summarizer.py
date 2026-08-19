"""103 記事要約・生成の単体テスト。

対応仕様: docs/システムフォルダ/103-記事要約生成-仕様書.md
対応テスト記録: docs/システムフォルダ/103-記事要約生成-テスト.md
"""
from types import SimpleNamespace
from unittest.mock import Mock, patch

import anthropic
import httpx
import pytest

from src import article_summarizer as az
from src.news_collector import Candidate


def _candidate(title="タイトル", url="https://example.com/a", source="出典"):
    return Candidate(title=title, url=url, source=source, published_at="2026-08-19T00:00:00Z")


def _mock_page_response(
    status_code=200,
    text="<html><body>本文</body></html>",
    url="https://example.com/a",
    encoding="utf-8",
    apparent_encoding="utf-8",
):
    resp = Mock()
    resp.status_code = status_code
    resp.text = text
    resp.url = url
    resp.encoding = encoding
    resp.apparent_encoding = apparent_encoding
    return resp


def _tool_use_response(articles):
    block = SimpleNamespace(type="tool_use", input={"articles": articles})
    return SimpleNamespace(content=[block])


def _mock_client(response):
    client = Mock()
    client.with_options.return_value = client
    client.messages.create.return_value = response
    return client


# --- 条件網羅テスト(境界値) -------------------------------------------------

def test_body_excerpt_is_truncated_to_max_chars():
    long_text = "あ" * (az.BODY_EXCERPT_CHARS + 500)
    with patch.object(az.requests, "get", return_value=_mock_page_response(text="<html>x</html>")), \
         patch.object(az.trafilatura, "extract", return_value=long_text):
        body = az._fetch_body("https://example.com/a")
    assert len(body) == az.BODY_EXCERPT_CHARS


def test_body_fetch_request_exception_returns_none():
    import requests as requests_module

    with patch.object(az.requests, "get", side_effect=requests_module.Timeout("timeout")):
        assert az._fetch_body("https://example.com/a") is None


def test_body_fetch_non_200_returns_none():
    with patch.object(az.requests, "get", return_value=_mock_page_response(status_code=404)):
        assert az._fetch_body("https://example.com/a") is None


def test_body_fetch_extraction_failure_returns_none():
    with patch.object(az.requests, "get", return_value=_mock_page_response()), \
         patch.object(az.trafilatura, "extract", return_value=None):
        assert az._fetch_body("https://example.com/a") is None


def test_body_fetch_extraction_raises_exception_returns_none():
    with patch.object(az.requests, "get", return_value=_mock_page_response()), \
         patch.object(az.trafilatura, "extract", side_effect=RuntimeError("malformed html")):
        assert az._fetch_body("https://example.com/a") is None


def test_missing_charset_falls_back_to_apparent_encoding():
    response = _mock_page_response(encoding=None, apparent_encoding="shift_jis")
    with patch.object(az.requests, "get", return_value=response), \
         patch.object(az.trafilatura, "extract", return_value="本文"):
        az._fetch_body("https://example.com/a")
    assert response.encoding == "shift_jis"


# --- 機能要件テスト(仕様書7節のAC-1〜AC-6に対応) -----------------------------

def test_ac1_returns_articles_from_claude(monkeypatch):
    candidate = _candidate()
    articles = [{"title": "T", "summary": "S", "url": candidate.url, "source": candidate.source}]
    client = _mock_client(_tool_use_response(articles))
    with patch.object(az.requests, "get", return_value=_mock_page_response(url=candidate.url)), \
         patch.object(az.trafilatura, "extract", return_value="本文"):
        result = az.generate_articles([candidate], client=client)
    assert result == articles
    client.messages.create.assert_called_once()
    assert client.messages.create.call_args.kwargs["model"] == az.MODEL


def test_ac2_no_fetchable_candidates_skips_api_call():
    candidate = _candidate()
    client = _mock_client(_tool_use_response([]))
    with patch.object(az.requests, "get", return_value=_mock_page_response(status_code=500)):
        result = az.generate_articles([candidate], client=client)
    assert result == []
    client.messages.create.assert_not_called()


def test_ac3_candidate_with_failed_fetch_is_excluded_others_continue():
    ok_candidate = _candidate(url="https://example.com/ok")
    bad_candidate = _candidate(url="https://example.com/bad")
    articles = [{"title": "T", "summary": "S", "url": ok_candidate.url, "source": ok_candidate.source}]
    client = _mock_client(_tool_use_response(articles))

    def fake_get(url, timeout, headers):
        if url == bad_candidate.url:
            return _mock_page_response(status_code=500, url=url)
        return _mock_page_response(url=url)

    with patch.object(az.requests, "get", side_effect=fake_get), \
         patch.object(az.trafilatura, "extract", return_value="本文"):
        result = az.generate_articles([bad_candidate, ok_candidate], client=client)
    assert result == articles
    prompt = client.messages.create.call_args.kwargs["messages"][0]["content"]
    assert bad_candidate.url not in prompt
    assert ok_candidate.url in prompt


def test_ac4_api_status_error_raises_summarization_error():
    candidate = _candidate()
    client = _mock_client(None)
    fake_response = httpx.Response(status_code=500, request=httpx.Request("POST", "https://api.anthropic.com/v1/messages"))
    client.messages.create.side_effect = anthropic.APIStatusError("boom", response=fake_response, body=None)
    with patch.object(az.requests, "get", return_value=_mock_page_response()), \
         patch.object(az.trafilatura, "extract", return_value="本文"):
        with pytest.raises(az.SummarizationError):
            az.generate_articles([candidate], client=client)


def test_ac4_api_connection_error_raises_summarization_error():
    candidate = _candidate()
    client = _mock_client(None)
    client.messages.create.side_effect = anthropic.APIConnectionError(
        request=httpx.Request("POST", "https://api.anthropic.com/v1/messages")
    )
    with patch.object(az.requests, "get", return_value=_mock_page_response()), \
         patch.object(az.trafilatura, "extract", return_value="本文"):
        with pytest.raises(az.SummarizationError):
            az.generate_articles([candidate], client=client)


def test_ac5_response_without_tool_use_block_raises_error():
    candidate = _candidate()
    response = SimpleNamespace(content=[SimpleNamespace(type="text", text="not a tool use")])
    client = _mock_client(response)
    with patch.object(az.requests, "get", return_value=_mock_page_response()), \
         patch.object(az.trafilatura, "extract", return_value="本文"):
        with pytest.raises(az.SummarizationError):
            az.generate_articles([candidate], client=client)


def test_ac5_tool_use_missing_articles_key_raises_error():
    candidate = _candidate()
    response = SimpleNamespace(content=[SimpleNamespace(type="tool_use", input={"unexpected": []})])
    client = _mock_client(response)
    with patch.object(az.requests, "get", return_value=_mock_page_response()), \
         patch.object(az.trafilatura, "extract", return_value="本文"):
        with pytest.raises(az.SummarizationError):
            az.generate_articles([candidate], client=client)


def test_more_than_max_articles_is_truncated():
    """toolスキーマにmaxItemsを使えない(Anthropic API制約)ため、コード側で上限を強制する。"""
    candidates = [_candidate(url=f"https://example.com/{i}") for i in range(4)]
    articles = [
        {"title": f"T{i}", "summary": "S", "url": c.url, "source": c.source}
        for i, c in enumerate(candidates)
    ]
    client = _mock_client(_tool_use_response(articles))
    with patch.object(az.requests, "get", return_value=_mock_page_response()), \
         patch.object(az.trafilatura, "extract", return_value="本文"):
        result = az.generate_articles(candidates, client=client)
    assert len(result) == az.MAX_ARTICLES
    assert result == articles[: az.MAX_ARTICLES]


def test_ac6_unknown_url_in_response_raises_error():
    candidate = _candidate()
    articles = [{"title": "T", "summary": "S", "url": "https://not-a-candidate.example.com/x", "source": "出典"}]
    client = _mock_client(_tool_use_response(articles))
    with patch.object(az.requests, "get", return_value=_mock_page_response()), \
         patch.object(az.trafilatura, "extract", return_value="本文"):
        with pytest.raises(az.SummarizationError):
            az.generate_articles([candidate], client=client)
