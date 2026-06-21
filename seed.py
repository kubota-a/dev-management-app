from __future__ import annotations

from datetime import date, datetime, time, timedelta, timezone
from decimal import Decimal
from zoneinfo import ZoneInfo

from werkzeug.security import generate_password_hash

from app import app
from models import (
    BudgetActualLog,
    Department,
    DepartmentMember,
    DepartmentMembership,
    DepartmentYearlyBudget,
    Notification,
    Project,
    ProjectDraft,
    ProjectReport,
    ProjectStatusLog,
    Task,
    User,
    db,
    utc_now,
)


# 実行日基準でデモ用データを作成します。
# Render Shell から daily reset する運用を想定しています。

JST = ZoneInfo("Asia/Tokyo")


DEPARTMENTS = [
    {"key": "sys_dev", "name": "システム開発部"},
    {"key": "infra", "name": "情報基盤部"},
    {"key": "biz_reform", "name": "業務改革推進部"},
]

YEARLY_BUDGETS_2026 = [
    {"department_key": "sys_dev", "fiscal_year": 2026, "annual_budget_amount": 18_000_000},
    {"department_key": "infra", "fiscal_year": 2026, "annual_budget_amount": 15_000_000},
    {"department_key": "biz_reform", "fiscal_year": 2026, "annual_budget_amount": 16_000_000},
]

USERS = [
    {"key": "tanaka", "login_id": "tanaka", "display_name": "田中 拓海", "role": "applicant", "department_key": "sys_dev"},
    {"key": "sato", "login_id": "sato", "display_name": "佐藤 美咲", "role": "applicant", "department_key": "sys_dev"},
    {"key": "yamamoto", "login_id": "yamamoto", "display_name": "山本 瑞希", "role": "manager", "department_key": "sys_dev"},
    {"key": "suzuki", "login_id": "suzuki", "display_name": "鈴木 孝介", "role": "applicant", "department_key": "infra"},
    {"key": "takahashi", "login_id": "takahashi", "display_name": "高橋 彩乃", "role": "applicant", "department_key": "infra"},
    {"key": "nakamura", "login_id": "nakamura", "display_name": "中村 直樹", "role": "manager", "department_key": "infra"},
    {"key": "ito", "login_id": "ito", "display_name": "伊藤 良太", "role": "applicant", "department_key": "biz_reform"},
    {"key": "watanabe", "login_id": "watanabe", "display_name": "渡辺 優菜", "role": "applicant", "department_key": "biz_reform"},
    {"key": "morita", "login_id": "morita", "display_name": "森田 葵", "role": "applicant", "department_key": "biz_reform"},
    {"key": "fujimoto", "login_id": "fujimoto", "display_name": "藤本 健", "role": "applicant", "department_key": "biz_reform"},
    {"key": "kobayashi", "login_id": "kobayashi", "display_name": "小林 理絵", "role": "manager", "department_key": "biz_reform"},
    {"key": "tajiri", "login_id": "tajiri", "display_name": "田尻 憲市郎", "role": "hq", "department_key": None},
]

# README/ログイン画面向けおすすめアカウント
# - 申請者（おすすめ）: watanabe / 渡辺 優菜
# - 部門管理者（おすすめ）: kobayashi / 小林 理絵
# - 本部管理者（おすすめ）: tajiri / 田尻 憲市郎

PROJECT_DRAFTS = [
    {
        "user_key": "sato",
        "department_key": "sys_dev",
        "title": "承認コメント履歴表示の改善案",
        "purpose": "差し戻し理由の把握時間を短縮するため、履歴表示の視認性を高めます。",
        "estimated_person_months": "1.20",
        "estimated_budget_amount": "850000",
        "date_role": "draft_recent_a",
    },
    {
        "user_key": "sato",
        "department_key": "sys_dev",
        "title": "案件テンプレート選択機能の検討",
        "purpose": "申請入力のばらつきを抑えるため、初期入力テンプレートを導入します。",
        "estimated_person_months": None,
        "estimated_budget_amount": None,
        "date_role": "draft_recent_b",
    },
    {
        "user_key": "takahashi",
        "department_key": "infra",
        "title": "端末棚卸し連携の半自動化",
        "purpose": "棚卸し台帳更新の手作業を削減し、更新遅延を防止します。",
        "estimated_person_months": "1.80",
        "estimated_budget_amount": "1200000",
        "date_role": "draft_recent_c",
    },
    {
        "user_key": "watanabe",
        "department_key": "biz_reform",
        "title": "業務手順ナレッジ検索導線の再設計",
        "purpose": None,
        "estimated_person_months": "1.50",
        "estimated_budget_amount": "980000",
        "date_role": "draft_recent_d",
    },
    {
        "user_key": "watanabe",
        "department_key": "biz_reform",
        "title": "業務マニュアルAI検索機能の試験導入",
        "purpose": None,
        "estimated_person_months": "1.00",
        "estimated_budget_amount": None,
        "date_role": "draft_recent_e",
    },
]

PROJECTS = [
    {"key": "proj_01", "project_code": "REQ-2026-00001", "title": "開発管理ポータル通知機能改善", "applicant_key": "tanaka", "status": "department_pending", "approval_stage": "department_pending", "budget": "1800000", "pm": "2.50", "date_role": "pending_waiting", "planned_role": "pending_start_normal"},
    {"key": "proj_02", "project_code": "REQ-2026-00002", "title": "承認フロー画面の操作性改善", "applicant_key": "sato", "status": "hq_pending", "approval_stage": "hq_pending", "budget": "3200000", "pm": "3.50", "date_role": "hq_pending_normal", "planned_role": "pending_start_soon"},
    {"key": "proj_03", "project_code": "REQ-2026-00003", "title": "案件一覧検索機能追加", "applicant_key": "sato", "status": "in_progress", "approval_stage": "approved", "budget": "2400000", "pm": "3.00", "date_role": "progress_normal", "planned_role": "progress_start_mid"},
    {"key": "proj_04", "project_code": "REQ-2026-00004", "title": "申請フォーム入力補助機能導入", "applicant_key": "tanaka", "status": "completed", "approval_stage": "approved", "budget": "1600000", "pm": "2.00", "date_role": "completed_old", "planned_role": "completed_start_old"},
    {"key": "proj_05", "project_code": "REQ-2026-00005", "title": "社内認証基盤連携対応", "applicant_key": "suzuki", "status": "department_pending", "approval_stage": "department_pending", "budget": "2800000", "pm": "3.20", "date_role": "pending_recent", "planned_role": "pending_start_late"},
    {"key": "proj_06", "project_code": "REQ-2026-00006", "title": "操作ログ集約基盤整備", "applicant_key": "takahashi", "status": "hq_pending", "approval_stage": "hq_pending", "budget": "4000000", "pm": "4.20", "date_role": "hq_pending_recent", "planned_role": "pending_start_normal"},
    {"key": "proj_07", "project_code": "REQ-2026-00007", "title": "バックアップ運用可視化対応", "applicant_key": "suzuki", "status": "in_progress", "approval_stage": "approved", "budget": "2300000", "pm": "2.80", "date_role": "progress_delayed", "planned_role": "progress_start_old"},
    {"key": "proj_08", "project_code": "REQ-2026-00008", "title": "権限棚卸し支援ダッシュボード作成", "applicant_key": "takahashi", "status": "completed", "approval_stage": "approved", "budget": "2100000", "pm": "2.60", "date_role": "completed_recent", "planned_role": "completed_start_recent"},
    {"key": "proj_09", "project_code": "REQ-2026-00009", "title": "Excel進捗管理廃止に向けた統合化PoC", "applicant_key": "ito", "status": "department_pending", "approval_stage": "department_pending", "budget": "3600000", "pm": "3.50", "date_role": "pending_ito_recent", "planned_role": "pending_start_late"},
    {"key": "proj_10", "project_code": "REQ-2026-00010", "title": "月次レポート入力改善", "applicant_key": "watanabe", "status": "in_progress", "approval_stage": "approved", "budget": "1800000", "pm": "2.30", "date_role": "progress_due_soon", "planned_role": "progress_start_recent"},
    {"key": "proj_11", "project_code": "REQ-2026-00011", "title": "予算執行状況の可視化機能追加", "applicant_key": "ito", "status": "in_progress", "approval_stage": "approved", "budget": "4200000", "pm": "4.00", "date_role": "progress_normal", "planned_role": "progress_start_mid"},
    {"key": "proj_12", "project_code": "REQ-2026-00012", "title": "旧申請システム移行準備案件", "applicant_key": "watanabe", "status": "rejected", "approval_stage": "rejected", "budget": "2700000", "pm": "3.00", "date_role": "rejected_recent", "planned_role": "pending_start_normal"},
    {"key": "proj_13", "project_code": "REQ-2026-00013", "title": "業務ナレッジ共有ポータル改善", "applicant_key": "watanabe", "status": "hq_pending", "approval_stage": "hq_pending", "budget": "1900000", "pm": "2.20", "date_role": "pending_watanabe_recent", "planned_role": "pending_start_normal"},
    {"key": "proj_14", "project_code": "REQ-2026-00014", "title": "ナレッジ検索改善", "applicant_key": "watanabe", "status": "in_progress", "approval_stage": "approved", "budget": "2600000", "pm": "3.10", "date_role": "progress_watanabe_attention", "planned_role": "progress_start_recent"},
    {"key": "proj_15", "project_code": "REQ-2026-00015", "title": "社内申請ワークフロー簡素化対応", "applicant_key": "watanabe", "status": "completed", "approval_stage": "approved", "budget": "1700000", "pm": "2.00", "date_role": "completed_watanabe_recent", "planned_role": "completed_start_recent"},
    {"key": "proj_16", "project_code": "REQ-2026-00016", "title": "業務マニュアル検索改善", "applicant_key": "watanabe", "status": "in_progress", "approval_stage": "approved", "budget": "2500000", "pm": "2.80", "date_role": "progress_due_soon", "planned_role": "progress_start_recent"},
    {"key": "proj_17", "project_code": "REQ-2026-00017", "title": "FAQ更新支援ツール導入", "applicant_key": "watanabe", "status": "department_pending", "approval_stage": "department_pending", "budget": "1600000", "pm": "1.80", "date_role": "pending_watanabe_recent", "planned_role": "pending_start_normal"},
    {"key": "proj_18", "project_code": "REQ-2026-00018", "title": "申請テンプレート整備", "applicant_key": "morita", "status": "in_progress", "approval_stage": "approved", "budget": "1400000", "pm": "1.60", "date_role": "progress_normal", "planned_role": "progress_start_recent"},
]

