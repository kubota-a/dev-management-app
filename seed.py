from __future__ import annotations

from datetime import date, datetime, time, timedelta, timezone
from decimal import Decimal
from zoneinfo import ZoneInfo

from werkzeug.security import generate_password_hash

from app import app
from models import (
    BudgetActualLog,
    Department,
    DepartmentYearlyBudget,
    Notification,
    Project,
    ProjectDraft,
    ProjectStatusLog,
    Task,
    User,
    db,
)


# 実行モード: "fixed" または "relative"
SEED_MODE = "fixed"

JST = ZoneInfo("Asia/Tokyo")


DEPARTMENTS = [
    {"key": "sys_dev", "name": "システム開発部"},
    {"key": "infra", "name": "情報基盤部"},
    {"key": "biz_reform", "name": "業務改革推進部"},
]

YEARLY_BUDGETS_2026 = [
    {"department_key": "sys_dev", "fiscal_year": 2026, "annual_budget_amount": 18_000_000},
    {"department_key": "infra", "fiscal_year": 2026, "annual_budget_amount": 15_000_000},
    {"department_key": "biz_reform", "fiscal_year": 2026, "annual_budget_amount": 12_000_000},
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
    {"key": "kobayashi", "login_id": "kobayashi", "display_name": "小林 理絵", "role": "manager", "department_key": "biz_reform"},
    {"key": "tajiri", "login_id": "tajiri", "display_name": "田尻 憲市郎", "role": "hq", "department_key": None},
]

# README/ログイン画面向けおすすめアカウント
# - 申請者（おすすめ）: watanabe / 渡辺 優菜
# - 部門管理者（おすすめ）: yamamoto / 山本 瑞希
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
    {"key": "proj_09", "project_code": "REQ-2026-00009", "title": "Excel進捗管理廃止に向けた統合化PoC", "applicant_key": "ito", "status": "department_pending", "approval_stage": "department_pending", "budget": "3600000", "pm": "3.50", "date_role": "pending_waiting", "planned_role": "pending_start_late"},
    {"key": "proj_10", "project_code": "REQ-2026-00010", "title": "月次報告入力業務の簡素化対応", "applicant_key": "watanabe", "status": "in_progress", "approval_stage": "approved", "budget": "1800000", "pm": "2.30", "date_role": "progress_due_soon", "planned_role": "progress_start_recent"},
    {"key": "proj_11", "project_code": "REQ-2026-00011", "title": "予算執行状況の可視化機能追加", "applicant_key": "ito", "status": "in_progress", "approval_stage": "approved", "budget": "4200000", "pm": "4.00", "date_role": "progress_budget_over", "planned_role": "progress_start_mid"},
    {"key": "proj_12", "project_code": "REQ-2026-00012", "title": "旧申請システム移行準備案件", "applicant_key": "watanabe", "status": "rejected", "approval_stage": "rejected", "budget": "2700000", "pm": "3.00", "date_role": "rejected_recent", "planned_role": "pending_start_normal"},
    {"key": "proj_13", "project_code": "REQ-2026-00013", "title": "業務ナレッジ共有ポータル改善", "applicant_key": "watanabe", "status": "department_pending", "approval_stage": "department_pending", "budget": "1900000", "pm": "2.20", "date_role": "pending_watanabe_recent", "planned_role": "pending_start_normal"},
    {"key": "proj_14", "project_code": "REQ-2026-00014", "title": "月次報告自動生成機能の高度化", "applicant_key": "watanabe", "status": "in_progress", "approval_stage": "approved", "budget": "2600000", "pm": "3.10", "date_role": "progress_watanabe_attention", "planned_role": "progress_start_recent"},
    {"key": "proj_15", "project_code": "REQ-2026-00015", "title": "社内申請ワークフロー簡素化対応", "applicant_key": "watanabe", "status": "completed", "approval_stage": "approved", "budget": "1700000", "pm": "2.00", "date_role": "completed_watanabe_recent", "planned_role": "completed_start_recent"},
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
    "proj_14": "月次報告作成時の転記作業を減らし、報告内容のばらつきと提出遅延を抑制します。",
    "proj_15": "申請内容の確認から承認依頼までの手順を整理し、申請者と承認者双方の確認負荷を軽減します。",
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
    "proj_14": "主な施策：\n・前月データをもとにした報告文案の自動生成\n・入力漏れチェックの追加\n・提出前レビュー導線の改善\n\n期待効果：\n・報告作成時間の短縮\n・入力漏れの削減\n・月初業務の負荷分散",
    "proj_15": "主な施策：\n・申請フォームの入力項目整理\n・承認前チェック項目の見直し\n・完了報告までの導線整備\n\n期待効果：\n・申請作成時間の短縮\n・差し戻し件数の削減\n・完了報告の抜け漏れ防止",
}

