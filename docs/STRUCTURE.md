# プロジェクト構造

## 1. ディレクトリ構成
現時点(101・102実装済み)の実際の構成。

```
プロジェクトルート/
├── .claude/            # このテンプレート一式
├── .vscode/             # エディタ設定
├── .github/
│   └── workflows/
│       └── daily-news.yml  # src.orchestratorを起動するworkflow(workflow_dispatchのみ、
│                            # 起動自体はcron-job.orgが毎日9:05 JSTに外部から行う)
├── docs/                # 設計書一式(鳥瞰図 + システムフォルダ)
├── src/
│   ├── common/
│   │   └── logging_setup.py   # 構造化ロギング共通基盤(logging-rules.md準拠)
│   ├── news_collector.py      # 101: ニュース収集
│   ├── state_store.py         # 102: 重複判定・状態管理
│   ├── article_summarizer.py  # 103: 記事要約・生成(Claude API)
│   ├── line_notifier.py       # 104: LINE配信
│   └── orchestrator.py        # 105: オーケストレーター(エントリポイント)
├── tests/               # pytestによるコンポーネント単体テスト(component-test-guardのドライバ)
├── data/                # 102が書き込む状態ファイル(delivered.json)の格納先
├── logging-config.json  # logging-rules.mdが参照する実行時設定
├── requirements.txt      # 本番実行用の依存関係
└── requirements-dev.txt  # テスト用の依存関係(pytest等)を追加
```

101〜105すべて実装済み。未着手: LINE公式アカウントの実運用準備(チャネルアクセストークン
発行・userId取得・GitHub Secretsへの登録)。これが完了するまでworkflowは実行しても
LINE配信ステップでエラーになる(104のAC-3)。

## 2. 稼働システム一覧

| 番号 | システム名 | 役割(1行) | システム単位設計書 |
|---|---|---|---|
| 100 | AI駆動開発ニュース配信システム | AI駆動開発関連の最新情報を収集・要約し、毎朝LINEへ通知する | docs/システムフォルダ/100-システム仕様書.md |

## 3. 大まかな入力から出力までの流れ
未実装。設計上の想定は次の通り(システム単位設計書「3. 入力から出力までの処理フロー」で詳細化する)。

- 入力元: RSS/ニュースフィード各種(日本語・英語のAI駆動開発関連ソース)
- 経由: システム100(収集→重複除外→要約→配信)
- 出力先: LINE(Messaging APIのプッシュメッセージとして開発者本人へ通知)