PROJECT_PURPOSE = {
    "proj_01": "通知の取りこぼしを減らし、承認待ち案件の初動を早めます。",
    "proj_02": "承認者の操作手順を短縮し、差し戻し処理の負荷を下げます。",
    "proj_03": "案件検索精度を高め、担当者が必要な案件へ即時到達できるようにします。",
    "proj_04": "入力の迷いを減らし、申請品質の平準化を目指します。",
    "proj_05": "認証基盤連携でログイン運用を統一し、管理コストを削減します。",
    "proj_06": "操作ログを集約し、監査対応と障害調査の初動を短縮します。",
    "proj_07": "バックアップ運用状況を可視化し、見落としリスクを低減します。",
    "proj_08": "棚卸し対応の作業工数を抑え、統制運用の定着を促進します。",
    "proj_09": "Excel依存を段階的に廃止し、進捗管理を単一運用へ移行します。",
    "proj_10": "月次報告の入力負荷を軽減し、報告遅延の発生を抑制します。",
    "proj_11": "予算執行の見える化で、部門別の判断速度を高めます。",
    "proj_12": "移行対象を明確化し、次期移行計画の精度向上を図ります。",
    "proj_13": "部門内に分散している業務ナレッジを探しやすくし、問い合わせ対応や引き継ぎにかかる時間を短縮します。",
    "proj_14": "部門内に分散しているナレッジを検索しやすくし、問い合わせ対応や引き継ぎにかかる時間を短縮します。",
    "proj_15": "申請内容の確認から承認依頼までの手順を整理し、申請者と承認者双方の確認負荷を軽減します。",
    "proj_16": "業務マニュアル検索の精度と導線を改善し、問い合わせ対応時間の短縮を目指します。",
    "proj_17": "FAQ更新業務の属人化を防ぎ、問い合わせ対応で利用しやすい更新支援フローを整備します。",
    "proj_18": "申請テンプレートを標準化し、申請品質の平準化と作成時間の短縮を図ります。",
}

PROJECT_SUMMARIES = {
    "proj_01": "主な施策：\n・案件更新イベントを契機にした通知生成の見直し\n・通知一覧の優先表示ルール整理\n・既読操作の導線短縮と一括既読の追加\n\n期待効果：\n・通知見落とし件数の削減\n・承認初動までの平均時間短縮\n・利用者からの問い合わせ件数低減",
    "proj_02": "主な施策：\n・承認画面の入力必須箇所を上部に再配置\n・差し戻し理由入力の補助文言整備\n・案件比較時に必要な情報の折りたたみ表示導入\n\n期待効果：\n・承認1件あたりの操作時間短縮\n・差し戻し理由の記載品質向上\n・承認者の作業負担平準化",
    "proj_03": "主な施策：\n・案件名、申請者、状態を横断する複合検索追加\n・検索条件の保存と再利用機能を実装\n・検索結果の応答速度改善に向けた索引最適化\n\n期待効果：\n・案件探索時間の短縮\n・担当者ごとの検索手順ばらつき解消\n・月次確認作業の効率向上",
    "proj_04": "主な施策：\n・申請フォームの入力補助候補を項目ごとに整備\n・過去案件の入力値を参照する候補提示を追加\n・入力エラー時の案内文を業務文脈に合わせて改善\n\n期待効果：\n・入力ミス削減と再申請率低減\n・申請作成に必要な時間の短縮\n・新人利用者の立ち上がり支援",
    "proj_05": "主な施策：\n・社内認証基盤の連携方式を現行運用へ適合\n・権限情報同期の周期と失敗時再実行を定義\n・ログイン障害時の切り分け手順を標準化\n\n期待効果：\n・認証運用の一本化による管理工数削減\n・アカウント運用ミスの抑制\n・障害発生時の復旧時間短縮",
    "proj_06": "主な施策：\n・複数システムの操作ログ収集形式を統一\n・検索しやすい共通キーを定義して保存\n・監査向けの抽出テンプレートを整備\n\n期待効果：\n・監査資料作成時間の短縮\n・障害調査時のログ追跡性向上\n・運用チーム間の連携品質改善",
    "proj_07": "主な施策：\n・バックアップ実行結果を日次で可視化する画面を作成\n・失敗ジョブの検知条件と通知基準を明確化\n・運用手順の更新履歴を追える形で整備\n\n期待効果：\n・障害予兆の早期発見\n・バックアップ失敗の長期放置防止\n・運用担当者の引き継ぎ負荷軽減",
    "proj_08": "主な施策：\n・権限棚卸し対象の抽出ルールをテンプレート化\n・対象部門別の確認状況をダッシュボード表示\n・是正対応の進捗を一元管理する運用を整備\n\n期待効果：\n・棚卸し作業の見える化\n・未対応アカウントの早期特定\n・統制監査への説明容易化",
    "proj_09": "主な施策：\n・Excel管理項目を現行ポータル項目へマッピング\n・PoCで必要な最小機能を定義して段階移行を検証\n・部門横断で進捗定義を統一して入力ルール化\n\n期待効果：\n・二重管理の解消\n・進捗報告の更新遅れ削減\n・本移行計画の精度向上",
    "proj_10": "主な施策：\n・月次報告フォームの必須項目を整理し入力点数を削減\n・前月データの流用機能と入力補助を導入\n・提出前チェックを自動化して差し戻し要因を抑制\n\n期待効果：\n・報告作成時間の短縮\n・入力漏れの未然防止\n・月初の業務集中緩和",
    "proj_11": "主な施策：\n・予算計画と実績の差異を部門単位で可視化\n・執行率の閾値超過を把握しやすい表示へ改善\n・月次レビュー向けに時系列比較を追加\n\n期待効果：\n・予算超過傾向の早期把握\n・対策判断までのリードタイム短縮\n・部門マネジメントの説明力向上",
    "proj_12": "主な施策：\n・旧システム機能を対象範囲ごとに棚卸し\n・移行優先度と依存関係を整理した台帳を整備\n・現行運用との差分観点をレビュー可能な形で作成\n\n期待効果：\n・移行漏れリスクの抑制\n・次期案件化時の見積精度向上\n・関係部門との合意形成迅速化",
    "proj_13": "主な施策：\n・業務カテゴリ別のナレッジ整理\n・よく使う手順への導線追加\n・検索結果の表示順見直し\n\n期待効果：\n・問い合わせ対応時間の短縮\n・属人化した手順確認の削減\n・新人メンバーの立ち上がり支援",
    "proj_14": "主な施策：\n・ナレッジカテゴリとタグの整理\n・検索条件と検索結果表示の見直し\n・よく使う手順への導線追加\n\n期待効果：\n・問い合わせ対応時間の短縮\n・属人化した手順確認の削減\n・新人メンバーの立ち上がり支援",
    "proj_15": "主な施策：\n・申請フォームの入力項目整理\n・承認前チェック項目の見直し\n・完了報告までの導線整備\n\n期待効果：\n・申請作成時間の短縮\n・差し戻し件数の削減\n・完了報告の抜け漏れ防止",
    "proj_16": "主な施策：\n・業務マニュアル検索条件の最適化\n・よく参照される導線の改善\n・検索結果表示の見直し\n\n期待効果：\n・問い合わせ対応時間の短縮\n・検索精度の向上\n・現場の調査負荷軽減",
    "proj_17": "主な施策：\n・FAQ更新フローの標準化\n・更新差分チェック手順の整備\n・問い合わせ対応への反映導線追加\n\n期待効果：\n・FAQ更新漏れの削減\n・問い合わせ一次対応の迅速化\n・更新作業の属人化防止",
    "proj_18": "主な施策：\n・申請テンプレート項目の標準化\n・案件種別ごとの記入ガイド整備\n・申請前チェックリストの導入\n\n期待効果：\n・申請内容のばらつき抑制\n・差し戻し件数の削減\n・申請作成時間の短縮",
}

