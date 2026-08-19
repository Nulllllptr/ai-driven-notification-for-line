"""104 LINE配信: 103が生成した記事をLINE Messaging APIでプッシュ送信する。

仕様: docs/システムフォルダ/104-LINE配信-仕様書.md
"""
import os
import re
import time
from datetime import datetime
from zoneinfo import ZoneInfo

import requests

from src.common.logging_setup import get_logger

logger = get_logger("line_notifier")

PUSH_ENDPOINT = "https://api.line.me/v2/bot/message/push"
REQUEST_TIMEOUT_SECONDS = 10
MAX_RETRIES = 1
RETRY_DELAY_SECONDS = 2
JST = ZoneInfo("Asia/Tokyo")
_BEARER_TOKEN_PATTERN = re.compile(r"Bearer\s+\S+")


class LineNotificationError(Exception):
    """LINE Messaging APIへの送信に失敗した場合に送出する(仕様書 AC-3〜AC-5)。"""


def _format_message(articles: list[dict], now: datetime | None = None) -> str:
    now = now or datetime.now(JST)
    lines = [f"AI駆動開発 ニュースまとめ ({now.strftime('%Y-%m-%d')})", ""]
    for article in articles:
        lines.append(f"■ {article['title']}")
        lines.append(article["summary"])
        lines.append(article["url"])
        lines.append(f"(出典: {article['source']})")
        lines.append("")
    return "\n".join(lines).rstrip()


def _is_retryable(status_code: int) -> bool:
    return status_code == 429 or status_code >= 500


def _post_once(payload: dict, headers: dict) -> requests.Response:
    return requests.post(PUSH_ENDPOINT, json=payload, headers=headers, timeout=REQUEST_TIMEOUT_SECONDS)


def _mask_token(message: str) -> str:
    """例外メッセージ等にAuthorizationヘッダの値が紛れ込んでもトークンを露出させない最終防御。"""
    return _BEARER_TOKEN_PATTERN.sub("Bearer ***", message)


def send_articles(articles: list[dict], now: datetime | None = None) -> None:
    """記事一覧を1件のテキストメッセージにまとめLINEへプッシュ送信する。

    articlesが空の場合は何もしない(「3件未満は送信しない」という業務判断は105が行う。
    ここでは0件呼び出しに対する二重の安全策としてスキップする)。
    """
    if not articles:
        logger.info("no articles to send, skipping LINE push")
        return

    channel_access_token = os.environ.get("LINE_CHANNEL_ACCESS_TOKEN")
    user_id = os.environ.get("LINE_USER_ID")
    if not channel_access_token or not user_id:
        raise LineNotificationError("LINE_CHANNEL_ACCESS_TOKEN / LINE_USER_ID is not set")

    payload = {"to": user_id, "messages": [{"type": "text", "text": _format_message(articles, now=now)}]}
    headers = {"Content-Type": "application/json", "Authorization": f"Bearer {channel_access_token}"}

    attempts = 0
    last_error = ""
    while attempts <= MAX_RETRIES:
        attempts += 1
        try:
            response = _post_once(payload, headers)
        except requests.RequestException as exc:
            last_error = _mask_token(str(exc))
            logger.warning("LINE push request failed (attempt %d): %s", attempts, last_error)
            if attempts > MAX_RETRIES:
                break
            time.sleep(RETRY_DELAY_SECONDS)
            continue

        if response.status_code == 200:
            logger.info("sent %d articles to LINE", len(articles))
            return

        last_error = _mask_token(f"status={response.status_code} body={response.text}")
        if not _is_retryable(response.status_code) or attempts > MAX_RETRIES:
            break
        logger.warning("LINE push failed, retrying (attempt %d): %s", attempts, last_error)
        time.sleep(RETRY_DELAY_SECONDS)

    raise LineNotificationError(f"LINE push failed after {attempts} attempt(s): {last_error}")
