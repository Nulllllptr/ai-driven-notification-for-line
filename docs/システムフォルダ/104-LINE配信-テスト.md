# コンポーネントテスト: LINE配信

対応する仕様書は`./104-LINE配信-仕様書.md`。

## 1. テスト方針
条件網羅テスト・機能要件テストの2観点で行う。非機能要件テストは該当なし(4節参照)。
上位モジュール(105)が未実装のため、`tests/test_line_notifier.py`(pytest)から
`send_articles()`を直接呼び出すドライバ形式で単体実行確認した。`requests.post`をモック化し、
実際のLINE Messaging APIへの通信は行っていない。リトライ間の`time.sleep`もモック化し、
テスト実行時間に影響しないようにした。

## 2. 条件網羅テスト(分岐・境界値)

| ケースID | 入力条件 | 期待結果 | 実施結果 | 実施日 |
|---|---|---|---|---|
| T-01 | 記事2件、日付指定あり | メッセージ本文に日付と両記事のタイトルが含まれる | PASS | 2026-08-19 |
| T-02 | `LINE_CHANNEL_ACCESS_TOKEN`未設定 | `LineNotificationError`が送出される | PASS | 2026-08-19 |
| T-03 | `LINE_USER_ID`未設定 | `LineNotificationError`が送出される | PASS | 2026-08-19 |

## 3. 機能要件テスト
仕様書「7. 受け入れ条件(EARS形式)」の各IDに対応するテストを実施する。

| ケースID | 対応する受け入れ条件ID | 入力 | 期待出力 | 実施結果 | 実施日 |
|---|---|---|---|---|---|
| T-AC1 | AC-1 | 記事2件 | `requests.post`が1回だけ呼ばれ、`to`/`Authorization`/1件のtextメッセージが正しく設定される | PASS | 2026-08-19 |
| T-AC2 | AC-2 | 記事0件 | `requests.post`が呼ばれない | PASS | 2026-08-19 |
| T-AC3 | AC-3 | 認証情報未設定 | リクエスト送信前に`LineNotificationError`が送出される | PASS | 2026-08-19 |
| T-AC4a | AC-4 | 1回目500応答、2回目200応答 | 2回呼ばれ、最終的に成功する | PASS | 2026-08-19 |
| T-AC4b | AC-4 | 1回目ネットワークエラー、2回目200応答 | 2回呼ばれ、最終的に成功する | PASS | 2026-08-19 |
| T-AC5a | AC-5 | 常に500応答 | 初回+1回のリトライ(計2回)後に`LineNotificationError`が送出される | PASS | 2026-08-19 |
| T-AC5b | AC-5 | 400応答(非リトライ対象) | リトライせず1回で`LineNotificationError`が送出される | PASS | 2026-08-19 |

## 4. 非機能要件テスト
仕様書「6. 制約・注意事項」の記載(文字数上限・レート制限・トークンの非ログ出力)のうち、
文字数上限超過時の切り詰めは実装しない設計判断であり数値基準を伴うテスト対象ではない。
レート制限は1日1回の送信であれば問題にならない旨の記載であり、実行時に検証すべき閾値は
ない。該当なし。

## 5. ドライバでの実行確認メモ
`tests/test_line_notifier.py`をドライバとして使用。`requests.post`をモック化し、
`LINE_CHANNEL_ACCESS_TOKEN`/`LINE_USER_ID`は`monkeypatch.setenv`でテスト用の値を設定した。

## 6. 独立レビューでの指摘と対応(2026-08-19)
実装者と独立したサブエージェントによるレビューで2点の指摘があり、同じループ内で対応した。
- 例外メッセージ・エラー応答本文にAuthorizationヘッダの値が万一混入した場合、共通ロギング
  基盤(`logging_setup.py`)の`mask_fields`正規表現だけでは`Bearer <token>`のトークン部分まで
  マスクしきれない(空白区切りの語1つしか置換しないため) → `line_notifier.py`に
  `Bearer\s+\S+`を専用にマスクする`_mask_token`を追加し、`last_error`生成箇所すべてに適用。
  `test_mask_token_redacts_bearer_value`で検証
- `LINE_USER_ID`未設定時のテストが例外送出のみ確認しており、`LINE_CHANNEL_ACCESS_TOKEN`未設定側
  と異なり送信スキップ(`requests.post`が呼ばれないこと)を検証していなかった → 対称になるよう
  `mock_post.assert_not_called()`を追加
- (対応不要・情報レベル) `attempts > MAX_RETRIES`のガードは外側ループ条件により実質到達
  不能な冗長ガードとの指摘。無駄なsleepを避ける効果があり実害もないため現状維持