PROJECT_MONTHLY_REPORTS = {
    "proj_03": "検索条件UIの設計とAPI実装を進めています。検索条件の保存機能は設計方針が固まり、現在は検索APIの実装とインデックス最適化の検証を行っています。",
    "proj_07": "バックアップジョブ見直しと監視閾値調整を進めています。一部タスクに遅れが出ているため、担当者間で優先度を見直しながら対応しています。",
    "proj_10": "月次報告フォームの入力項目整理と画面遷移改善を進めています。入力補助ロジックの実装に着手しており、次回は部門ヒアリング結果を反映する予定です。",
    "proj_11": "予算執行状況の集計ロジックとグラフ表示の調整を進めています。予算消化が大きいため、残作業の範囲と追加費用の見込みを確認しています。",
    "proj_14": "ナレッジカテゴリとタグ整理を進めています。検索結果の表示順改善に一部遅れがあるため、利用頻度の高い手順から優先して調整しています。",
    "proj_04": "申請フォーム入力補助機能の導入作業は完了しました。入力補助候補の整備、フォーム文言改修、操作説明更新まで完了しています。",
    "proj_08": "権限棚卸し支援ダッシュボード作成は完了しました。権限一覧取り込み、棚卸し画面実装、判定ルール調整まで完了しています。",
    "proj_15": "社内申請ワークフロー簡素化対応は完了しました。申請手順の棚卸し、入力項目整理、承認前チェック項目の調整まで完了しています。",
    "proj_16": "業務マニュアル検索改善を進めています。検索条件調整と表示改善を実施し、次回は利用ログを見ながら精度調整を行う予定です。",
}

PROJECT_MONTHLY_REPORT_ROLES = {
    "proj_03": "report_mid",
    "proj_07": "report_old",
    "proj_10": "report_recent",
    "proj_11": "report_mid",
    "proj_14": "report_recent",
    "proj_04": "report_completed_old",
    "proj_08": "report_completed",
    "proj_15": "report_completed",
    "proj_16": "report_recent",
}

PROJECT_REPORT_MONTHLY_HISTORY = {
    "proj_03": [
        "今月は検索条件の洗い出しと画面設計を中心に進めました。主要な検索軸は固まり、大きな課題はありません。",
        "検索条件UIの実装と保存機能の設計を進めました。API連携部分の確認事項はありますが、全体の進捗は予定範囲内です。",
        "検索条件UIの設計とAPI実装を進めています。検索条件の保存機能は設計方針が固まり、現在は検索APIの実装とインデックス最適化の検証を行っています。",
    ],
    "proj_04": [
        "入力補助候補の整理とフォーム文言の見直しを進めました。利用者レビューでも大きな手戻りは発生していません。",
        "申請フォーム入力補助機能の導入作業は完了しました。入力補助候補の整備、フォーム文言改修、操作説明更新まで完了しています。",
    ],
    "proj_07": [
        "対象サーバの整理と現行バックアップ運用の確認を実施しました。運用課題の洗い出しを完了しています。",
        "バックアップジョブ見直しと監視閾値調整を進めています。一部タスクに遅れが出ているため、担当者間で優先度を見直しながら対応しています。",
    ],
    "proj_08": [
        "棚卸し対象の抽出ルールと画面要件を整理しました。ダッシュボード構成の方針は合意済みです。",
        "権限棚卸し支援ダッシュボード作成は完了しました。権限一覧取り込み、棚卸し画面実装、判定ルール調整まで完了しています。",
    ],
    "proj_10": [
        "入力項目の棚卸しと現行帳票の見直しを進めました。削減候補の整理が完了しています。",
        "画面遷移改善案の検討と入力補助の仕様整理を行いました。次月は実装と部門確認を進める予定です。",
        "月次報告フォームの入力項目整理と画面遷移改善を進めています。入力補助ロジックの実装に着手しており、次回は部門ヒアリング結果を反映する予定です。",
    ],
    "proj_11": [
        "予算執行状況の可視化に向けて要件定義と集計観点の整理を進めました。主要指標は確定しています。",
        "集計ロジックの検証と表示方式の比較を進めました。残タスクはありますが、全体の進捗は計画どおりです。",
        "予算執行状況の集計ロジックとグラフ表示の調整を進めています。予算消化が大きいため、残作業の範囲と追加費用の見込みを確認しています。",
    ],
    "proj_14": [
        "ナレッジ分類ルールの見直しとタグ設計を進めました。利用シナリオ整理まで完了しています。",
        "ナレッジカテゴリとタグ整理を進めています。検索結果の表示順改善に一部遅れがあるため、利用頻度の高い手順から優先して調整しています。",
    ],
    "proj_15": [
        "申請フローの現状整理と改善観点の棚卸しを行いました。差し戻し要因の洗い出しまで完了しています。",
        "社内申請ワークフロー簡素化対応は完了しました。申請手順の棚卸し、入力項目整理、承認前チェック項目の調整まで完了しています。",
    ],
    "proj_16": [
        "検索条件の見直しと利用導線の確認を進めました。改善対象の優先順位付けまで終えています。",
        "業務マニュアル検索改善を進めています。検索条件調整と表示改善を実施し、次回は利用ログを見ながら精度調整を行う予定です。",
    ],
    "proj_18": [
        "テンプレート項目の標準化と記入ガイドの整備を進めました。利用部門向けの説明素材も準備しています。",
    ],
}

PROJECT_COMPLETION_REPORTS = {
    "proj_04": "全タスクの完了を確認しました。入力補助候補の整備とフォーム改修が完了しているため、部門管理者による完了認定をお願いします。",
    "proj_08": "全タスクの完了を確認しました。棚卸し支援ダッシュボードの実装と確認作業が完了しているため、完了認定をお願いします。",
    "proj_15": "全タスクの完了を確認しました。申請フロー簡素化対応の実装と最終確認が完了したため、部門管理者による完了認定をお願いします。",
    "proj_18": "全タスクの完了を確認しました。テンプレート整備と関連導線の作業が完了しているため、部門管理者による完了認定をお願いします。",
}


PROJECT_DRAFT_DATE_RULES = {
    "draft_recent_a": {"created": -5, "updated": -1},
    "draft_recent_b": {"created": -7, "updated": -3},
    "draft_recent_c": {"created": -8, "updated": -4},
    "draft_recent_d": {"created": -9, "updated": -5},
    "draft_recent_e": {"created": -6, "updated": -1},
}