PROJECT_MONTHLY_REPORTS = {
    "proj_03": "検索条件UIの設計とAPI実装を進めています。検索条件の保存機能は設計方針が固まり、現在は検索APIの実装とインデックス最適化の検証を行っています。",
    "proj_07": "バックアップジョブ見直しと監視閾値調整を進めています。一部タスクに遅れが出ているため、担当者間で優先度を見直しながら対応しています。",
    "proj_10": "月次報告フォームの入力項目整理と画面遷移改善を進めています。入力補助ロジックの実装に着手しており、次回は部門ヒアリング結果を反映する予定です。",
    "proj_11": "予算執行状況の集計ロジックとグラフ表示の調整を進めています。予算消化が大きいため、残作業の範囲と追加費用の見込みを確認しています。",
    "proj_14": "前月データ参照ロジックの整理が完了し、報告文案生成ルールの作成を進めています。入力漏れチェック実装に一部遅れがあるため、優先的に対応しています。",
    "proj_04": "申請フォーム入力補助機能の導入作業は完了しました。入力補助候補の整備、フォーム文言改修、操作説明更新まで完了しています。",
    "proj_08": "権限棚卸し支援ダッシュボード作成は完了しました。権限一覧取り込み、棚卸し画面実装、判定ルール調整まで完了しています。",
    "proj_15": "社内申請ワークフロー簡素化対応は完了しました。申請手順の棚卸し、入力項目整理、承認前チェック項目の調整まで完了しています。",
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
}


PROJECT_DRAFT_DATE_RULES = {
    "draft_recent_a": {"fixed": {"created": -5, "updated": -1}, "relative": {"created": -5, "updated": -1}},
    "draft_recent_b": {"fixed": {"created": -7, "updated": -3}, "relative": {"created": -7, "updated": -3}},
    "draft_recent_c": {"fixed": {"created": -8, "updated": -4}, "relative": {"created": -8, "updated": -4}},
    "draft_recent_d": {"fixed": {"created": -9, "updated": -5}, "relative": {"created": -9, "updated": -5}},
    "draft_recent_e": {"fixed": {"created": -6, "updated": -2}, "relative": {"created": -6, "updated": -1}},
}

PROJECT_DATE_RULES = {
    "pending_waiting": {"fixed": {"created": -18, "updated": -6, "approved": None, "completed": None, "rejected": None}, "relative": {"created": -18, "updated": -6, "approved": None, "completed": None, "rejected": None}},
    "pending_recent": {"fixed": {"created": -12, "updated": -2, "approved": None, "completed": None, "rejected": None}, "relative": {"created": -12, "updated": -2, "approved": None, "completed": None, "rejected": None}},
    "hq_pending_normal": {"fixed": {"created": -14, "updated": -4, "approved": None, "completed": None, "rejected": None}, "relative": {"created": -14, "updated": -4, "approved": None, "completed": None, "rejected": None}},
    "hq_pending_recent": {"fixed": {"created": -10, "updated": -1, "approved": None, "completed": None, "rejected": None}, "relative": {"created": -10, "updated": -1, "approved": None, "completed": None, "rejected": None}},
    "progress_normal": {"fixed": {"created": -20, "updated": -1, "approved": -2, "completed": None, "rejected": None}, "relative": {"created": -20, "updated": -1, "approved": -2, "completed": None, "rejected": None}},
    "progress_delayed": {"fixed": {"created": -25, "updated": -1, "approved": -2, "completed": None, "rejected": None}, "relative": {"created": -25, "updated": -1, "approved": -2, "completed": None, "rejected": None}},
    "progress_due_soon": {"fixed": {"created": -16, "updated": 0, "approved": -2, "completed": None, "rejected": None}, "relative": {"created": -16, "updated": 0, "approved": -2, "completed": None, "rejected": None}},
    "progress_budget_over": {"fixed": {"created": -22, "updated": -1, "approved": -2, "completed": None, "rejected": None}, "relative": {"created": -22, "updated": -1, "approved": -2, "completed": None, "rejected": None}},
    "completed_old": {"fixed": {"created": -35, "updated": -2, "approved": -8, "completed": -1, "rejected": None}, "relative": {"created": -35, "updated": -2, "approved": -8, "completed": -1, "rejected": None}},
    "completed_recent": {"fixed": {"created": -24, "updated": -1, "approved": -8, "completed": 0, "rejected": None}, "relative": {"created": -24, "updated": -1, "approved": -8, "completed": -1, "rejected": None}},
    "rejected_recent": {"fixed": {"created": -11, "updated": -1, "approved": None, "completed": None, "rejected": -1}, "relative": {"created": -11, "updated": -1, "approved": None, "completed": None, "rejected": -1}},
    "pending_watanabe_recent": {"fixed": {"created": -5, "updated": -1, "approved": None, "completed": None, "rejected": None}, "relative": {"created": -4, "updated": -1, "approved": None, "completed": None, "rejected": None}},
    "progress_watanabe_attention": {"fixed": {"created": -24, "updated": -1, "approved": -2, "completed": None, "rejected": None}, "relative": {"created": -18, "updated": 0, "approved": -2, "completed": None, "rejected": None}},
    "completed_watanabe_recent": {"fixed": {"created": -28, "updated": -1, "approved": -8, "completed": -1, "rejected": None}, "relative": {"created": -24, "updated": -1, "approved": -8, "completed": -1, "rejected": None}},
}

