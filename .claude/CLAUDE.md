# プロジェクト用CLAUDE.md(雛形)

## 最初に行うこと

`docs/PRODUCT.md`・`docs/TECH.md`・`docs/STRUCTURE.md`(鳥瞰図設計書、3ファイルで1層を構成する)と
`docs/システムフォルダ/`(システム単位・コンポーネント単位の設計書、採番台帳)が揃っているか確認する。
- 揃っていない場合: `design-doc-guard`スキルを起動する。スクラッチ開発(まだ何も実装されていない)であれば、
  目的・制約・有効ユニットだけをヒアリングして生成する。コンポーネントのつながり・処理フロー・
  インフラ構成は実装が進んでから埋める。既存コードへの導入であれば、コードを読んでこの時点で埋める。
- 揃っている場合: 内容を読み、対象プロジェクトの目的・現時点の構成・制約を把握してから作業に入る。
  実際のコードと乖離していないか都度疑い、乖離があれば`design-doc-guard`で更新する。
- **コンポーネントの実装・修正指示があったときは、対応する仕様書(コンポーネント単位設計書)が
  存在するか必ず確認する。存在しない場合は実装せず、先に`design-doc-guard`で仕様書を作成する**
  (仕様書は開発手法の選択に関わらず常に必須)。
- 実装・修正で内容が変わるときは、該当する設計書を必ず更新する。
- **コンポーネントの実装・修正は、依頼のたびに毎回`design-doc-guard`4-1節の自走ループ
  (実装→`component-test-guard`→独立サブエージェントでの`code-review-guard`→仕様突き合わせ→
  問題があれば修正して繰り返す)で行う。単発の1回実装では終わらせない。`/goal`コマンドを
  明示的に起動する必要はない**(`/goal`は複数コンポーネント横断など独自の完了条件を指定したいときに使う)。

## ユニット索引

このプロジェクトで有効化しているユニットは`docs/TECH.md`の「5. 開発方針」表を参照。
各ユニットの役割は以下の通り(v0.1時点)。

| ユニット | 種別 | 役割 |
|---|---|---|
| design-doc-guard | skill | 鳥瞰図/システム単位/コンポーネント単位の設計書を生成・更新させ、仕様書のないコンポーネント実装を禁止し、実装を自走ループ(実装→テスト→独立レビュー→仕様突き合わせ)で行わせる(必須・起点) |
| dev-method-guard | skill | TDD/仕様書駆動など開発手法の選定・遵守 |
| security-guard | skill | 実装提案時のセキュリティ観点チェック |
| implementation-rules | rule | 命名・層分担・エラー処理の方針 |
| cost-guard | skill | 設計・代替案比較にコスト観点を追加 |
| logging-rules | rule | ログの粒度・形式・保管方針 |
| ops-guard | skill | ログ起点のLLM自動修正ループの設計パターン |
| client-doc-guard | skill | 非エンジニア向け説明資料の生成 |
| implementation-guard | skill | 実装時に必ず添える判断根拠・外部境界一覧・固定コーディングルール・撤退判断 |
| code-review-guard | skill | 随時のコードレビュー(正確性・重複/簡潔化/効率、依頼時・実装完了時) |
| component-test-guard | skill | コンポーネント単位の単体実行確認(条件網羅・機能・非機能要件テスト)、成果物は仕様書と同フォルダに保管 |
| release-review-guard | skill | コミット/デプロイ前の重大度別レビュー(シークレット・認可を最優先) |
| cicd-guard | skill | CI/CDパイプラインの段階構成・進行的デリバリー/自動ロールバック方針 |
| ai-output-verification-guard | skill | AI生成コード・パッケージ・APIの実在確認、モデルバージョン固定 |
| supply-chain-integrity-guard | skill | ロックファイル整合性・依存関係混同対策・SBOM・ライセンス確認 |
| migration-safety-guard | skill | DBスキーマ変更のExpand-Migrate-Contract・後方互換・ロールバック |
| api-lifecycle-guard | skill | 破壊的変更判定・バージョニング・コントラクトテスト・レート制限 |
| ai-agent-operations-guard | skill | AIエージェント自体のトークンコスト・監査ログ・キルスイッチ・ツール権限最小化 |
| secrets-lifecycle-guard | skill | シークレットのローテーション・失効運用 |
| tech-debt-ledger-guard | skill | 技術的負債の記録・分類・棚卸し(TECH_DEBT_LEDGER.md) |
| git-workflow | rule | feature/fixブランチ運用、developへのマージコミット保持 |

## コマンド索引

`.claude/commands/`配下の開発者が明示的に起動するコマンド。ユニット索引のskill/ruleと異なり、
条件に応じた自動発火はしない。

| コマンド | 役割 |
|---|---|
| /goal | コンポーネント単体の実装には不要(design-doc-guardが自動で自走ループを適用する)。
  複数コンポーネント横断など、開発者が独自の完了条件を指定したいときに使う |
| /adopt-template | 既にCLAUDE.md/rules/skillsを持つ既存プロジェクトへ、この一式を非破壊で移植する。
  コピー先に存在するものは一切上書きせず、存在しない機能だけを補う |

## テンプレートバージョン

- テンプレートID: ai-driven-dev-template
- version: 2.7.0(ユニット追加ごとに更新する。開発者からの直接指示により、根拠のない試行的実装の開示
  (ai-output-verification-guard)、リトライループでのエラー回避禁止・実装後の静的/境界値テスト必須化
  (implementation-guard)、Gitブランチ戦略(git-workflow.md)を追加。以降、随時コードレビューを担う
  code-review-guardを追加し、system-overview-guardをdesign-doc-guardへ改称・拡張して鳥瞰図設計書・
  コンポーネント単位設計書を追加した(旧SYSTEM_OVERVIEW.mdはSYSTEM_DESIGN.mdへ改称)。さらに設計書を
  docs/配下(鳥瞰図1ファイル+システムフォルダ内の採番ファイル)へ再配置し、コンポーネント仕様書を
  実装前の必須ゲート化(dev-method-guardの手法選択より優先)。開発方針表はプロジェクト全体で
  重複させないためBIRDSEYE_DESIGN.md側に集約。component-test-guardを追加し、条件網羅・機能・
  非機能要件テストの成果物を仕様書と同フォルダに保管する運用を追加。以降、自走ループ用の
  /goalコマンドを追加し、既存skillの呼び出し順序をオーケストレーションする形で導入した。さらに、
  cc-sdd(gotalab/cc-sdd)の考え方を参考に、鳥瞰図設計書をBIRDSEYE_DESIGN.md単一ファイルから
  PRODUCT.md/TECH.md/STRUCTURE.mdの3ファイル構成へ再編し、コンポーネント仕様書にEARS形式の
  受け入れ条件を追加し、システム単位設計書のコンポーネント表に依存関係・並列実装可否列を追加し、
  /goalのレビュー工程を実装者と分離した独立サブエージェント実行に変更した。以降、既存プロジェクトへの
  非破壊移植を担う/adopt-templateコマンドを追加した。以降、自走ループを/goal起動なしでも常に
  適用されるdesign-doc-guardの既定手順(4-1節)へ移し、/goalは複数コンポーネント横断など
  独自の完了条件を指定する場合専用に縮小した)
- 元テンプレート更新の追従は手動。差分確認が必要な場合はversion行を比較する。