PROJECT_DATE_RULES = {
    "pending_waiting": {"created": -6, "updated": -2, "approved": None, "completed": None, "rejected": None},
    "pending_recent": {"created": -12, "updated": -2, "approved": None, "completed": None, "rejected": None},
    "hq_pending_normal": {"created": -6, "updated": -2, "approved": None, "completed": None, "rejected": None},
    "hq_pending_recent": {"created": -4, "updated": -1, "approved": None, "completed": None, "rejected": None},
    "progress_normal": {"created": -20, "updated": -1, "approved": -2, "completed": None, "rejected": None},
    "progress_delayed": {"created": -25, "updated": -1, "approved": -2, "completed": None, "rejected": None},
    "progress_due_soon": {"created": -16, "updated": 0, "approved": -2, "completed": None, "rejected": None},
    "progress_budget_over": {"created": -22, "updated": -1, "approved": -2, "completed": None, "rejected": None},
    "completed_old": {"created": -35, "updated": -2, "approved": -8, "completed": -1, "rejected": None},
    "completed_recent": {"created": -24, "updated": -1, "approved": -8, "completed": -1, "rejected": None},
    "rejected_recent": {"created": -11, "updated": -1, "approved": None, "completed": None, "rejected": -1},
    "pending_watanabe_recent": {"created": -3, "updated": -1, "approved": None, "completed": None, "rejected": None},
    "pending_ito_recent": {"created": -1, "updated": -1, "approved": None, "completed": None, "rejected": None},
    "progress_watanabe_attention": {"created": -18, "updated": 0, "approved": -2, "completed": None, "rejected": None},
    "completed_watanabe_recent": {"created": -24, "updated": -1, "approved": -8, "completed": -1, "rejected": None},
}

MONTHLY_REPORT_DATE_RULES = {
    "report_recent": -1,
    "report_today": 0,
    "report_mid": -3,
    "report_old": -7,
    "report_completed": -1,
    "report_completed_old": -2,
}

PLANNED_DATE_RULES = {
    "pending_start_normal": {"start": 10, "end": 51},
    "pending_start_soon": {"start": 9, "end": 77},
    "pending_start_late": {"start": 15, "end": 92},
    "progress_start_old": {"start": -7, "end": 46},
    "progress_start_mid": {"start": -3, "end": 41},
    "progress_start_recent": {"start": -1, "end": 26},
    "completed_start_old": {"start": -25, "end": -1},
    "completed_start_recent": {"start": -15, "end": -1},
}

TASK_DATE_RULES = {
    "n1": 9,
    "n2": 11,
    "n3": 13,
    "n4": 15,
    "n5": 18,
    "n6": 20,
    "n7": 22,
    "d1": -1,
    "d2": 8,
    "d3": 12,
    "d4": 15,
    "d5": 17,
    "d6": 19,
    "d7": 21,
    "s1": 0,
    "s2": 1,
    "s3": 4,
    "s4": 7,
    "s5": 10,
    "s6": 13,
    "s7": 15,
    "b1": 9,
    "b2": 12,
    "b3": 14,
    "b4": 17,
    "b5": 20,
    "b6": 22,
    "b7": 24,
    "co1": -12,
    "co2": -10,
    "co3": -8,
    "co4": -6,
    "co5": -5,
    "co6": -4,
    "cr1": -7,
    "cr2": -5,
    "cr3": -3,
    "cr4": -1,
    "cr5": -1,
    "cr6": -1,
    "ws1": -5,
    "ws2": 3,
    "ws_delay": -1,
    "w_overdue2": -2,
    "w_today": 0,
    "w_plus2": 2,
    "ws3": 6,
    "ws4": 10,
    "wc1": -10,
    "wc2": -8,
    "wc3": -6,
    "wc4": -4,
    "wc5": -2,
}

BUDGET_LOG_DATE_RULES = {
    "blog_recent": -1,
    "blog_mid": -3,
    "blog_old": -6,
    "blog_older": -9,
}

NOTIFICATION_DATE_RULES = {
    "notif_recent_a": 0,
    "notif_recent_b": -1,
    "notif_mid_a": -2,
    "notif_mid_b": -3,
    "notif_old_a": -4,
}

STATUS_LOG_DATE_RULES = {
    "sl_submit_old": -6,
    "sl_submit_mid": -5,
    "sl_submit_recent": -2,
    "sl_approve_dept_old": -4,
    "sl_approve_dept_recent": -3,
    "sl_approve_hq_old": -3,
    "sl_approve_hq_recent": -2,
    "sl_complete_old": -1,
    "sl_complete_recent": -1,
    "sl_reject_recent": -1,
    "sl_submit_watanabe_hq": -4,
    "sl_submit_watanabe_recent": -3,
    "sl_submit_ito_recent": -1,
    "sl_approve_dept_watanabe_hq": -2,
}


def get_seed_anchor() -> date:
    return datetime.now(JST).date()


def combine_jst_to_utc(target_date: date, hour: int, minute: int) -> datetime:
    jst_dt = datetime.combine(target_date, time(hour=hour, minute=minute), tzinfo=JST)
    return jst_dt.astimezone(timezone.utc)


def resolve_project_draft_datetimes(role: str) -> tuple[datetime, datetime]:
    anchor = get_seed_anchor()
    rule = PROJECT_DRAFT_DATE_RULES[role]
    created = combine_jst_to_utc(anchor + timedelta(days=rule["created"]), 10, 15)
    updated = combine_jst_to_utc(anchor + timedelta(days=rule["updated"]), 19, 10)
    return created, updated


def resolve_project_dates(role: str) -> dict[str, datetime | None]:
    anchor = get_seed_anchor()
    rule = PROJECT_DATE_RULES[role]

    def _dt(offset: int | None, hour: int) -> datetime | None:
        if offset is None:
            return None
        return combine_jst_to_utc(anchor + timedelta(days=offset), hour, 0)

    return {
        "created_at": _dt(rule["created"], 9),
        "updated_at": _dt(rule["updated"], 18),
        "approved_at": _dt(rule["approved"], 14),
        "completed_at": _dt(rule["completed"], 17),
        "final_rejected_at": _dt(rule["rejected"], 16),
    }


def resolve_planned_date(role: str) -> tuple[date, date]:
    anchor = get_seed_anchor()
    rule = PLANNED_DATE_RULES[role]
    return anchor + timedelta(days=rule["start"]), anchor + timedelta(days=rule["end"])


def resolve_task_dates(role: str) -> tuple[date, date]:
    anchor = get_seed_anchor()
    due = anchor + timedelta(days=TASK_DATE_RULES[role])
    start = due - timedelta(days=7)
    return start, due


def resolve_budget_log_dates(role: str) -> tuple[date, datetime]:
    anchor = get_seed_anchor()
    recorded_on = anchor + timedelta(days=BUDGET_LOG_DATE_RULES[role])
    created_at = combine_jst_to_utc(recorded_on, 20, 0)
    return recorded_on, created_at


def resolve_monthly_report_updated_at(role: str) -> datetime:
    anchor = get_seed_anchor()
    target = anchor + timedelta(days=MONTHLY_REPORT_DATE_RULES[role])
    return combine_jst_to_utc(target, 17, 30)


def shift_month_start(base_month: date, offset_months: int) -> date:
    month_index = (base_month.year * 12 + (base_month.month - 1)) + offset_months
    year = month_index // 12
    month = (month_index % 12) + 1
    return date(year, month, 1)


def resolve_monthly_report_submitted_at(report_month: date, sequence_index: int) -> datetime:
    submit_day = 24 + min(sequence_index, 4)
    submit_hour = 17 + (sequence_index % 2)
    submit_minute = 20 if sequence_index % 2 == 0 else 45
    return combine_jst_to_utc(date(report_month.year, report_month.month, submit_day), submit_hour, submit_minute)


def clamp_to_not_future(target: datetime) -> datetime:
    now = utc_now()
    if target > now:
        return now
    return target


def resolve_notification_created_at(role: str) -> datetime:
    anchor = get_seed_anchor()
    target = anchor + timedelta(days=NOTIFICATION_DATE_RULES[role])
    return combine_jst_to_utc(target, 12, 0)


