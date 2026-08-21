# 技術スタック・開発方針

## 1. インフラ構成
- 実行基盤: GitHub Actions(`.github/workflows/daily-news.yml`、`workflow_dispatch`トリガーのみ)。
  起動そのものは外部の無料cronサービス**cron-job.org**が毎日9:05 JSTにGitHub REST APIの
  workflow dispatchエンドポイントを呼ぶことで行う。GitHub Actions native の`schedule`(cron)
  トリガーは実運用で一度も発火しないことが確認されたため不採用とした(GitHub側の既知の信頼性
  問題、105の仕様書「改訂履歴」参照)
- リポジトリ: 本リポジトリ(public)。public repoはGitHub Actionsの実行時間が無料枠無制限
- cron-job.org呼び出し用のGitHub Fine-grained Personal Access Token(`Actions: Read and write`
  権限、このリポジトリのみに限定)を発行し、cron-job.org側にのみ登録する。このトークンは
  本リポジトリのGitHub Secretsには含めない(リポジトリ内のコードからは使わないため)
- 外部API連携:
  - LINE Messaging API(プッシュメッセージ送信。月200通まで無料)
  - Anthropic API(Claude、記事要約・重複判定用途。従量課金、月数百円程度を許容する方針)
  - ニュース収集元のRSS/フィード各種(無料)
- データストア: 専用DBは持たない。配信済み記事の状態は本リポジトリ内のJSONファイルで管理し、
  ワークフロー実行のたびにActionsがコミットして更新する(外部DBサービスは使わない)

## 2. 技術スタック(実装に追従して更新)
- 言語: Python 3.13
- 主要ライブラリ: `feedparser`(RSS/Atom解析)、`requests`(HTTP取得)、
  `trafilatura`(記事本文抽出)、`anthropic`(Claude API SDK、モデルは`claude-haiku-4-5`に固定)、
  `tzdata`(JST日時表示の環境非依存化)
- 開発・テスト用: `pytest`(`requirements-dev.txt`に分離)

## 3. ビルド・実行コマンド
- 依存インストール: `pip install -r requirements-dev.txt`
- テスト実行: `python -m pytest tests/`
- 本番実行: `python -m src.orchestrator`(GitHub Actionsの`.github/workflows/daily-news.yml`を
  cron-job.orgが毎日9:05 JSTに`workflow_dispatch`で起動。Actionsタブから手動実行も可能)

## 4. 環境変数
GitHub Secretsに登録し、値そのものはここに書かない(secrets-lifecycle-guardの対象)。

| 変数名 | 用途 |
|---|---|
| LINE_CHANNEL_ACCESS_TOKEN | LINE Messaging APIのチャネルアクセストークン |
| LINE_USER_ID | 通知の送信先(自分のuserId、またはbroadcast送信に切り替える場合は不要) |
| ANTHROPIC_API_KEY | 記事要約・重複判定に使うClaude APIのキー |

## 5. 開発方針(このプロジェクトで有効なユニット)

個人の小規模自動化プロジェクトのため、実益のある主要ユニットのみ有効化する
(開発者の了承を得た方針。異論があれば都度見直す)。

| ユニット | 有効/無効 | 補足 |
|---|---|---|
| design-doc-guard | 有効 | 必須・起点 |
| implementation-guard | 有効 | |
| code-review-guard | 有効 | |
| component-test-guard | 有効 | 条件網羅/機能/非機能テスト |
| security-guard | 有効 | LINE/Anthropicトークンを扱うため |
| cost-guard | 有効 | 無料枠・従量課金の比較検討用 |
| logging-rules | 有効 | GitHub Actions実行ログの方針 |
| secrets-lifecycle-guard | 有効 | チャネルアクセストークン・APIキーのローテーション |
| release-review-guard | 有効 | コミット前のシークレット混入・認可チェック |
| git-workflow | 有効(rule) | feature/fixブランチ運用 |
| implementation-rules | 有効(rule) | 命名・層分担・エラー処理方針の蓄積先 |
| ai-output-verification-guard | 有効 | 外部ライブラリ・API・LLMモデルバージョンの実在確認 |
| dev-method-guard | 無効 | design-doc-guardの仕様書必須化(4節)で代替済み |
| ops-guard | 無効 | ログ起点の自動修正ループは個人小規模用途には過剰 |
| client-doc-guard | 無効 | 非エンジニア向け説明資料は不要 |
| cicd-guard | 無効 | 単一のGitHub Actionsワークフローのみで、段階的デリバリー構成は不要 |
| supply-chain-integrity-guard | 無効 | 個人小規模、SBOM等の運用は過剰 |
| migration-safety-guard | 無効 | DBスキーマを持たない |
| api-lifecycle-guard | 無効 | 外部公開APIを提供しない |
| ai-agent-operations-guard | 無効 | 高頻度・長時間のAIエージェント運用は行わない |
| tech-debt-ledger-guard | 無効 | 必要な妥協が生じた時点で有効化を検討 |