MONTHLY_REPORT_DATE_RULES = {
    "report_recent": {"fixed": -1, "relative": -1},
    "report_today": {"fixed": 0, "relative": 0},
    "report_mid": {"fixed": -3, "relative": -3},
    "report_old": {"fixed": -7, "relative": -7},
    "report_completed": {"fixed": -1, "relative": -1},
    "report_completed_old": {"fixed": -2, "relative": -2},
}

PLANNED_DATE_RULES = {
    "pending_start_normal": {"fixed": {"start": 10, "end": 51}, "relative": {"start": 10, "end": 51}},
    "pending_start_soon": {"fixed": {"start": 9, "end": 77}, "relative": {"start": 9, "end": 77}},
    "pending_start_late": {"fixed": {"start": 15, "end": 92}, "relative": {"start": 15, "end": 92}},
    "progress_start_old": {"fixed": {"start": -7, "end": 46}, "relative": {"start": -7, "end": 46}},
    "progress_start_mid": {"fixed": {"start": -3, "end": 41}, "relative": {"start": -3, "end": 41}},
    "progress_start_recent": {"fixed": {"start": -1, "end": 26}, "relative": {"start": -1, "end": 26}},
    "completed_start_old": {"fixed": {"start": -25, "end": -1}, "relative": {"start": -25, "end": -1}},
    "completed_start_recent": {"fixed": {"start": -15, "end": -1}, "relative": {"start": -15, "end": -1}},
}

TASK_DATE_RULES = {
    "n1": {"fixed": 9, "relative": 9},
    "n2": {"fixed": 11, "relative": 11},
    "n3": {"fixed": 13, "relative": 13},
    "n4": {"fixed": 15, "relative": 15},
    "n5": {"fixed": 18, "relative": 18},
    "n6": {"fixed": 20, "relative": 20},
    "n7": {"fixed": 22, "relative": 22},
    "d1": {"fixed": -1, "relative": -1},
    "d2": {"fixed": 8, "relative": 8},
    "d3": {"fixed": 12, "relative": 12},
    "d4": {"fixed": 15, "relative": 15},
    "d5": {"fixed": 17, "relative": 17},
    "d6": {"fixed": 19, "relative": 19},
    "d7": {"fixed": 21, "relative": 21},
    "s1": {"fixed": 6, "relative": 0},
    "s2": {"fixed": 7, "relative": 1},
    "s3": {"fixed": 10, "relative": 4},
    "s4": {"fixed": 13, "relative": 7},
    "s5": {"fixed": 16, "relative": 10},
    "s6": {"fixed": 19, "relative": 13},
    "s7": {"fixed": 21, "relative": 15},
    "b1": {"fixed": 9, "relative": 9},
    "b2": {"fixed": 12, "relative": 12},
    "b3": {"fixed": 14, "relative": 14},
    "b4": {"fixed": 17, "relative": 17},
    "b5": {"fixed": 20, "relative": 20},
    "b6": {"fixed": 22, "relative": 22},
    "b7": {"fixed": 24, "relative": 24},
    "co1": {"fixed": -12, "relative": -12},
    "co2": {"fixed": -10, "relative": -10},
    "co3": {"fixed": -8, "relative": -8},
    "co4": {"fixed": -6, "relative": -6},
    "co5": {"fixed": -5, "relative": -5},
    "co6": {"fixed": -4, "relative": -4},
    "cr1": {"fixed": -7, "relative": -7},
    "cr2": {"fixed": -5, "relative": -5},
    "cr3": {"fixed": -3, "relative": -3},
    "cr4": {"fixed": -1, "relative": -1},
    "cr5": {"fixed": 0, "relative": -1},
    "cr6": {"fixed": 1, "relative": -1},
    "ws1": {"fixed": -5, "relative": -5},
    "ws2": {"fixed": 7, "relative": 3},
    "ws_delay": {"fixed": -1, "relative": -1},
    "ws3": {"fixed": 10, "relative": 6},
    "ws4": {"fixed": 14, "relative": 10},
    "wc1": {"fixed": -10, "relative": -10},
    "wc2": {"fixed": -8, "relative": -8},
    "wc3": {"fixed": -6, "relative": -6},
    "wc4": {"fixed": -4, "relative": -4},
    "wc5": {"fixed": -2, "relative": -2},
}