def resolve_status_log_acted_at(role: str) -> datetime:
    anchor = get_seed_anchor()
    target = anchor + timedelta(days=STATUS_LOG_DATE_RULES[role])
    return combine_jst_to_utc(target, 15, 30)


def reset_all_data() -> None:
    print("既存データ削除を開始します...")
    db.session.query(ProjectStatusLog).delete()
    db.session.query(ProjectReport).delete()
    db.session.query(Notification).delete()
    db.session.query(BudgetActualLog).delete()
    db.session.query(Task).delete()
    db.session.query(Project).delete()
    db.session.query(ProjectDraft).delete()
    db.session.query(DepartmentMembership).delete()
    db.session.query(DepartmentMember).delete()
    db.session.query(User).delete()
    db.session.query(DepartmentYearlyBudget).delete()
    db.session.query(Department).delete()
    db.session.commit()
    print("既存データ削除が完了しました。")


def create_departments() -> dict[str, Department]:
    departments_by_key: dict[str, Department] = {}
    for item in DEPARTMENTS:
        dept = Department(name=item["name"])
        db.session.add(dept)
        departments_by_key[item["key"]] = dept
    db.session.flush()
    print(f"departments: {len(departments_by_key)}件作成")
    return departments_by_key


def create_department_yearly_budgets(departments_by_key: dict[str, Department]) -> list[DepartmentYearlyBudget]:
    rows: list[DepartmentYearlyBudget] = []
    for item in YEARLY_BUDGETS_2026:
        row = DepartmentYearlyBudget(
            department_id=departments_by_key[item["department_key"]].id,
            fiscal_year=item["fiscal_year"],
            annual_budget_amount=Decimal(str(item["annual_budget_amount"])),
        )
        db.session.add(row)
        rows.append(row)
    db.session.flush()
    print(f"department_yearly_budgets: {len(rows)}件作成")
    return rows


def create_users(departments_by_key: dict[str, Department]) -> dict[str, User]:
    users_by_key: dict[str, User] = {}
    for item in USERS:
        dept = departments_by_key[item["department_key"]] if item["department_key"] else None
        user = User(
            login_id=item["login_id"],
            password_hash=generate_password_hash("password123"),
            display_name=item["display_name"],
            role=item["role"],
            department_id=dept.id if dept else None,
            is_active=True,
        )
        db.session.add(user)
        users_by_key[item["key"]] = user
    db.session.flush()
    print(f"users: {len(users_by_key)}件作成")
    return users_by_key


def create_department_members(users_by_key: dict[str, User]) -> dict[str, DepartmentMember]:
    members_by_name: dict[str, DepartmentMember] = {}
    for item in USERS:
        if item["role"] == "hq":
            continue

        user = users_by_key[item["key"]]
        member = DepartmentMember(
            user_id=user.id,
            display_name=user.display_name,
            email=None,
            can_assign_task=item["role"] == "applicant",
            is_active=True,
        )
        db.session.add(member)
        members_by_name[member.display_name] = member
    db.session.flush()
    print(f"department_members: {len(members_by_name)}件作成")
    return members_by_name


def create_department_memberships(
    users_by_key: dict[str, User],
    members_by_name: dict[str, DepartmentMember],
    departments_by_key: dict[str, Department],
) -> list[DepartmentMembership]:
    rows: list[DepartmentMembership] = []
    for item in USERS:
        if item["role"] == "hq":
            continue

        user = users_by_key[item["key"]]
        member = members_by_name[user.display_name]
        row = DepartmentMembership(
            member_id=member.id,
            department_id=departments_by_key[item["department_key"]].id,
            is_primary=True,
            role_label="manager" if item["role"] == "manager" else "member",
            joined_on=None,
            left_on=None,
        )
        db.session.add(row)
        rows.append(row)
    db.session.flush()
    print(f"department_memberships: {len(rows)}件作成")
    return rows


def create_project_drafts(users_by_key: dict[str, User], departments_by_key: dict[str, Department]) -> list[ProjectDraft]:
    rows: list[ProjectDraft] = []
    for item in PROJECT_DRAFTS:
        created_at, updated_at = resolve_project_draft_datetimes(item["date_role"])
        row = ProjectDraft(
            user_id=users_by_key[item["user_key"]].id,
            title=item["title"],
            purpose=item["purpose"],
            department_id=departments_by_key[item["department_key"]].id,
            estimated_person_months=Decimal(item["estimated_person_months"]) if item["estimated_person_months"] else None,
            estimated_budget_amount=Decimal(item["estimated_budget_amount"]) if item["estimated_budget_amount"] else None,
            created_at=created_at,
            updated_at=updated_at,
        )
        db.session.add(row)
        rows.append(row)
    db.session.flush()
    print(f"project_drafts: {len(rows)}件作成")
    return rows


def create_projects(users_by_key: dict[str, User], departments_by_key: dict[str, Department]) -> dict[str, Project]:
    projects_by_key: dict[str, Project] = {}
    for item in PROJECTS:
        applicant = users_by_key[item["applicant_key"]]
        project_dates = resolve_project_dates(item["date_role"])
        planned_start_date, planned_end_date = resolve_planned_date(item["planned_role"])
        monthly_report_comment = PROJECT_MONTHLY_REPORTS.get(item["key"])
        monthly_report_role = PROJECT_MONTHLY_REPORT_ROLES.get(item["key"])
        monthly_report_updated_at = (
            resolve_monthly_report_updated_at(monthly_report_role)
            if monthly_report_comment and monthly_report_role
            else None
        )
        approved_budget = Decimal(item["budget"]) if item["status"] in {"in_progress", "completed"} else None
        rejection_comment = "現行運用との差分整理と移行対象範囲の記載が不足しています。" if item["status"] == "rejected" else None

        project = Project(
            project_code=item["project_code"],
            title=item["title"],
            purpose=PROJECT_PURPOSE[item["key"]],
            summary=PROJECT_SUMMARIES[item["key"]],
            estimated_person_months=Decimal(item["pm"]),
            estimated_budget_amount=Decimal(item["budget"]),
            approved_budget_amount=approved_budget,
            applicant_id=applicant.id,
            department_id=applicant.department_id,
            status=item["status"],
            approval_stage=item["approval_stage"],
            rejection_comment=rejection_comment,
            planned_start_date=planned_start_date,
            planned_end_date=planned_end_date,
            monthly_report_comment=monthly_report_comment,
            monthly_report_updated_at=monthly_report_updated_at,
            final_rejected_at=project_dates["final_rejected_at"],
            approved_at=project_dates["approved_at"],
            completed_at=project_dates["completed_at"],
            created_at=project_dates["created_at"],
            updated_at=project_dates["updated_at"],
        )
        db.session.add(project)
        projects_by_key[item["key"]] = project
    db.session.flush()
    print(f"projects: {len(projects_by_key)}件作成")
    return projects_by_key


def create_tasks(projects_by_key: dict[str, Project], members_by_name: dict[str, DepartmentMember]) -> list[Task]:
    task_specs = {
        "proj_03": [
            ("要件整理ミーティング", "佐藤 美咲", "in_progress", 55, "n1"),
            ("検索条件UI設計", "佐藤 美咲", "in_progress", 60, "n2"),
            ("検索API実装", "佐藤 美咲", "in_progress", 40, "n3"),
            ("インデックス最適化", "佐藤 美咲", "not_started", 0, "n4"),
            ("回帰テストケース作成", "田中 拓海", "in_progress", 35, "n5"),
            ("利用部門レビュー", "田中 拓海", "not_started", 0, "n6"),
            ("運用手順反映", "佐藤 美咲", "not_started", 0, "n7"),
        ],
        "proj_07": [
            ("対象サーバ整理", "鈴木 孝介", "in_progress", 55, "d1"),
            ("バックアップジョブ見直し", "鈴木 孝介", "in_progress", 45, "d2"),
            ("監視閾値調整", "高橋 彩乃", "not_started", 0, "d3"),
            ("通知先メンテ", "高橋 彩乃", "in_progress", 35, "d4"),
            ("手順書更新", "鈴木 孝介", "not_started", 0, "d5"),
            ("定例報告資料作成", "鈴木 孝介", "not_started", 0, "d6"),
            ("本番適用計画作成", "高橋 彩乃", "not_started", 0, "d7"),
        ],
        "proj_10": [
            ("入力項目棚卸し", "渡辺 優菜", "done", 100, "s1"),
            ("画面遷移改善案作成", "森田 葵", "in_progress", 65, "s2"),
            ("入力補助ロジック実装", "藤本 健", "in_progress", 55, "s3"),
            ("月次帳票テンプレート調整", "伊藤 良太", "in_progress", 45, "s4"),
            ("部門ヒアリング対応", "渡辺 優菜", "in_progress", 35, "w_today"),
            ("運用説明資料作成", "伊藤 良太", "not_started", 0, "s6"),
            ("リリース計画確認", "森田 葵", "in_progress", 20, "s7"),
        ],
        "proj_11": [
            ("要件定義レビュー", "伊藤 良太", "in_progress", 70, "b1"),
            ("集計ロジック検証", "伊藤 良太", "in_progress", 68, "b2"),
            ("グラフ表示調整", "森田 葵", "in_progress", 62, "b3"),
            ("CSV出力改善", "藤本 健", "in_progress", 58, "b4"),
            ("予算差異分析観点整理", "伊藤 良太", "in_progress", 55, "b5"),
            ("承認者向け説明準備", "伊藤 良太", "in_progress", 50, "b6"),
            ("受入テスト調整", "伊藤 良太", "not_started", 0, "b7"),
        ],
        "proj_04": [
            ("入力補助候補抽出", "田中 拓海", "done", 100, "co1"),
            ("フォーム文言改修", "田中 拓海", "done", 100, "co2"),
            ("簡易バリデーション追加", "佐藤 美咲", "done", 100, "co3"),
            ("UI確認テスト", "佐藤 美咲", "done", 100, "co4"),
            ("操作説明更新", "田中 拓海", "done", 100, "co5"),
            ("完了報告", "田中 拓海", "done", 100, "co6"),
        ],
        "proj_08": [
            ("権限一覧取り込み", "高橋 彩乃", "done", 100, "cr1"),
            ("棚卸し画面実装", "高橋 彩乃", "done", 100, "cr2"),
            ("判定ルール調整", "鈴木 孝介", "done", 100, "cr3"),
            ("操作手順確認", "高橋 彩乃", "done", 100, "cr4"),
            ("利用部門確認", "鈴木 孝介", "done", 100, "cr5"),
            ("完了報告", "高橋 彩乃", "done", 100, "cr6"),
        ],
        "proj_14": [
            ("ナレッジ分類ルール整理", "渡辺 優菜", "done", 100, "ws1"),
            ("検索結果表示順の調整", "森田 葵", "in_progress", 60, "ws2"),
            ("タグ検索条件の実装", "渡辺 優菜", "in_progress", 45, "ws_delay"),
            ("検索画面UI調整", "藤本 健", "in_progress", 35, "ws3"),
            ("利用シナリオ確認", "伊藤 良太", "in_progress", 30, "w_plus2"),
        ],
        "proj_15": [
            ("申請手順の棚卸し", "渡辺 優菜", "done", 100, "wc1"),
            ("入力項目の整理", "渡辺 優菜", "done", 100, "wc2"),
            ("承認前チェック項目調整", "藤本 健", "done", 100, "wc3"),
            ("完了報告導線の確認", "渡辺 優菜", "done", 100, "wc4"),
            ("操作説明の更新", "渡辺 優菜", "done", 100, "wc5"),
        ],
        "proj_16": [
            ("検索条件最適化", "伊藤 良太", "in_progress", 72, "n3"),
            ("検索結果UI改善", "森田 葵", "in_progress", 68, "n4"),
            ("カテゴリ導線見直し", "藤本 健", "in_progress", 62, "n5"),
            ("利用ログ分析", "伊藤 良太", "in_progress", 58, "n6"),
            ("運用ルール整理", "渡辺 優菜", "not_started", 0, "n7"),
        ],
        "proj_18": [
            ("テンプレート項目定義", "森田 葵", "done", 100, "s1"),
            ("記入ガイド整備", "森田 葵", "done", 100, "s2"),
            ("申請前チェック導線追加", "藤本 健", "done", 100, "s3"),
            ("完了報告ドラフト作成", "森田 葵", "done", 100, "s4"),
        ],
    }

    rows: list[Task] = []
    for project_key, specs in task_specs.items():
        project = projects_by_key[project_key]
        for title, assignee_name, status, progress_rate, task_role in specs:
            member = members_by_name.get(assignee_name)
            if member is None:
                raise ValueError(f"DepartmentMember が見つかりません: {assignee_name}")
            start_date, due_date = resolve_task_dates(task_role)
            row = Task(
                project_id=project.id,
                title=title,
                assignee_member_id=member.id,
                assignee_name=assignee_name,
                status=status,
                progress_rate=progress_rate,
                start_date=start_date,
                due_date=due_date,
            )
            db.session.add(row)
            rows.append(row)
    db.session.flush()
    print(f"tasks: {len(rows)}件作成")
    return rows


def create_budget_actual_logs(projects_by_key: dict[str, Project]) -> list[BudgetActualLog]:
    budget_specs = {
        "proj_03": [(320000, "初期設計費", "blog_older"), (370000, "API実装費", "blog_old"), (350000, "テスト準備費", "blog_mid"), (352000, "追加調整費", "blog_recent")],
        "proj_07": [(0, "予備ログ", "blog_older"), (510000, "監視設定費", "blog_old"), (430000, "運用改善費", "blog_mid"), (490000, "資料整備費", "blog_mid"), (479000, "調整対応費", "blog_recent")],
        "proj_10": [(220000, "要件整理費", "blog_older"), (240000, "UI調整費", "blog_old"), (210000, "機能実装費", "blog_mid"), (230000, "導入準備費", "blog_recent")],
        "proj_11": [(700000, "要件定義費", "blog_older"), (680000, "集計処理開発費", "blog_old"), (620000, "可視化機能実装費", "blog_mid"), (520000, "テスト・調整費", "blog_mid"), (480000, "追加改修費", "blog_recent")],
        "proj_04": [(380000, "調査費", "blog_old"), (420000, "実装費", "blog_mid"), (416000, "最終調整費", "blog_recent")],
        "proj_08": [(590000, "設計費", "blog_old"), (640000, "開発費", "blog_mid"), (702000, "検証費", "blog_recent")],
        "proj_14": [
            (340000, "要件整理費", "blog_older"),
            (360000, "検索条件調整費", "blog_old"),
            (300000, "タグ検索実装費", "blog_mid"),
            (300000, "検索導線改善費", "blog_recent"),
        ],
        "proj_15": [
            (220000, "設計費", "blog_older"),
            (300000, "実装費", "blog_old"),
            (200000, "テスト費", "blog_mid"),
            (180000, "操作説明整備費", "blog_recent"),
        ],
        "proj_16": [
            (560000, "検索条件調整費", "blog_older"),
            (530000, "表示改善実装費", "blog_old"),
            (520000, "導線改善実装費", "blog_mid"),
            (590000, "検証・調整費", "blog_recent"),
        ],
        "proj_18": [
            (220000, "テンプレート設計費", "blog_older"),
            (240000, "導線実装費", "blog_mid"),
            (240000, "最終調整費", "blog_recent"),
        ],
    }

    rows: list[BudgetActualLog] = []
    for project_key, specs in budget_specs.items():
        project = projects_by_key[project_key]
        for amount, memo, role in specs:
            recorded_on, created_at = resolve_budget_log_dates(role)
            row = BudgetActualLog(
                project_id=project.id,
                amount=Decimal(str(amount)),
                memo=memo,
                recorded_on=recorded_on,
                created_at=created_at,
            )
            db.session.add(row)
            rows.append(row)
    db.session.flush()
    print(f"budget_actual_logs: {len(rows)}件作成")
    return rows