BUDGET_LOG_DATE_RULES = {
    "blog_recent": {"fixed": -1, "relative": -1},
    "blog_mid": {"fixed": -3, "relative": -3},
    "blog_old": {"fixed": -6, "relative": -6},
    "blog_older": {"fixed": -9, "relative": -9},
}

NOTIFICATION_DATE_RULES = {
    "notif_recent_a": {"fixed": 0, "relative": 0},
    "notif_recent_b": {"fixed": -1, "relative": -1},
    "notif_mid_a": {"fixed": -2, "relative": -2},
    "notif_mid_b": {"fixed": -3, "relative": -3},
    "notif_old_a": {"fixed": -4, "relative": -4},
}

STATUS_LOG_DATE_RULES = {
    "sl_submit_old": {"fixed": -20, "relative": -20},
    "sl_submit_mid": {"fixed": -12, "relative": -12},
    "sl_submit_recent": {"fixed": -7, "relative": -7},
    "sl_approve_dept_old": {"fixed": -10, "relative": -10},
    "sl_approve_dept_recent": {"fixed": -3, "relative": -3},
    "sl_approve_hq_old": {"fixed": -8, "relative": -8},
    "sl_approve_hq_recent": {"fixed": -2, "relative": -2},
    "sl_complete_old": {"fixed": -1, "relative": -1},
    "sl_complete_recent": {"fixed": 0, "relative": -1},
    "sl_reject_recent": {"fixed": -1, "relative": -1},
}


def get_seed_anchor(mode: str) -> date:
    if mode == "fixed":
        return date(2026, 5, 15)
    return datetime.now(JST).date()


def combine_jst_to_utc(target_date: date, hour: int, minute: int) -> datetime:
    jst_dt = datetime.combine(target_date, time(hour=hour, minute=minute), tzinfo=JST)
    return jst_dt.astimezone(timezone.utc)


def resolve_project_draft_datetimes(mode: str, role: str) -> tuple[datetime, datetime]:
    anchor = get_seed_anchor(mode)
    rule = PROJECT_DRAFT_DATE_RULES[role][mode]
    created = combine_jst_to_utc(anchor + timedelta(days=rule["created"]), 10, 15)
    updated = combine_jst_to_utc(anchor + timedelta(days=rule["updated"]), 19, 10)
    return created, updated


def resolve_project_dates(mode: str, role: str) -> dict[str, datetime | None]:
    anchor = get_seed_anchor(mode)
    rule = PROJECT_DATE_RULES[role][mode]

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


def resolve_planned_date(mode: str, role: str) -> tuple[date, date]:
    anchor = get_seed_anchor(mode)
    rule = PLANNED_DATE_RULES[role][mode]
    return anchor + timedelta(days=rule["start"]), anchor + timedelta(days=rule["end"])


def resolve_task_dates(mode: str, role: str) -> tuple[date, date]:
    anchor = get_seed_anchor(mode)
    due = anchor + timedelta(days=TASK_DATE_RULES[role][mode])
    start = due - timedelta(days=7)
    return start, due


def resolve_budget_log_dates(mode: str, role: str) -> tuple[date, datetime]:
    anchor = get_seed_anchor(mode)
    recorded_on = anchor + timedelta(days=BUDGET_LOG_DATE_RULES[role][mode])
    created_at = combine_jst_to_utc(recorded_on, 20, 0)
    return recorded_on, created_at


def resolve_monthly_report_updated_at(mode: str, role: str) -> datetime:
    anchor = get_seed_anchor(mode)
    target = anchor + timedelta(days=MONTHLY_REPORT_DATE_RULES[role][mode])
    return combine_jst_to_utc(target, 17, 30)


def resolve_notification_created_at(mode: str, role: str) -> datetime:
    anchor = get_seed_anchor(mode)
    target = anchor + timedelta(days=NOTIFICATION_DATE_RULES[role][mode])
    return combine_jst_to_utc(target, 12, 0)