def create_project_reports(projects_by_key: dict[str, Project]) -> list[ProjectReport]:
    rows: list[ProjectReport] = []
    for project_key, project in projects_by_key.items():
        tasks = list(project.tasks or [])
        if project.status not in {"in_progress", "completed"} or not tasks:
            continue

        monthly_comments = PROJECT_REPORT_MONTHLY_HISTORY.get(project_key, [])
        if monthly_comments:
            latest_monthly_at = clamp_to_not_future(project.monthly_report_updated_at or project.updated_at or utc_now())
            current_month = date(get_seed_anchor().year, get_seed_anchor().month, 1)
            latest_month = date(
                latest_monthly_at.astimezone(JST).year,
                latest_monthly_at.astimezone(JST).month,
                1,
            )
            latest_month = min(latest_month, current_month)
            monthly_reports: list[ProjectReport] = []
            for idx, comment in enumerate(reversed(monthly_comments)):
                report_month = shift_month_start(latest_month, -idx)
                if idx == 0:
                    submitted_at = project.monthly_report_updated_at or project.updated_at or utc_now()
                else:
                    submitted_at = resolve_monthly_report_submitted_at(report_month, idx)
                submitted_at = clamp_to_not_future(submitted_at)
                report = ProjectReport(
                    project_id=project.id,
                    reporter_id=project.applicant_id,
                    report_type="monthly",
                    report_month=report_month,
                    comment=comment,
                    submitted_at=submitted_at,
                )
                db.session.add(report)
                rows.append(report)
                monthly_reports.append(report)

            latest_report = max(monthly_reports, key=lambda item: item.submitted_at)
            project.monthly_report_comment = latest_report.comment
            project.monthly_report_updated_at = latest_report.submitted_at

        all_tasks_done = bool(tasks) and all(task.status == "done" for task in tasks)
        if all_tasks_done and project.status in {"in_progress", "completed"}:
            completion_submitted_at = project.completed_at or project.updated_at
            if completion_submitted_at is None:
                completion_due_date = max((task.due_date for task in tasks if task.due_date), default=None)
                if completion_due_date is None:
                    completion_submitted_at = utc_now()
                else:
                    completion_submitted_at = combine_jst_to_utc(completion_due_date, 17, 30)
            completion_submitted_at = clamp_to_not_future(completion_submitted_at)
            report = ProjectReport(
                project_id=project.id,
                reporter_id=project.applicant_id,
                report_type="completion",
                report_month=None,
                comment=PROJECT_COMPLETION_REPORTS.get(
                    project_key,
                    "全タスクの完了を確認しました。部門管理者による完了認定をお願いします。",
                ),
                submitted_at=completion_submitted_at,
            )
            db.session.add(report)
            rows.append(report)

    db.session.flush()
    print(f"project_reports: {len(rows)}件作成")
    return rows


def set_project_last_progress_updates(projects_by_key: dict[str, Project]) -> None:
    """開発中・完了済み案件に、最終進捗更新日時・更新者を設定する。"""
    for project in projects_by_key.values():
        if project.status not in {"in_progress", "completed"}:
            project.last_progress_updated_at = None
            project.last_progress_updated_by_id = None
            continue

        candidates: list[dict[str, datetime | int | None]] = []

        for report in project.project_reports:
            if report.submitted_at is not None:
                candidates.append(
                    {
                        "updated_at": report.submitted_at,
                        "updated_by_id": report.reporter_id,
                    }
                )

        for log in project.budget_actual_logs:
            if log.created_at is not None:
                candidates.append(
                    {
                        "updated_at": log.created_at,
                        "updated_by_id": project.applicant_id,
                    }
                )

        for task in project.tasks:
            if task.updated_at is not None:
                candidates.append(
                    {
                        "updated_at": task.updated_at,
                        "updated_by_id": project.applicant_id,
                    }
                )

        if project.updated_at is not None:
            candidates.append(
                {
                    "updated_at": project.updated_at,
                    "updated_by_id": project.applicant_id,
                }
            )

        latest = max(candidates, key=lambda item: item["updated_at"], default=None)

        if latest is None or latest["updated_at"] is None:
            project.last_progress_updated_at = None
            project.last_progress_updated_by_id = None
        else:
            project.last_progress_updated_at = clamp_to_not_future(latest["updated_at"])
            project.last_progress_updated_by_id = latest["updated_by_id"]

    db.session.flush()
    print("projects.last_progress_updated_at / by_id を設定")


def create_notifications(users_by_key: dict[str, User], projects_by_key: dict[str, Project]) -> list[Notification]:
    rows: list[Notification] = []
    row = Notification(
        user_id=users_by_key["kobayashi"].id,
        project_id=projects_by_key["proj_18"].id,
        type="completed",
        message="全タスクが完了しました。案件完了の確認を行ってください。",
        is_read=False,
        created_at=resolve_notification_created_at("notif_recent_b"),
    )
    db.session.add(row)
    rows.append(row)
    db.session.flush()
    print(f"notifications: {len(rows)}件作成")
    return rows