def resolve_status_log_acted_at(mode: str, role: str) -> datetime:
    anchor = get_seed_anchor(mode)
    target = anchor + timedelta(days=STATUS_LOG_DATE_RULES[role][mode])
    return combine_jst_to_utc(target, 15, 30)


def reset_all_data() -> None:
    print("既存データ削除を開始します...")
    db.session.query(ProjectStatusLog).delete()
    db.session.query(Notification).delete()
    db.session.query(BudgetActualLog).delete()
    db.session.query(Task).delete()
    db.session.query(Project).delete()
    db.session.query(ProjectDraft).delete()
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


def create_project_drafts(mode: str, users_by_key: dict[str, User], departments_by_key: dict[str, Department]) -> list[ProjectDraft]:
    rows: list[ProjectDraft] = []
    for item in PROJECT_DRAFTS:
        created_at, updated_at = resolve_project_draft_datetimes(mode, item["date_role"])
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


def create_projects(mode: str, users_by_key: dict[str, User], departments_by_key: dict[str, Department]) -> dict[str, Project]:
    projects_by_key: dict[str, Project] = {}
    for item in PROJECTS:
        applicant = users_by_key[item["applicant_key"]]
        project_dates = resolve_project_dates(mode, item["date_role"])
        planned_start_date, planned_end_date = resolve_planned_date(mode, item["planned_role"])
        monthly_report_comment = PROJECT_MONTHLY_REPORTS.get(item["key"])
        monthly_report_role = PROJECT_MONTHLY_REPORT_ROLES.get(item["key"])
        monthly_report_updated_at = (
            resolve_monthly_report_updated_at(mode, monthly_report_role)
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


def create_tasks(mode: str, projects_by_key: dict[str, Project]) -> list[Task]:
    task_specs = {
        "proj_03": [
            ("要件整理ミーティング", "佐藤 美咲", "in_progress", 55, "n1"),
            ("検索条件UI設計", "佐藤 美咲", "in_progress", 60, "n2"),
            ("検索API実装", "佐藤 美咲", "in_progress", 40, "n3"),
            ("インデックス最適化", "佐藤 美咲", "not_started", 0, "n4"),
            ("回帰テストケース作成", "田中 拓海", "in_progress", 35, "n5"),
            ("利用部門レビュー", "田中 拓海", "not_started", 0, "n6"),
            ("運用手順反映", "山本 瑞希", "not_started", 0, "n7"),
        ],
        "proj_07": [
            ("対象サーバ整理", "鈴木 孝介", "in_progress", 55, "d1"),
            ("バックアップジョブ見直し", "鈴木 孝介", "in_progress", 45, "d2"),
            ("監視閾値調整", "中村 直樹", "not_started", 0, "d3"),
            ("通知先メンテ", "高橋 彩乃", "in_progress", 35, "d4"),
            ("手順書更新", "鈴木 孝介", "not_started", 0, "d5"),
            ("定例報告資料作成", "中村 直樹", "not_started", 0, "d6"),
            ("本番適用計画作成", "高橋 彩乃", "not_started", 0, "d7"),
        ],
        "proj_10": [
            ("入力項目棚卸し", "渡辺 優菜", "done", 100, "s1"),
            ("画面遷移改善案作成", "渡辺 優菜", "in_progress", 70, "s2"),
            ("入力補助ロジック実装", "渡辺 優菜", "in_progress", 55, "s3"),
            ("月次帳票テンプレート調整", "伊藤 良太", "in_progress", 40, "s4"),
            ("部門ヒアリング対応", "渡辺 優菜", "not_started", 0, "s5"),
            ("運用説明資料作成", "小林 理絵", "not_started", 0, "s6"),
            ("リリース計画確認", "渡辺 優菜", "not_started", 0, "s7"),
        ],
        "proj_11": [
            ("要件定義レビュー", "伊藤 良太", "in_progress", 60, "b1"),
            ("集計ロジック検証", "伊藤 良太", "in_progress", 55, "b2"),
            ("グラフ表示調整", "伊藤 良太", "in_progress", 40, "b3"),
            ("CSV出力改善", "小林 理絵", "in_progress", 35, "b4"),
            ("予算差異分析観点整理", "伊藤 良太", "not_started", 0, "b5"),
            ("承認者向け説明準備", "小林 理絵", "not_started", 0, "b6"),
            ("受入テスト調整", "伊藤 良太", "not_started", 0, "b7"),
        ],
        "proj_04": [
            ("入力補助候補抽出", "田中 拓海", "done", 100, "co1"),
            ("フォーム文言改修", "田中 拓海", "done", 100, "co2"),
            ("簡易バリデーション追加", "山本 瑞希", "done", 100, "co3"),
            ("UI確認テスト", "佐藤 美咲", "done", 100, "co4"),
            ("操作説明更新", "田中 拓海", "done", 100, "co5"),
            ("完了報告", "山本 瑞希", "done", 100, "co6"),
        ],
        "proj_08": [
            ("権限一覧取り込み", "高橋 彩乃", "done", 100, "cr1"),
            ("棚卸し画面実装", "高橋 彩乃", "done", 100, "cr2"),
            ("判定ルール調整", "中村 直樹", "done", 100, "cr3"),
            ("操作手順確認", "高橋 彩乃", "done", 100, "cr4"),
            ("利用部門確認", "中村 直樹", "done", 100, "cr5"),
            ("完了報告", "高橋 彩乃", "done", 100, "cr6"),
        ],
        "proj_14": [
            ("前月データ参照ロジック整理", "渡辺 優菜", "done", 100, "ws1"),
            ("報告文案生成ルール作成", "渡辺 優菜", "in_progress", 65, "ws2"),
            ("入力漏れチェック実装", "渡辺 優菜", "in_progress", 45, "ws_delay"),
            ("レビュー導線UI調整", "小林 理絵", "not_started", 0, "ws3"),
            ("受入確認シナリオ作成", "渡辺 優菜", "not_started", 0, "ws4"),
        ],
        "proj_15": [
            ("申請手順の棚卸し", "渡辺 優菜", "done", 100, "wc1"),
            ("入力項目の整理", "渡辺 優菜", "done", 100, "wc2"),
            ("承認前チェック項目調整", "小林 理絵", "done", 100, "wc3"),
            ("完了報告導線の確認", "渡辺 優菜", "done", 100, "wc4"),
            ("操作説明の更新", "渡辺 優菜", "done", 100, "wc5"),
        ],
    }

    rows: list[Task] = []
    for project_key, specs in task_specs.items():
        project = projects_by_key[project_key]
        for title, assignee_name, status, progress_rate, task_role in specs:
            start_date, due_date = resolve_task_dates(mode, task_role)
            row = Task(
                project_id=project.id,
                title=title,
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


def create_budget_actual_logs(mode: str, projects_by_key: dict[str, Project]) -> list[BudgetActualLog]:
    budget_specs = {
        "proj_03": [(320000, "初期設計費", "blog_older"), (370000, "API実装費", "blog_old"), (350000, "テスト準備費", "blog_mid"), (352000, "追加調整費", "blog_recent")],
        "proj_07": [(0, "予備ログ", "blog_older"), (510000, "監視設定費", "blog_old"), (430000, "運用改善費", "blog_mid"), (490000, "資料整備費", "blog_mid"), (479000, "調整対応費", "blog_recent")],
        "proj_10": [(360000, "要件整理費", "blog_older"), (390000, "UI調整費", "blog_old"), (320000, "機能実装費", "blog_mid"), (352000, "導入準備費", "blog_recent")],
        "proj_11": [(910000, "要件定義費", "blog_older"), (880000, "集計処理開発費", "blog_old"), (940000, "可視化機能実装費", "blog_mid"), (860000, "テスト・調整費", "blog_mid"), (946000, "追加改修費", "blog_recent")],
        "proj_04": [(380000, "調査費", "blog_old"), (420000, "実装費", "blog_mid"), (416000, "最終調整費", "blog_recent")],
        "proj_08": [(590000, "設計費", "blog_old"), (640000, "開発費", "blog_mid"), (702000, "検証費", "blog_recent")],
        "proj_14": [
            (520000, "要件整理費", "blog_older"),
            (610000, "自動生成ロジック実装費", "blog_old"),
            (430000, "入力チェック調整費", "blog_mid"),
            (380000, "レビュー導線改善費", "blog_recent"),
        ],
        "proj_15": [
            (420000, "設計費", "blog_older"),
            (520000, "実装費", "blog_old"),
            (360000, "テスト費", "blog_mid"),
            (280000, "操作説明整備費", "blog_recent"),
        ],
    }

    rows: list[BudgetActualLog] = []
    for project_key, specs in budget_specs.items():
        project = projects_by_key[project_key]
        for amount, memo, role in specs:
            recorded_on, created_at = resolve_budget_log_dates(mode, role)
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


def create_notifications(mode: str, users_by_key: dict[str, User], projects_by_key: dict[str, Project]) -> list[Notification]:
    specs = [
        ("tajiri", "proj_02", "hq_pending", "REQ-2026-00002 が本部承認待ちです。", False, "notif_recent_a"),
        ("tajiri", "proj_06", "hq_pending", "REQ-2026-00006 が本部承認待ちです。", False, "notif_recent_b"),
        ("yamamoto", "proj_01", "department_pending", "REQ-2026-00001 が部門承認待ちです。", False, "notif_mid_a"),
        ("yamamoto", "proj_03", "approved", "REQ-2026-00003 が承認されました。", True, "notif_mid_b"),
        ("nakamura", "proj_05", "department_pending", "REQ-2026-00005 が部門承認待ちです。", False, "notif_old_a"),
        ("nakamura", "proj_07", "approved", "REQ-2026-00007 が承認されました。", True, "notif_mid_b"),
        ("kobayashi", "proj_09", "department_pending", "REQ-2026-00009 が部門承認待ちです。", False, "notif_mid_a"),
        ("kobayashi", "proj_10", "approved", "REQ-2026-00010 が承認されました。", True, "notif_old_a"),
        ("sato", "proj_03", "approved", "REQ-2026-00003 が承認されました。", False, "notif_recent_b"),
        ("sato", "proj_02", "hq_pending", "REQ-2026-00002 は本部承認待ちに進みました。", False, "notif_mid_a"),
        ("watanabe", "proj_10", "approved", "REQ-2026-00010 が承認されました。", False, "notif_recent_a"),
        ("watanabe", "proj_12", "rejected", "REQ-2026-00012 は却下されました。", False, "notif_recent_b"),
        ("tanaka", "proj_04", "completed", "REQ-2026-00004 が完了しました。", True, "notif_mid_b"),
        ("takahashi", "proj_08", "completed", "REQ-2026-00008 が完了しました。", True, "notif_old_a"),
        ("suzuki", "proj_07", "approved", "REQ-2026-00007 が承認されました。", True, "notif_mid_a"),
        ("ito", "proj_11", "approved", "REQ-2026-00011 が承認されました。", True, "notif_mid_b"),
        ("ito", "proj_09", "application_received", "REQ-2026-00009 の申請を受け付けました。", False, "notif_old_a"),
        ("tanaka", "proj_01", "application_received", "REQ-2026-00001 の申請を受け付けました。", True, "notif_old_a"),
        ("sato", "proj_02", "application_received", "REQ-2026-00002 の申請を受け付けました。", True, "notif_mid_b"),
        ("watanabe", "proj_10", "application_received", "REQ-2026-00010 の申請を受け付けました。", True, "notif_mid_a"),
        ("watanabe", "proj_13", "application_received", "REQ-2026-00013 の申請を受け付けました。", False, "notif_recent_a"),
        ("kobayashi", "proj_13", "department_pending", "REQ-2026-00013 が部門承認待ちです。", False, "notif_recent_a"),
        ("watanabe", "proj_14", "approved", "REQ-2026-00014 が承認されました。", False, "notif_recent_b"),
        ("watanabe", "proj_15", "completed", "REQ-2026-00015 が完了しました。", False, "notif_mid_a"),
    ]

    rows: list[Notification] = []
    for user_key, project_key, notif_type, message, is_read, date_role in specs:
        row = Notification(
            user_id=users_by_key[user_key].id,
            project_id=projects_by_key[project_key].id,
            type=notif_type,
            message=message,
            is_read=is_read,
            created_at=resolve_notification_created_at(mode, date_role),
        )
        db.session.add(row)
        rows.append(row)
    db.session.flush()
    print(f"notifications: {len(rows)}件作成")
    return rows


def create_project_status_logs(mode: str, users_by_key: dict[str, User], projects_by_key: dict[str, Project]) -> list[ProjectStatusLog]:
    rows: list[ProjectStatusLog] = []

    # submit 12件
    for i, project in enumerate(PROJECTS[:12]):
        role = "sl_submit_old" if i < 4 else "sl_submit_mid" if i < 8 else "sl_submit_recent"
        row = ProjectStatusLog(
            project_id=projects_by_key[project["key"]].id,
            actor_id=users_by_key[project["applicant_key"]].id,
            from_status=None,
            to_status="department_pending",
            action="submit",
            comment=None,
            acted_at=resolve_status_log_acted_at(mode, role),
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
            acted_at=resolve_status_log_acted_at(mode, "sl_approve_dept_recent"),
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
            acted_at=resolve_status_log_acted_at(mode, "sl_approve_dept_old"),
        )
        row_hq = ProjectStatusLog(
            project_id=projects_by_key[project_key].id,
            actor_id=users_by_key["tajiri"].id,
            from_status="hq_pending",
            to_status="in_progress",
            action="approve_hq",
            comment=None,
            acted_at=resolve_status_log_acted_at(mode, "sl_approve_hq_recent"),
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
            acted_at=resolve_status_log_acted_at(mode, "sl_approve_dept_old"),
        )
        row_hq = ProjectStatusLog(
            project_id=projects_by_key[project_key].id,
            actor_id=users_by_key["tajiri"].id,
            from_status="hq_pending",
            to_status="in_progress",
            action="approve_hq",
            comment=None,
            acted_at=resolve_status_log_acted_at(mode, "sl_approve_hq_old"),
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
            acted_at=resolve_status_log_acted_at(mode, role),
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
        acted_at=resolve_status_log_acted_at(mode, "sl_reject_recent"),
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
        acted_at=resolve_status_log_acted_at(mode, "sl_submit_recent"),
    )
    db.session.add(row_submit_13)
    rows.append(row_submit_13)

    # 渡辺 優菜の追加デモ案件: 開発中1件（申請 → 部門承認 → 本部承認）
    row_submit_14 = ProjectStatusLog(
        project_id=projects_by_key["proj_14"].id,
        actor_id=users_by_key["watanabe"].id,
        from_status=None,
        to_status="department_pending",
        action="submit",
        comment=None,
        acted_at=resolve_status_log_acted_at(mode, "sl_submit_mid"),
    )
    row_dept_14 = ProjectStatusLog(
        project_id=projects_by_key["proj_14"].id,
        actor_id=users_by_key["kobayashi"].id,
        from_status="department_pending",
        to_status="hq_pending",
        action="approve_department",
        comment=None,
        acted_at=resolve_status_log_acted_at(mode, "sl_approve_dept_old"),
    )
    row_hq_14 = ProjectStatusLog(
        project_id=projects_by_key["proj_14"].id,
        actor_id=users_by_key["tajiri"].id,
        from_status="hq_pending",
        to_status="in_progress",
        action="approve_hq",
        comment=None,
        acted_at=resolve_status_log_acted_at(mode, "sl_approve_hq_recent"),
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
        acted_at=resolve_status_log_acted_at(mode, "sl_submit_old"),
    )
    row_dept_15 = ProjectStatusLog(
        project_id=projects_by_key["proj_15"].id,
        actor_id=users_by_key["kobayashi"].id,
        from_status="department_pending",
        to_status="hq_pending",
        action="approve_department",
        comment=None,
        acted_at=resolve_status_log_acted_at(mode, "sl_approve_dept_old"),
    )
    row_hq_15 = ProjectStatusLog(
        project_id=projects_by_key["proj_15"].id,
        actor_id=users_by_key["tajiri"].id,
        from_status="hq_pending",
        to_status="in_progress",
        action="approve_hq",
        comment=None,
        acted_at=resolve_status_log_acted_at(mode, "sl_approve_hq_old"),
    )
    row_complete_15 = ProjectStatusLog(
        project_id=projects_by_key["proj_15"].id,
        actor_id=users_by_key["watanabe"].id,
        from_status="in_progress",
        to_status="completed",
        action="complete",
        comment=None,
        acted_at=resolve_status_log_acted_at(mode, "sl_complete_old"),
    )
    db.session.add(row_submit_15)
    db.session.add(row_dept_15)
    db.session.add(row_hq_15)
    db.session.add(row_complete_15)
    rows.extend([row_submit_15, row_dept_15, row_hq_15, row_complete_15])

    db.session.flush()
    print(f"project_status_logs: {len(rows)}件作成")
    return rows


def main() -> None:
    if SEED_MODE not in {"fixed", "relative"}:
        raise ValueError("SEED_MODE は 'fixed' または 'relative' を指定してください。")

    with app.app_context():
        print(f"seed開始: mode={SEED_MODE}")
        reset_all_data()

        departments_by_key = create_departments()
        create_department_yearly_budgets(departments_by_key)
        users_by_key = create_users(departments_by_key)
        create_project_drafts(SEED_MODE, users_by_key, departments_by_key)
        projects_by_key = create_projects(SEED_MODE, users_by_key, departments_by_key)
        create_tasks(SEED_MODE, projects_by_key)
        create_budget_actual_logs(SEED_MODE, projects_by_key)
        create_notifications(SEED_MODE, users_by_key, projects_by_key)
        create_project_status_logs(SEED_MODE, users_by_key, projects_by_key)

        db.session.commit()
        print("seed完了")
        print("投入モード:", SEED_MODE)
        print("投入件数: departments=3, department_yearly_budgets=3, users=10, project_drafts=5, projects=15, tasks=50, budget_actual_logs=32, notifications=24, project_status_logs=37")


if __name__ == "__main__":
    main()