def create_project_status_logs(users_by_key: dict[str, User], projects_by_key: dict[str, Project]) -> list[ProjectStatusLog]:
    rows: list[ProjectStatusLog] = []

    # submit 12件
    for i, project in enumerate(PROJECTS[:12]):
        role = (
            "sl_submit_ito_recent"
            if project["key"] == "proj_09"
            else "sl_submit_mid"
            if project["key"] in {"proj_10", "proj_11"}
            else "sl_submit_old"
            if i < 4
            else "sl_submit_mid"
            if i < 8
            else "sl_submit_recent"
        )
        row = ProjectStatusLog(
            project_id=projects_by_key[project["key"]].id,
            actor_id=users_by_key[project["applicant_key"]].id,
            from_status=None,
            to_status="department_pending",
            action="submit",
            comment=None,
            acted_at=resolve_status_log_acted_at(role),
        )
        db.session.add(row)
        rows.append(row)

    # hq_pending 2件分の部門承認
    for project_key in ["proj_02", "proj_06"]:
        row = ProjectStatusLog(
            project_id=projects_by_key[project_key].id,
            actor_id=users_by_key["yamamoto"].id if project_key == "proj_02" else users_by_key["nakamura"].id,
            from_status="department_pending",
            to_status="hq_pending",
            action="approve_department",
            comment=None,
            acted_at=resolve_status_log_acted_at("sl_approve_dept_recent"),
        )
        db.session.add(row)
        rows.append(row)

    # in_progress 4件分: 部門承認 + 本部承認
    for project_key in ["proj_03", "proj_07", "proj_10", "proj_11"]:
        manager_key = "yamamoto" if project_key == "proj_03" else "nakamura" if project_key == "proj_07" else "kobayashi"
        row_dept = ProjectStatusLog(
            project_id=projects_by_key[project_key].id,
            actor_id=users_by_key[manager_key].id,
            from_status="department_pending",
            to_status="hq_pending",
            action="approve_department",
            comment=None,
            acted_at=resolve_status_log_acted_at("sl_approve_dept_old"),
        )
        row_hq = ProjectStatusLog(
            project_id=projects_by_key[project_key].id,
            actor_id=users_by_key["tajiri"].id,
            from_status="hq_pending",
            to_status="in_progress",
            action="approve_hq",
            comment=None,
            acted_at=resolve_status_log_acted_at("sl_approve_hq_recent"),
        )
        db.session.add(row_dept)
        db.session.add(row_hq)
        rows.extend([row_dept, row_hq])

    # completed 2件分: 部門承認 + 本部承認 + 完了
    for project_key, manager_key in [("proj_04", "yamamoto"), ("proj_08", "nakamura")]:
        row_dept = ProjectStatusLog(
            project_id=projects_by_key[project_key].id,
            actor_id=users_by_key[manager_key].id,
            from_status="department_pending",
            to_status="hq_pending",
            action="approve_department",
            comment=None,
            acted_at=resolve_status_log_acted_at("sl_approve_dept_old"),
        )
        row_hq = ProjectStatusLog(
            project_id=projects_by_key[project_key].id,
            actor_id=users_by_key["tajiri"].id,
            from_status="hq_pending",
            to_status="in_progress",
            action="approve_hq",
            comment=None,
            acted_at=resolve_status_log_acted_at("sl_approve_hq_old"),
        )
        db.session.add(row_dept)
        db.session.add(row_hq)
        rows.extend([row_dept, row_hq])

    # completed 2件分: 完了
    for project_key, actor_key, role in [("proj_04", "tanaka", "sl_complete_old"), ("proj_08", "takahashi", "sl_complete_recent")]:
        row = ProjectStatusLog(
            project_id=projects_by_key[project_key].id,
            actor_id=users_by_key[actor_key].id,
            from_status="in_progress",
            to_status="completed",
            action="complete",
            comment=None,
            acted_at=resolve_status_log_acted_at(role),
        )
        db.session.add(row)
        rows.append(row)

    # rejected 1件分
    row_reject = ProjectStatusLog(
        project_id=projects_by_key["proj_12"].id,
        actor_id=users_by_key["kobayashi"].id,
        from_status="department_pending",
        to_status="rejected",
        action="reject_department",
        comment="現行運用との差分整理と移行対象範囲の記載が不足しています。",
        acted_at=resolve_status_log_acted_at("sl_reject_recent"),
    )
    db.session.add(row_reject)
    rows.append(row_reject)

    # 渡辺 優菜の追加デモ案件: 申請中1件
    row_submit_13 = ProjectStatusLog(
        project_id=projects_by_key["proj_13"].id,
        actor_id=users_by_key["watanabe"].id,
        from_status=None,
        to_status="department_pending",
        action="submit",
        comment=None,
        acted_at=resolve_status_log_acted_at("sl_submit_watanabe_recent"),
    )
    row_dept_13 = ProjectStatusLog(
        project_id=projects_by_key["proj_13"].id,
        actor_id=users_by_key["kobayashi"].id,
        from_status="department_pending",
        to_status="hq_pending",
        action="approve_department",
        comment=None,
        acted_at=resolve_status_log_acted_at("sl_approve_dept_watanabe_hq"),
    )
    db.session.add(row_submit_13)
    db.session.add(row_dept_13)
    rows.extend([row_submit_13, row_dept_13])

    # 渡辺 優菜の追加デモ案件: 開発中1件（申請 → 部門承認 → 本部承認）
    row_submit_14 = ProjectStatusLog(
        project_id=projects_by_key["proj_14"].id,
        actor_id=users_by_key["watanabe"].id,
        from_status=None,
        to_status="department_pending",
        action="submit",
        comment=None,
        acted_at=resolve_status_log_acted_at("sl_submit_mid"),
    )
    row_dept_14 = ProjectStatusLog(
        project_id=projects_by_key["proj_14"].id,
        actor_id=users_by_key["kobayashi"].id,
        from_status="department_pending",
        to_status="hq_pending",
        action="approve_department",
        comment=None,
        acted_at=resolve_status_log_acted_at("sl_approve_dept_old"),
    )
    row_hq_14 = ProjectStatusLog(
        project_id=projects_by_key["proj_14"].id,
        actor_id=users_by_key["tajiri"].id,
        from_status="hq_pending",
        to_status="in_progress",
        action="approve_hq",
        comment=None,
        acted_at=resolve_status_log_acted_at("sl_approve_hq_recent"),
    )
    db.session.add(row_submit_14)
    db.session.add(row_dept_14)
    db.session.add(row_hq_14)
    rows.extend([row_submit_14, row_dept_14, row_hq_14])

    # 渡辺 優菜の追加デモ案件: 完了済み1件（申請 → 部門承認 → 本部承認 → 完了）
    row_submit_15 = ProjectStatusLog(
        project_id=projects_by_key["proj_15"].id,
        actor_id=users_by_key["watanabe"].id,
        from_status=None,
        to_status="department_pending",
        action="submit",
        comment=None,
        acted_at=resolve_status_log_acted_at("sl_submit_old"),
    )
    row_dept_15 = ProjectStatusLog(
        project_id=projects_by_key["proj_15"].id,
        actor_id=users_by_key["kobayashi"].id,
        from_status="department_pending",
        to_status="hq_pending",
        action="approve_department",
        comment=None,
        acted_at=resolve_status_log_acted_at("sl_approve_dept_old"),
    )
    row_hq_15 = ProjectStatusLog(
        project_id=projects_by_key["proj_15"].id,
        actor_id=users_by_key["tajiri"].id,
        from_status="hq_pending",
        to_status="in_progress",
        action="approve_hq",
        comment=None,
        acted_at=resolve_status_log_acted_at("sl_approve_hq_old"),
    )
    row_complete_15 = ProjectStatusLog(
        project_id=projects_by_key["proj_15"].id,
        actor_id=users_by_key["watanabe"].id,
        from_status="in_progress",
        to_status="completed",
        action="complete",
        comment=None,
        acted_at=resolve_status_log_acted_at("sl_complete_old"),
    )
    db.session.add(row_submit_15)
    db.session.add(row_dept_15)
    db.session.add(row_hq_15)
    db.session.add(row_complete_15)
    rows.extend([row_submit_15, row_dept_15, row_hq_15, row_complete_15])

    row_submit_16 = ProjectStatusLog(
        project_id=projects_by_key["proj_16"].id,
        actor_id=users_by_key["watanabe"].id,
        from_status=None,
        to_status="department_pending",
        action="submit",
        comment=None,
        acted_at=resolve_status_log_acted_at("sl_submit_mid"),
    )
    row_dept_16 = ProjectStatusLog(
        project_id=projects_by_key["proj_16"].id,
        actor_id=users_by_key["kobayashi"].id,
        from_status="department_pending",
        to_status="hq_pending",
        action="approve_department",
        comment=None,
        acted_at=resolve_status_log_acted_at("sl_approve_dept_old"),
    )
    row_hq_16 = ProjectStatusLog(
        project_id=projects_by_key["proj_16"].id,
        actor_id=users_by_key["tajiri"].id,
        from_status="hq_pending",
        to_status="in_progress",
        action="approve_hq",
        comment=None,
        acted_at=resolve_status_log_acted_at("sl_approve_hq_recent"),
    )
    db.session.add(row_submit_16)
    db.session.add(row_dept_16)
    db.session.add(row_hq_16)
    rows.extend([row_submit_16, row_dept_16, row_hq_16])

    row_submit_17 = ProjectStatusLog(
        project_id=projects_by_key["proj_17"].id,
        actor_id=users_by_key["watanabe"].id,
        from_status=None,
        to_status="department_pending",
        action="submit",
        comment=None,
        acted_at=resolve_status_log_acted_at("sl_submit_watanabe_recent"),
    )
    db.session.add(row_submit_17)
    rows.append(row_submit_17)

    row_submit_18 = ProjectStatusLog(
        project_id=projects_by_key["proj_18"].id,
        actor_id=users_by_key["morita"].id,
        from_status=None,
        to_status="department_pending",
        action="submit",
        comment=None,
        acted_at=resolve_status_log_acted_at("sl_submit_mid"),
    )
    row_dept_18 = ProjectStatusLog(
        project_id=projects_by_key["proj_18"].id,
        actor_id=users_by_key["kobayashi"].id,
        from_status="department_pending",
        to_status="hq_pending",
        action="approve_department",
        comment=None,
        acted_at=resolve_status_log_acted_at("sl_approve_dept_old"),
    )
    row_hq_18 = ProjectStatusLog(
        project_id=projects_by_key["proj_18"].id,
        actor_id=users_by_key["tajiri"].id,
        from_status="hq_pending",
        to_status="in_progress",
        action="approve_hq",
        comment=None,
        acted_at=resolve_status_log_acted_at("sl_approve_hq_recent"),
    )
    db.session.add(row_submit_18)
    db.session.add(row_dept_18)
    db.session.add(row_hq_18)
    rows.extend([row_submit_18, row_dept_18, row_hq_18])

    db.session.flush()
    print(f"project_status_logs: {len(rows)}件作成")
    return rows


def main() -> None:
    with app.app_context():
        print("seed開始")
        reset_all_data()

        departments_by_key = create_departments()
        create_department_yearly_budgets(departments_by_key)
        users_by_key = create_users(departments_by_key)
        members_by_name = create_department_members(users_by_key)
        create_department_memberships(users_by_key, members_by_name, departments_by_key)
        create_project_drafts(users_by_key, departments_by_key)
        projects_by_key = create_projects(users_by_key, departments_by_key)
        create_tasks(projects_by_key, members_by_name)
        create_budget_actual_logs(projects_by_key)
        create_project_reports(projects_by_key)
        set_project_last_progress_updates(projects_by_key)
        create_notifications(users_by_key, projects_by_key)
        create_project_status_logs(users_by_key, projects_by_key)

        db.session.commit()
        print("seed完了")
        print("投入件数: departments=3, department_yearly_budgets=3, users=12, department_members=11, department_memberships=11, project_drafts=5, projects=18, tasks=59, budget_actual_logs=39, project_reports=26, notifications=1, project_status_logs=45")


if __name__ == "__main__":
    main()
