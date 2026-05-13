import os
import re
from datetime import date, datetime, timedelta
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP
from zoneinfo import ZoneInfo
from dotenv import load_dotenv  # .envファイルを読み込むライブラリ
from flask import Flask, flash, jsonify, redirect, render_template, request, session, url_for  # Webアプリ本体を作るフレームワーク
from flask_migrate import Migrate  # DBマイグレーション（DB構造変更の履歴管理）ツール
from flask_login import LoginManager, current_user, login_required, login_user, logout_user  # ログイン管理用ライブラリ
from flask_wtf import CSRFProtect
from sqlalchemy import func
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import joinedload
from werkzeug.security import check_password_hash

from forms import LoginForm
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
    jst_today,
    utc_now,
)  # db = SQLAlchemy本体、User = ユーザーモデル

# .envファイルを読み込む
load_dotenv()

app = Flask(__name__)

# 基本設定
app.config["SECRET_KEY"] = os.getenv("SECRET_KEY", "dev-secret-key")
app.config["SQLALCHEMY_DATABASE_URI"] = os.getenv("DATABASE_URL")
app.config["SQLALCHEMY_ENGINE_OPTIONS"] = {
    "pool_pre_ping": True,
    "pool_recycle": 300,
}
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False

# 拡張機能（Flaskに追加機能を付けるライブラリ）を初期化
# app に db 情報を登録し、マイグレーションとログイン管理を有効化
db.init_app(app)
migrate = Migrate(app, db)
login_manager = LoginManager(app)
csrf = CSRFProtect(app)

# 未ログイン時に飛ばすログイン画面のURL
login_manager.login_view = "login"
login_manager.login_message = "このページを表示するにはログインしてください。"
login_manager.login_message_category = "warning"


@login_manager.user_loader
def load_user(user_id):
    """Flask-Login用。ユーザーIDからユーザーを取得する。"""
    return User.query.get(int(user_id))


@app.route("/")
def index():
    """動作確認トップページ。"""
    return "Hello, quest_1!"


# =============================
# ■ 共通：ログイン画面
# =============================
@app.route("/login", methods=["GET", "POST"])
def login():
    """ログイン画面とログイン処理。"""
    # ログイン済みユーザーはロール別トップへ戻す
    if current_user.is_authenticated:
        return redirect(redirect_by_role(current_user.role))

    form = LoginForm()
    inline_error = None

    # 入力チェックを通過した場合のみ認証処理を行う
    if form.validate_on_submit():
        user = User.query.filter_by(login_id=form.login_id.data).first()

        # 認証可否に関わらず同じエラーメッセージを返す
        if user and user.is_active and check_password_hash(user.password_hash, form.password.data):
            login_user(user, remember=form.remember.data)
            session["login_success_toast"] = "ログイン成功"
            return redirect(redirect_by_role(user.role))

        inline_error = "IDまたはパスワードが正しくありません"
    elif form.is_submitted():
        # 複数エラー時でも最初の1件だけ表示する
        for field in (form.login_id, form.password):
            if field.errors:
                inline_error = field.errors[0]
                break

    return render_template(
        "login.html",
        form=form,
        inline_error=inline_error,
        login_toast_message=session.pop("login_toast_message", None),
    )


def redirect_by_role(role: str):
    if role == "applicant":
        return url_for("applicant_top")
    if role == "manager":
        return url_for("manager_top")
    if role == "hq":
        return url_for("hq_top")
    return url_for("index")


@app.context_processor
def inject_global_toast_messages():
    """共通トースト表示用のメッセージを全テンプレートへ渡す。"""
    messages = []

    login_success_toast = session.pop("login_success_toast", None)
    if login_success_toast:
        messages.append({"category": "success", "message": login_success_toast})

    return {"global_toast_messages": messages}


def require_applicant():
    """申請者ロールのみ通す。権限外はロール別トップへ戻す。"""
    if current_user.role != "applicant":
        return redirect(redirect_by_role(current_user.role))
    return None


def require_manager():
    """部門管理者ロールのみ許可する。"""
    if current_user.role != "manager":
        return redirect(redirect_by_role(current_user.role))
    return None


def require_hq():
    """本部管理者ロールのみ許可する。"""
    if current_user.role != "hq":
        return redirect(redirect_by_role(current_user.role))
    return None


def parse_date_value(value: str):
    """YYYY-MM-DD文字列をdateへ変換。空文字はNone。"""
    raw = (value or "").strip()
    if not raw:
        return None, None
    try:
        return date.fromisoformat(raw), None
    except ValueError:
        return None, "日付の形式が正しくありません。"


def get_unread_notifications_count() -> int:
    """ログインユーザーの未読通知件数。"""
    return Notification.query.filter_by(user_id=current_user.id, is_read=False).count()


def format_jst_date(dt: datetime | None, pattern: str = "%Y/%m/%d") -> str:
    """UTC保存のDateTimeをJST表示文字列に整形する。"""
    if dt is None:
        return "—"
    return dt.astimezone(ZoneInfo("Asia/Tokyo")).strftime(pattern)


def format_jst_date_ja(dt: datetime | None) -> str:
    """UTC保存のDateTimeをJSTの日本語日付に整形する。"""
    if dt is None:
        return "—"
    jst_dt = dt.astimezone(ZoneInfo("Asia/Tokyo"))
    return f"{jst_dt.year}年{jst_dt.month}月{jst_dt.day}日"


def format_business_date(d: date | None, pattern: str = "%Y/%m/%d") -> str:
    """Date型を業務日付として表示整形する。"""
    if d is None:
        return "未設定"
    return d.strftime(pattern)


def format_business_date_ja(d: date | None) -> str:
    """Date型を日本語日付で整形する。"""
    if d is None:
        return "未設定"
    return f"{d.year}年{d.month}月{d.day}日"


def format_decimal_amount(value: Decimal | None) -> str:
    """金額を3桁区切りの円表記に整形する。"""
    if value is None:
        return "¥0"
    return f"¥{int(value):,}"


def format_person_months(value: Decimal | None) -> str:
    """工数を不要な末尾0を落として人月表記に整形する。"""
    if value is None:
        return "0 人月"
    normalized = value.normalize()
    text = format(normalized, "f").rstrip("0").rstrip(".")
    return f"{text} 人月"


def format_percent_value(value: Decimal | None) -> str:
    """割合を小数第1位まで表示し、不要な .0 だけを取り除く。"""
    if value is None:
        return "0"
    rounded = value.quantize(Decimal("0.1"))
    text = format(rounded, "f")
    if text.endswith(".0"):
        text = text[:-2]
    return text


def _format_hq_percent_int(value: Decimal | int | float | None) -> str:
    """HQトップ用。割合を整数％表示用の文字列に整形する。"""
    if value is None:
        return "0"
    decimal_value = Decimal(str(value))
    return str(int(decimal_value.quantize(Decimal("1"), rounding=ROUND_HALF_UP)))


def get_fiscal_year(target_date: date) -> int:
    """Date型（業務日付）から日本の年度を返す。"""
    return target_date.year if target_date.month >= 4 else target_date.year - 1


def get_latest_rejection_log(project: Project) -> ProjectStatusLog | None:
    """案件の最新却下ログを返す。"""
    reject_logs = [
        log
        for log in project.project_status_logs
        if log.to_status == "rejected" or log.action in {"reject_department", "reject_hq"}
    ]
    if not reject_logs:
        return None
    return max(reject_logs, key=lambda log: (log.acted_at, log.id))


def build_project_status_view_data(project: Project) -> dict:
    """申請状況画面の表示用データを作る。"""
    status_map = {
        "department_pending": {"banner_class": "s-wait-dept", "label": "部門承認待ち"},
        "hq_pending": {"banner_class": "s-wait-hq", "label": "本部承認待ち"},
        "rejected": {"banner_class": "s-reject", "label": "却下（要修正）"},
    }
    status_info = status_map.get(project.status, status_map["department_pending"])

    logs_by_action = {}
    for log in project.project_status_logs:
        logs_by_action.setdefault(log.action, []).append(log)
    for action, logs in logs_by_action.items():
        logs_by_action[action] = max(logs, key=lambda item: (item.acted_at, item.id))

    submit_log = logs_by_action.get("submit")
    submitted_at = submit_log.acted_at if submit_log else project.created_at
    dept_approved_log = logs_by_action.get("approve_department")
    rejection_log = get_latest_rejection_log(project)

    planned_start = format_business_date(project.planned_start_date) if project.planned_start_date else "未設定"
    planned_end = format_business_date(project.planned_end_date) if project.planned_end_date else "未設定"
    if project.planned_start_date or project.planned_end_date:
        planned_period = f"{planned_start} 〜 {planned_end}"
    else:
        planned_period = "未設定"

    step2_label = "部門確認"
    step2_class = ""
    step2_icon = "2"
    step2_date = "—"
    step3_label = "本部確認"
    step3_class = ""
    step3_icon = "3"
    step3_date = "—"
    step4_class = ""
    step4_icon = "4"
    step4_date = "—"

    if project.status == "department_pending":
        step2_class = "st-current"
        step2_icon = "⋯"
        step2_date = "待機中"
    elif project.status == "hq_pending":
        step2_class = "st-done"
        step2_icon = "✓"
        step2_label = "部門承認済"
        step2_date = format_jst_date(dept_approved_log.acted_at, "%m/%d") if dept_approved_log else "—"
        step3_class = "st-current"
        step3_icon = "⋯"
        step3_date = "待機中"
    elif project.status == "rejected":
        if rejection_log and rejection_log.action == "reject_hq":
            step2_class = "st-done"
            step2_icon = "✓"
            step2_label = "部門承認済"
            step2_date = format_jst_date(dept_approved_log.acted_at, "%m/%d") if dept_approved_log else "—"
            step3_class = "st-reject"
            step3_icon = "✕"
            step3_label = "本部 却下"
            step3_date = format_jst_date(rejection_log.acted_at, "%m/%d")
        else:
            step2_class = "st-reject"
            step2_icon = "✕"
            step2_label = "部門 却下"
            step2_date = format_jst_date(rejection_log.acted_at, "%m/%d") if rejection_log else "—"

    rejection_comment = (project.rejection_comment or "").strip() or "却下理由は登録されていません。"
    reject_who = "—"
    if rejection_log:
        actor_name = rejection_log.actor.display_name if rejection_log.actor else "不明"
        reject_who = f"{actor_name} / {format_jst_date(rejection_log.acted_at, '%m/%d')}"

    return {
        "project_id": project.id,
        "status": project.status,
        "status_label": status_info["label"],
        "banner_class": status_info["banner_class"],
        "project_name": project.title,
        "project_code": project.project_code,
        "status_meta": f"申請日：{format_jst_date(submitted_at)} ／ {project.project_code}",
        "created_at_display": format_jst_date_ja(submitted_at),
        "applicant_name": project.applicant.display_name if project.applicant else "—",
        "department_name": project.department.name if project.department else "—",
        "purpose": project.purpose,
        "budget_display": format_decimal_amount(project.estimated_budget_amount),
        "person_months_display": format_person_months(project.estimated_person_months),
        "planned_period_display": planned_period,
        "show_reject_panel": project.status == "rejected",
        "reject_who": reject_who,
        "reject_comment": rejection_comment,
        "steps": [
            {
                "class_name": "st-done",
                "icon": "✓",
                "label": "申請済み",
                "date": format_jst_date(submitted_at, "%m/%d"),
            },
            {"class_name": step2_class, "icon": step2_icon, "label": step2_label, "date": step2_date},
            {"class_name": step3_class, "icon": step3_icon, "label": step3_label, "date": step3_date},
            {"class_name": step4_class, "icon": step4_icon, "label": "承認完了", "date": step4_date},
        ],
    }


def serialize_project_draft(draft: ProjectDraft) -> dict:
    """下書きを画面表示・JS用に整形する。"""
    purpose = (draft.purpose or "").strip()
    return {
        "id": int(draft.id),
        "title": draft.title or "",
        "purpose": draft.purpose or "",
        "department_id": int(draft.department_id) if draft.department_id is not None else None,
        "department_name": draft.department.name if draft.department else "",
        "estimated_budget_amount": int(draft.estimated_budget_amount) if draft.estimated_budget_amount is not None else None,
        "estimated_person_months": float(draft.estimated_person_months) if draft.estimated_person_months is not None else None,
        "planned_start_date": draft.planned_start_date.isoformat() if draft.planned_start_date else "",
        "planned_end_date": draft.planned_end_date.isoformat() if draft.planned_end_date else "",
        "updated_at_display": draft.updated_at.astimezone(ZoneInfo("Asia/Tokyo")).strftime("%Y/%m/%d %H:%M"),
        "purpose_preview": (purpose[:120] + "…") if len(purpose) > 120 else purpose,
    }


def prune_old_project_drafts(user_id: int):
    """下書き上限を5件に保つ。古いものから削除。"""
    stale_drafts = (
        ProjectDraft.query.filter_by(user_id=user_id)
        .order_by(ProjectDraft.updated_at.desc(), ProjectDraft.id.desc())
        .offset(5)
        .all()
    )
    for stale in stale_drafts:
        db.session.delete(stale)


def validate_project_form(form_data: dict):
    """申請時バリデーション。"""
    errors = {}
    normalized = {}

    title = (form_data.get("title") or "").strip()
    if not title:
        errors["title"] = "案件名を入力してください。"
    elif len(title) > 60:
        errors["title"] = "案件名は60文字以内で入力してください。"
    normalized["title"] = title

    purpose = (form_data.get("purpose") or "").strip()
    if len(purpose) < 5:
        errors["purpose"] = "目的・概要は5文字以上で入力してください。"
    elif len(purpose) > 500:
        errors["purpose"] = "目的・概要は500文字以内で入力してください。"
    normalized["purpose"] = purpose

    department_raw = (form_data.get("department_id") or "").strip()
    if not department_raw:
        errors["department_id"] = "担当部門を選択してください。"
        normalized["department_id"] = None
    else:
        try:
            department_id = int(department_raw)
        except ValueError:
            errors["department_id"] = "担当部門を選択してください。"
            department_id = None
        normalized["department_id"] = department_id

    budget_raw = (form_data.get("estimated_budget_amount") or "").strip()
    if not budget_raw:
        errors["estimated_budget_amount"] = "金額（予算）を入力してください。"
        normalized["estimated_budget_amount"] = None
    elif not budget_raw.isdigit():
        errors["estimated_budget_amount"] = "金額（予算）は半角数字で入力してください。"
        normalized["estimated_budget_amount"] = None
    else:
        budget_int = int(budget_raw)
        if budget_int < 1:
            errors["estimated_budget_amount"] = "金額（予算）は1円以上で入力してください。"
        elif budget_int > 999_999_999:
            errors["estimated_budget_amount"] = "金額（予算）は999,999,999円以下で入力してください。"
        normalized["estimated_budget_amount"] = Decimal(str(budget_int))

    person_months_raw = (form_data.get("estimated_person_months") or "").strip()
    if not person_months_raw:
        errors["estimated_person_months"] = "工数（人月）を入力してください。"
        normalized["estimated_person_months"] = None
    else:
        try:
            person_months = Decimal(person_months_raw)
        except InvalidOperation:
            errors["estimated_person_months"] = "工数（人月）は半角数字で入力してください。"
            person_months = None
        if person_months is not None:
            if person_months < Decimal("0.1"):
                errors["estimated_person_months"] = "工数（人月）は0.1以上で入力してください。"
            elif person_months > Decimal("999.9"):
                errors["estimated_person_months"] = "工数（人月）は999.9以下で入力してください。"
            normalized["estimated_person_months"] = person_months.quantize(Decimal("0.01"))

    start_date, start_err = parse_date_value(form_data.get("planned_start_date", ""))
    end_date, end_err = parse_date_value(form_data.get("planned_end_date", ""))
    if not start_date:
        errors["planned_dates"] = "開始予定日を入力してください。"
    elif start_err or end_err:
        errors["planned_dates"] = "日付の形式が正しくありません。"
    elif start_date and end_date and start_date > end_date:
        errors["planned_dates"] = "開始予定日は完了予定日以前の日付にしてください。"
    normalized["planned_start_date"] = start_date
    normalized["planned_end_date"] = end_date

    confirmed = (form_data.get("confirmed") or "").strip()
    if confirmed != "1":
        errors["confirmed"] = "確認後に申請してください。"
    normalized["confirmed"] = confirmed

    draft_id_raw = (form_data.get("draft_id") or "").strip()
    if draft_id_raw:
        try:
            normalized["draft_id"] = int(draft_id_raw)
        except ValueError:
            normalized["draft_id"] = None
    else:
        normalized["draft_id"] = None

    return errors, normalized


def validate_project_draft_form(payload: dict):
    """下書き保存時バリデーション。"""
    errors = {}
    normalized = {
        "title": (payload.get("title") or "").strip(),
        "purpose": (payload.get("purpose") or "").strip(),
        "department_id": None,
        "estimated_budget_amount": None,
        "estimated_person_months": None,
        "planned_start_date": None,
        "planned_end_date": None,
    }

    department_raw = (payload.get("department_id") or "").strip()
    if department_raw:
        try:
            normalized["department_id"] = int(department_raw)
        except ValueError:
            errors["department_id"] = "担当部門を選択してください。"

    budget_raw = (payload.get("estimated_budget_amount") or "").strip()
    if budget_raw:
        if not budget_raw.isdigit():
            errors["estimated_budget_amount"] = "金額（予算）は半角数字で入力してください。"
        else:
            budget_int = int(budget_raw)
            if budget_int < 1:
                errors["estimated_budget_amount"] = "金額（予算）は1円以上で入力してください。"
            elif budget_int > 999_999_999:
                errors["estimated_budget_amount"] = "金額（予算）は999,999,999円以下で入力してください。"
            normalized["estimated_budget_amount"] = Decimal(str(budget_int))

    pm_raw = (payload.get("estimated_person_months") or "").strip()
    if pm_raw:
        try:
            pm = Decimal(pm_raw)
        except InvalidOperation:
            errors["estimated_person_months"] = "工数（人月）は半角数字で入力してください。"
            pm = None
        if pm is not None:
            if pm < Decimal("0.1"):
                errors["estimated_person_months"] = "工数（人月）は0.1以上で入力してください。"
            elif pm > Decimal("999.9"):
                errors["estimated_person_months"] = "工数（人月）は999.9以下で入力してください。"
            normalized["estimated_person_months"] = pm.quantize(Decimal("0.01"))

    start_date, start_err = parse_date_value(payload.get("planned_start_date", ""))
    end_date, end_err = parse_date_value(payload.get("planned_end_date", ""))
    if start_err or end_err:
        errors["planned_dates"] = "日付の形式が正しくありません。"
    elif start_date and end_date and start_date > end_date:
        errors["planned_dates"] = "開始予定日は完了予定日以前の日付にしてください。"
    normalized["planned_start_date"] = start_date
    normalized["planned_end_date"] = end_date

    has_any = any(
        [
            normalized["title"],
            normalized["purpose"],
            normalized["department_id"] is not None,
            normalized["estimated_budget_amount"] is not None,
            normalized["estimated_person_months"] is not None,
            normalized["planned_start_date"] is not None,
            normalized["planned_end_date"] is not None,
        ]
    )
    if not has_any:
        errors["empty"] = "保存できる内容がありません。1項目以上入力してください。"

    return errors, normalized


def generate_project_code() -> str:
    """REQ-YYYY-xxxxx 形式の案件番号を生成する。"""
    year = datetime.now(ZoneInfo("Asia/Tokyo")).year
    prefix = f"REQ-{year}-"
    latest = (
        Project.query.filter(Project.project_code.like(f"{prefix}%"))
        .order_by(Project.project_code.desc())
        .first()
    )
    last_seq = 0
    if latest:
        suffix = latest.project_code.replace(prefix, "")
        if suffix.isdigit():
            last_seq = int(suffix)
    return f"{prefix}{str(last_seq + 1).zfill(5)}"


# =============================
# ■ 共通：ログアウト処理
# =============================
@app.route("/logout", methods=["POST"])
@login_required
def logout():
    """ログアウト処理。"""
    logout_user()
    session["login_toast_message"] = "ログアウトしました。"
    return redirect(url_for("login"))


# =============================
# ■ 申請者：トップ画面
# =============================
def build_empty_applicant_top_view_data() -> dict:
    """申請者トップ画面の空状態データを返す。"""
    return {
        "approval_projects": [],
        "in_progress_projects": [],
        "attention_tasks": {
            "delayed": {
                "count_label": "なし",
                "count_class": "side-card-count-normal",
                "items": [],
            },
            "due_soon": {
                "count_label": "なし",
                "count_class": "side-card-count-normal",
                "items": [],
            },
        },
    }


def build_applicant_top_approval_projects(projects: list[Project]) -> list[dict]:
    """申請中案件の承認ステータス表示データを作成する。"""
    items = []
    for project in projects:
        submit_logs = [log for log in project.project_status_logs if log.action == "submit" and log.acted_at is not None]
        submitted_at = max((log.acted_at for log in submit_logs), default=None) or project.created_at
        submitted_sort_at = submitted_at or datetime.min.replace(tzinfo=ZoneInfo("UTC"))

        steps = []
        is_rejected = project.status == "rejected"
        reject_message = ""
        if project.status == "department_pending":
            steps = [
                {"class_name": "done", "icon": "✓", "label": "申請済"},
                {"class_name": "current", "icon": "⋯", "label": "部門承認待ち"},
                {"class_name": "", "icon": "3", "label": "本部承認待ち"},
                {"class_name": "", "icon": "4", "label": "開発管理へ"},
            ]
        elif project.status == "hq_pending":
            steps = [
                {"class_name": "done", "icon": "✓", "label": "申請済"},
                {"class_name": "done", "icon": "✓", "label": "部門承認済"},
                {"class_name": "current", "icon": "⋯", "label": "本部承認待ち"},
                {"class_name": "", "icon": "4", "label": "開発管理へ"},
            ]
        elif project.status == "rejected":
            rejection_log = get_latest_rejection_log(project)
            if rejection_log and rejection_log.action == "reject_hq":
                steps = [
                    {"class_name": "done", "icon": "✓", "label": "申請済"},
                    {"class_name": "done", "icon": "✓", "label": "部門承認済"},
                    {"class_name": "rejected", "icon": "✕", "label": "本部却下"},
                    {"class_name": "", "icon": "4", "label": "開発管理へ"},
                ]
                reject_message = "本部管理者より却下されました。"
            elif rejection_log and rejection_log.action == "reject_department":
                steps = [
                    {"class_name": "done", "icon": "✓", "label": "申請済"},
                    {"class_name": "rejected", "icon": "✕", "label": "部門却下"},
                    {"class_name": "", "icon": "3", "label": "本部承認待ち"},
                    {"class_name": "", "icon": "4", "label": "開発管理へ"},
                ]
                reject_message = "部門管理者より却下されました。"
            else:
                steps = [
                    {"class_name": "done", "icon": "✓", "label": "申請済"},
                    {"class_name": "rejected", "icon": "✕", "label": "却下"},
                    {"class_name": "", "icon": "3", "label": "本部承認待ち"},
                    {"class_name": "", "icon": "4", "label": "開発管理へ"},
                ]
                reject_message = "申請は却下されました。"

        items.append(
            {
                "project_id": project.id,
                "project_name": project.title or "",
                "department_name": project.department.name if project.department else "未設定",
                "submitted_date_display": format_jst_date(submitted_at),
                "submitted_sort_at": submitted_sort_at,
                "is_rejected": is_rejected,
                "reject_message": reject_message,
                "steps": steps,
            }
        )

    items.sort(key=lambda item: (item["submitted_sort_at"], -item["project_id"]), reverse=True)
    for item in items:
        item.pop("submitted_sort_at", None)
    return items


def build_applicant_top_in_progress_projects(projects: list[Project]) -> list[dict]:
    """開発管理中案件カードの表示データを作成する。"""
    today = jst_today()
    items = []

    for project in projects:
        incomplete_tasks = [task for task in project.tasks if task.status != "done"]
        overdue_days = [(today - task.due_date).days for task in incomplete_tasks if task.due_date and task.due_date < today]
        has_delay = len(overdue_days) > 0
        delay_days_max = max(overdue_days) if overdue_days else 0

        total_tasks = len(project.tasks)
        progress_pct = 0
        if total_tasks > 0:
            progress_pct = int(round(sum(int(task.progress_rate or 0) for task in project.tasks) / total_tasks))

        base_budget = project.approved_budget_amount if project.approved_budget_amount is not None else project.estimated_budget_amount
        base_budget = Decimal(base_budget or 0)
        actual_budget = sum((Decimal(log.amount or 0) for log in project.budget_actual_logs), Decimal("0"))
        budget_pct = 0
        if base_budget > 0:
            budget_pct = int(round((actual_budget / base_budget) * Decimal("100")))

        budget_label = None
        budget_label_class = ""
        budget_gauge_class = "gf-budget-ok"
        if budget_pct >= 100:
            budget_label = "予算"
            budget_label_class = "pc-budget-over-badge"
            budget_gauge_class = "gf-budget-over"
        elif budget_pct >= 80:
            budget_label = "予算"
            budget_label_class = "pc-warning-badge"
            budget_gauge_class = "gf-budget-warn"

        card_class = "normal"
        if has_delay:
            card_class = "delayed"
        elif budget_pct >= 80:
            card_class = "warning"

        planned_end = project.planned_end_date
        items.append(
            {
                "project_id": project.id,
                "project_name": project.title or "",
                "department_name": project.department.name if project.department else "未設定",
                "planned_end_display": format_business_date(planned_end),
                "progress_pct": progress_pct,
                "progress_gauge_width": max(0, min(progress_pct, 100)),
                "budget_pct": budget_pct,
                "budget_gauge_width": max(0, min(budget_pct, 100)),
                "budget_gauge_class": budget_gauge_class,
                "budget_label": budget_label,
                "budget_label_class": budget_label_class,
                "has_delay": has_delay,
                "delay_days_max": delay_days_max,
                "card_class": card_class,
                "planned_end_sort_key": planned_end,
            }
        )

    # 遅延案件を先頭にし、遅延なし案件は完了予定日が近い順で並べる
    delayed_items = [item for item in items if item["has_delay"]]
    delayed_items.sort(key=lambda item: (-item["delay_days_max"], item["project_id"]))

    non_delayed_items = [item for item in items if not item["has_delay"]]
    non_delayed_items.sort(
        key=lambda item: (
            item["planned_end_sort_key"] is None,
            item["planned_end_sort_key"] or date.max,
            item["project_id"],
        )
    )

    sorted_items = delayed_items + non_delayed_items
    for item in sorted_items:
        item.pop("planned_end_sort_key", None)
    return sorted_items


def build_applicant_top_attention_tasks(projects: list[Project]) -> dict:
    """注意タスク（遅延・3日以内期限）の表示データを作成する。"""
    today = jst_today()
    due_soon_last = today + timedelta(days=2)
    delayed_items = []
    due_soon_items = []

    for project in projects:
        for task in project.tasks:
            if task.status == "done" or task.due_date is None:
                continue

            progress_rate = int(task.progress_rate or 0)
            if task.due_date < today:
                delayed_days = (today - task.due_date).days
                delayed_items.append(
                    {
                        "project_id": project.id,
                        "task_id": task.id,
                        "task_name": task.title or "",
                        "project_name": project.title or "",
                        "due_label": f"+{delayed_days}",
                        "progress_rate_label": f"{progress_rate}%",
                        "due_date_sort_key": task.due_date,
                    }
                )
            elif today <= task.due_date <= due_soon_last:
                due_label = f"{task.due_date.month}/{task.due_date.day}"
                due_class = "side-task-due-normal"
                due_kind = "due_later"
                if task.due_date == today:
                    due_label = "今日"
                    due_class = "side-task-due-today"
                    due_kind = "due_today"
                elif task.due_date == today + timedelta(days=1):
                    due_label = "明日"
                    due_class = "side-task-due-soon"
                    due_kind = "due_tomorrow"

                due_soon_items.append(
                    {
                        "project_id": project.id,
                        "task_id": task.id,
                        "task_name": task.title or "",
                        "project_name": project.title or "",
                        "due_label": due_label,
                        "due_class": due_class,
                        "due_kind": due_kind,
                        "progress_rate_label": f"{progress_rate}%",
                        "due_date_sort_key": task.due_date,
                    }
                )

    delayed_items.sort(key=lambda item: (item["due_date_sort_key"], item["task_id"]))
    due_soon_items.sort(
        key=lambda item: (
            item["due_date_sort_key"],
            item["task_id"],
        )
    )

    delayed_count = len(delayed_items)
    due_soon_count = len(due_soon_items)
    delayed_count_label = f"{delayed_count}件" if delayed_count > 0 else "なし"
    delayed_count_class = "side-card-count-danger" if delayed_count > 0 else "side-card-count-normal"

    due_soon_count_label = f"{due_soon_count}件" if due_soon_count > 0 else "なし"
    if due_soon_count == 0:
        due_soon_count_class = "side-card-count-normal"
    elif any(item["due_kind"] == "due_today" for item in due_soon_items):
        due_soon_count_class = "side-card-count-danger"
    elif any(item["due_kind"] == "due_tomorrow" for item in due_soon_items):
        due_soon_count_class = "side-card-count-warning"
    else:
        due_soon_count_class = "side-card-count-muted"

    for item in delayed_items:
        item.pop("due_date_sort_key", None)
    for item in due_soon_items:
        item.pop("due_date_sort_key", None)

    return {
        "delayed": {
            "count_label": delayed_count_label,
            "count_class": delayed_count_class,
            "items": delayed_items,
        },
        "due_soon": {
            "count_label": due_soon_count_label,
            "count_class": due_soon_count_class,
            "items": due_soon_items,
        },
    }


def build_applicant_top_view_data(user_id: int) -> dict:
    """申請者トップ画面の表示データをまとめて作成する。"""
    approval_projects = (
        Project.query.options(
            joinedload(Project.department),
            joinedload(Project.project_status_logs),
        )
        .filter(
            Project.applicant_id == user_id,
            Project.status.in_(["department_pending", "hq_pending", "rejected"]),
        )
        .all()
    )

    in_progress_projects = (
        Project.query.options(
            joinedload(Project.department),
            joinedload(Project.tasks),
            joinedload(Project.budget_actual_logs),
        )
        .filter(
            Project.applicant_id == user_id,
            Project.status == "in_progress",
            Project.approval_stage == "approved",
        )
        .all()
    )

    return {
        "approval_projects": build_applicant_top_approval_projects(approval_projects),
        "in_progress_projects": build_applicant_top_in_progress_projects(in_progress_projects),
        "attention_tasks": build_applicant_top_attention_tasks(in_progress_projects),
    }


@app.route("/top/applicant")
@login_required
def applicant_top():
    access_error = require_applicant()
    if access_error:
        return access_error

    try:
        view_data = build_applicant_top_view_data(current_user.id)
    except SQLAlchemyError:
        db.session.rollback()
        flash("ダッシュボード情報の取得に失敗しました。時間をおいてもう一度お試しください。", "danger")
        view_data = build_empty_applicant_top_view_data()

    return render_template(
        "applicant_top.html",
        view_data=view_data,
        unread_notifications_count=get_unread_notifications_count(),
    )


# =============================
# ■ 申請者：新規案件申請画面
# =============================
@app.route("/applicant/projects/new", methods=["GET", "POST"])
@login_required
def applicant_project_new():
    access_error = require_applicant()
    if access_error:
        return access_error

    departments = Department.query.order_by(Department.id.asc()).all()
    department_ids = {int(d.id) for d in departments}

    # 自分の下書きのみ新しい順で5件まで取得
    draft_records = (
        ProjectDraft.query.options(joinedload(ProjectDraft.department))
        .filter(ProjectDraft.user_id == current_user.id)
        .order_by(ProjectDraft.updated_at.desc(), ProjectDraft.id.desc())
        .limit(5)
        .all()
    )
    drafts_json = [serialize_project_draft(d) for d in draft_records]

    form_data = {
        "title": "",
        "department_id": "",
        "purpose": "",
        "estimated_budget_amount": "",
        "estimated_person_months": "",
        "planned_start_date": "",
        "planned_end_date": "",
        "draft_id": "",
    }
    form_errors = {}

    if request.method == "POST":
        raw_form = {
            "title": request.form.get("title", ""),
            "department_id": request.form.get("department_id", ""),
            "purpose": request.form.get("purpose", ""),
            "estimated_budget_amount": request.form.get("estimated_budget_amount", ""),
            "estimated_person_months": request.form.get("estimated_person_months", ""),
            "planned_start_date": request.form.get("planned_start_date", ""),
            "planned_end_date": request.form.get("planned_end_date", ""),
            "confirmed": request.form.get("confirmed", ""),
            "draft_id": request.form.get("draft_id", ""),
        }
        form_data.update({k: v for k, v in raw_form.items() if k in form_data})
        form_errors, normalized = validate_project_form(raw_form)

        # 部門存在チェック
        selected_department_id = normalized.get("department_id")
        if selected_department_id is not None and selected_department_id not in department_ids:
            form_errors["department_id"] = "選択された部門が見つかりません。"

        if not departments:
            form_errors["department_id"] = "申請に必要な部門データがありません。管理者に確認してください。"

        if form_errors:
            flash("入力内容を確認してください。", "danger")
        else:
            draft_to_delete = None
            draft_id = normalized.get("draft_id")
            if draft_id is not None:
                draft_to_delete = ProjectDraft.query.filter_by(id=draft_id, user_id=current_user.id).first()

            project = Project(
                project_code=generate_project_code(),
                title=normalized["title"],
                purpose=normalized["purpose"],
                summary=None,
                estimated_person_months=normalized["estimated_person_months"],
                estimated_budget_amount=normalized["estimated_budget_amount"],
                approved_budget_amount=None,
                applicant_id=current_user.id,
                department_id=normalized["department_id"],
                status="department_pending",
                approval_stage="department_pending",
                rejection_comment=None,
                planned_start_date=normalized["planned_start_date"],
                planned_end_date=normalized["planned_end_date"],
                monthly_report_comment=None,
                final_rejected_at=None,
                approved_at=None,
                completed_at=None,
            )
            try:
                db.session.add(project)
                db.session.flush()

                db.session.add(
                    ProjectStatusLog(
                        project_id=project.id,
                        actor_id=current_user.id,
                        from_status=None,
                        to_status="department_pending",
                        action="submit",
                        comment=None,
                        acted_at=utc_now(),
                    )
                )

                managers = User.query.filter(
                    User.role == "manager",
                    User.department_id == normalized["department_id"],
                    User.is_active.is_(True),
                ).all()
                for manager in managers:
                    db.session.add(
                        Notification(
                            user_id=manager.id,
                            project_id=project.id,
                            type="department_pending",
                            message=f"新しい開発案件「{project.title}」が申請されました。内容を確認してください。",
                            is_read=False,
                        )
                    )

                if draft_to_delete is not None:
                    db.session.delete(draft_to_delete)

                db.session.commit()
                flash("案件を申請しました。承認状況はこの画面で確認できます。", "success")
                return redirect(url_for("applicant_project_status", project_id=project.id))
            except Exception:
                db.session.rollback()
                flash("申請処理に失敗しました。入力内容を確認して、もう一度お試しください。", "danger")

    if not departments:
        flash("申請に必要な部門データがありません。管理者に確認してください。", "danger")

    return render_template(
        "applicant_project_new.html",
        departments=departments,
        drafts=draft_records,
        drafts_json=drafts_json,
        draft_count=len(drafts_json),
        form_data=form_data,
        form_errors=form_errors,
        unread_notifications_count=get_unread_notifications_count(),
    )


@app.route("/applicant/project-drafts", methods=["POST"])
@login_required
def applicant_project_drafts_create():
    access_error = require_applicant()
    if access_error:
        return jsonify({"ok": False, "message": "この画面を表示する権限がありません。"}), 403

    payload = request.get_json(silent=True) or {}
    errors, normalized = validate_project_draft_form(payload)

    if normalized.get("department_id") is not None:
        exists = Department.query.filter_by(id=normalized["department_id"]).first()
        if exists is None:
            errors["department_id"] = "選択された部門が見つかりません。"

    if errors:
        return jsonify({"ok": False, "message": next(iter(errors.values()))}), 400

    draft = ProjectDraft(
        user_id=current_user.id,
        title=normalized["title"] or None,
        purpose=normalized["purpose"] or None,
        department_id=normalized["department_id"],
        estimated_budget_amount=normalized["estimated_budget_amount"],
        estimated_person_months=normalized["estimated_person_months"],
        planned_start_date=normalized["planned_start_date"],
        planned_end_date=normalized["planned_end_date"],
    )
    try:
        db.session.add(draft)
        db.session.flush()
        prune_old_project_drafts(current_user.id)
        db.session.commit()
    except Exception:
        db.session.rollback()
        return jsonify({"ok": False, "message": "下書き保存に失敗しました。"}), 500

    draft_records = (
        ProjectDraft.query.options(joinedload(ProjectDraft.department))
        .filter(ProjectDraft.user_id == current_user.id)
        .order_by(ProjectDraft.updated_at.desc(), ProjectDraft.id.desc())
        .limit(5)
        .all()
    )
    return jsonify(
        {"ok": True, "message": "下書きを保存しました", "drafts": [serialize_project_draft(d) for d in draft_records]}
    )


@app.route("/applicant/project-drafts/<int:draft_id>/delete", methods=["POST"])
@login_required
def applicant_project_drafts_delete(draft_id):
    access_error = require_applicant()
    if access_error:
        return jsonify({"ok": False, "message": "この画面を表示する権限がありません。"}), 403

    draft = ProjectDraft.query.filter_by(id=draft_id, user_id=current_user.id).first()
    if draft is None:
        return jsonify({"ok": False, "message": "対象の下書きが見つかりません。"}), 404

    try:
        db.session.delete(draft)
        db.session.commit()
    except Exception:
        db.session.rollback()
        return jsonify({"ok": False, "message": "下書き削除に失敗しました。"}), 500

    draft_records = (
        ProjectDraft.query.options(joinedload(ProjectDraft.department))
        .filter(ProjectDraft.user_id == current_user.id)
        .order_by(ProjectDraft.updated_at.desc(), ProjectDraft.id.desc())
        .limit(5)
        .all()
    )
    return jsonify(
        {"ok": True, "message": "下書きを削除しました", "drafts": [serialize_project_draft(d) for d in draft_records]}
    )


# =============================
# ■ 申請者：申請状況確認・管理画面
# =============================
@app.route("/applicant/projects/status")
@login_required
def applicant_project_status_index():
    access_error = require_applicant()
    if access_error:
        return access_error

    target_statuses = ("department_pending", "hq_pending", "rejected")
    latest_project = (
        Project.query.filter(
            Project.applicant_id == current_user.id,
            Project.status.in_(target_statuses),
        )
        .order_by(Project.created_at.desc(), Project.id.desc())
        .first()
    )

    if latest_project is None:
        flash("確認できる申請中・却下案件はありません。", "notice")
        return redirect(url_for("applicant_top"))

    return redirect(url_for("applicant_project_status", project_id=latest_project.id))


@app.route("/applicant/projects/<int:project_id>/status")
@login_required
def applicant_project_status(project_id):
    access_error = require_applicant()
    if access_error:
        return access_error

    target_statuses = ("department_pending", "hq_pending", "rejected")
    project = (
        Project.query.options(
            joinedload(Project.applicant),
            joinedload(Project.department),
            joinedload(Project.project_status_logs).joinedload(ProjectStatusLog.actor),
        )
        .filter(Project.id == project_id, Project.applicant_id == current_user.id)
        .first()
    )
    if project is None:
        flash("対象の案件が見つかりません。", "danger")
        return redirect(url_for("applicant_top"))
    if project.status not in target_statuses:
        flash("この画面で確認できる申請状況はありません。", "danger")
        return redirect(url_for("applicant_top"))

    switch_projects = (
        Project.query.filter(
            Project.applicant_id == current_user.id,
            Project.status.in_(target_statuses),
        )
        .order_by(Project.created_at.desc(), Project.id.desc())
        .all()
    )
    if not switch_projects:
        flash("確認できる申請中・却下案件はありません。", "danger")
        return redirect(url_for("applicant_top"))

    switcher_options = []
    status_label_map = {
        "department_pending": "部門承認待ち",
        "hq_pending": "本部承認待ち",
        "rejected": "却下（要修正）",
    }
    for item in switch_projects:
        switcher_options.append(
            {
                "project_id": item.id,
                "label": f"{item.title} — {status_label_map.get(item.status, item.status)}",
            }
        )

    return render_template(
        "applicant_project_status.html",
        status_view=build_project_status_view_data(project),
        switcher_options=switcher_options,
        switcher_count=len(switcher_options),
        unread_notifications_count=get_unread_notifications_count(),
    )


# =============================
# ■ 申請者：案件進捗管理画面
# =============================
@app.route("/applicant/projects/progress")
@login_required
def applicant_project_progress():
    access_error = require_applicant()
    if access_error:
        return access_error

    latest_project = (
        Project.query.filter(
            Project.applicant_id == current_user.id,
            Project.status == "in_progress",
            Project.approval_stage == "approved",
        )
        .order_by(Project.updated_at.desc(), Project.id.desc())
        .first()
    )
    if latest_project is None:
        return render_template(
            "applicant_project_progress_empty.html",
            unread_notifications_count=get_unread_notifications_count(),
        )
    return redirect(url_for("applicant_project_progress_detail", project_id=latest_project.id))


def get_applicant_progress_projects(user_id: int) -> list[Project]:
    """申請者本人の開発中案件一覧を表示順で取得する。"""
    return (
        Project.query.options(
            joinedload(Project.department),
            joinedload(Project.tasks),
            joinedload(Project.budget_actual_logs),
        )
        .filter(
            Project.applicant_id == user_id,
            Project.status == "in_progress",
            Project.approval_stage == "approved",
        )
        .order_by(Project.planned_end_date.is_(None), Project.planned_end_date.asc(), Project.id.asc())
        .all()
    )


def normalize_task_status_by_progress(progress_rate: int) -> str:
    """進捗率を正としてステータスを補正する。"""
    if progress_rate <= 0:
        return "not_started"
    if progress_rate >= 100:
        return "done"
    return "in_progress"


def is_all_tasks_done(tasks: list[Task]) -> bool:
    """全タスクが完了しているかを判定する。"""
    if not tasks:
        return False
    return all(task.status == "done" for task in tasks)


def should_notify_all_tasks_done(before_all_done: bool, after_all_done: bool, project: Project) -> bool:
    """全タスク完了通知が必要なケースかを判定する。"""
    return (
        (not before_all_done)
        and after_all_done
        and project.status == "in_progress"
        and len(project.tasks) > 0
    )


def build_applicant_progress_task_data(task: Task, idx: int, today: date, tomorrow: date) -> dict:
    """タスクカード表示用データを作る。"""
    due_display = "期限：未設定"
    due_class = ""
    overdue_flag = False
    if task.due_date:
        if task.status != "done" and task.due_date < today:
            overdue_days = (today - task.due_date).days
            due_display = f"期限：{format_business_date(task.due_date)}（{overdue_days}日超過）"
            due_class = "overdue-date"
            overdue_flag = True
        elif task.due_date == today:
            due_display = f"期限：{format_business_date(task.due_date)}（今日）"
            due_class = "today-date"
        elif task.due_date == tomorrow:
            due_display = f"期限：{format_business_date(task.due_date)}（明日）"
            due_class = "today-date"
        else:
            due_display = f"期限：{format_business_date(task.due_date)}"

    status_to_js = {"not_started": "notstarted", "in_progress": "progress", "done": "done"}
    status_to_btn = {"not_started": "active-notstarted", "in_progress": "active-progress", "done": "active-done"}

    card_classes = []
    if overdue_flag:
        card_classes.append("overdue")
    elif task.status == "in_progress":
        card_classes.append("in-progress")
    elif task.status == "done":
        card_classes.append("done-task")

    pct_color = "var(--app-prog-header)"
    if task.status == "done":
        pct_color = "var(--app-prog-success)"
    elif task.status == "not_started":
        pct_color = "var(--app-prog-muted)"
    slider_color = "var(--app-prog-header)"
    if task.status == "done":
        slider_color = "var(--app-prog-success)"
    elif task.status == "not_started":
        slider_color = "#cbd5e1"

    return {
        "id": task.id,
        "idx": idx,
        "task_id": task.id,
        "title": task.title,
        "assignee_name": task.assignee_name,
        "due_display": due_display,
        "due_class": due_class,
        "start_display": f"開始：{format_business_date(task.start_date)}" if task.start_date else "開始：未設定",
        "start_date_value": task.start_date.isoformat() if task.start_date else "",
        "due_date_value": task.due_date.isoformat() if task.due_date else "",
        "progress_rate": int(task.progress_rate),
        "status": task.status,
        "status_js": status_to_js.get(task.status, "notstarted"),
        "active_btn_class": status_to_btn.get(task.status, "active-notstarted"),
        "card_class": " ".join(card_classes),
        "overdue_flag": overdue_flag,
        "pct_color": pct_color,
        "slider_color": slider_color,
    }


def build_applicant_progress_view_data(project: Project, progress_projects: list[Project]) -> dict:
    """案件進捗管理画面の表示用データを作る。"""
    today = jst_today()
    tomorrow = today + timedelta(days=1)
    base_budget = project.approved_budget_amount if project.approved_budget_amount is not None else project.estimated_budget_amount
    base_budget = Decimal(base_budget or 0)
    current_actual = sum((Decimal(log.amount or 0) for log in project.budget_actual_logs), Decimal("0"))

    sorted_tasks = sorted(
        project.tasks,
        key=lambda t: (
            t.status == "done",
            t.due_date is None,
            t.due_date or date.max,
            t.id,
        ),
    )
    done_count = sum(1 for t in sorted_tasks if t.status == "done")
    total_count = len(sorted_tasks)
    avg_progress = round(sum((int(t.progress_rate) for t in sorted_tasks), 0) / total_count) if total_count else 0

    budget_pct = 0
    if base_budget > 0:
        budget_pct = int(round((current_actual / base_budget) * Decimal("100")))

    current_index = next((idx for idx, p in enumerate(progress_projects) if p.id == project.id), -1)
    prev_project_id = progress_projects[current_index - 1].id if current_index > 0 else None
    next_project_id = progress_projects[current_index + 1].id if 0 <= current_index < len(progress_projects) - 1 else None

    return {
        "project": project,
        "project_id": project.id,
        "project_name": project.title,
        "project_code": project.project_code,
        "department_name": project.department.name if project.department else "未設定",
        "planned_period_display": f"{format_business_date(project.planned_start_date)} ～ {format_business_date(project.planned_end_date)}",
        "overall_progress_pct": avg_progress,
        "done_count": done_count,
        "task_count": total_count,
        "budget_amount_display": format_decimal_amount(base_budget),
        "current_actual_display": format_decimal_amount(current_actual),
        "budget_pct": budget_pct,
        "budget_gauge_class": "gf-over" if budget_pct >= 100 else "gf-warn" if budget_pct >= 80 else "gf-ok",
        "budget_pct_color": "var(--app-prog-danger)" if budget_pct >= 100 else "var(--app-prog-warning)" if budget_pct >= 80 else "var(--app-prog-success)",
        "tasks": [build_applicant_progress_task_data(task, idx, today, tomorrow) for idx, task in enumerate(sorted_tasks)],
        "monthly_report_comment": project.monthly_report_comment or "",
        "previous_monthly_report_comment": project.monthly_report_comment or "",
        "report_month_label": f"{today.year}年{today.month}月",
        "today_iso": today.isoformat(),
        "current_position": current_index + 1 if current_index >= 0 else 0,
        "total_projects": len(progress_projects),
        "prev_project_id": prev_project_id,
        "next_project_id": next_project_id,
        "footer_project_name": project.title,
        "base_budget_amount": int(base_budget),
        "current_actual_amount": int(current_actual),
    }


def build_applicant_progress_switcher_data(projects: list[Project], current_project_id: int) -> list[dict]:
    """申請者向け案件切替サブヘッダーの表示データを作る。"""
    today = jst_today()
    items: list[dict] = []

    for project in projects:
        tasks = list(project.tasks or [])
        has_delay = any(task.status != "done" and task.due_date and task.due_date < today for task in tasks)

        base_budget = project.approved_budget_amount if project.approved_budget_amount is not None else project.estimated_budget_amount
        budget_base = Decimal(base_budget or 0)
        budget_actual = sum((Decimal(log.amount or 0) for log in project.budget_actual_logs), Decimal("0"))
        has_budget_alert = bool(budget_base > 0 and ((budget_actual / budget_base) * Decimal("100")) >= Decimal("80"))

        can_complete_wait = bool(
            tasks
            and project.status == "in_progress"
            and project.approval_stage == "approved"
            and all(task.status == "done" and int(task.progress_rate or 0) == 100 for task in tasks)
        )

        nearest_due_date = min(
            (task.due_date for task in tasks if task.status != "done" and task.due_date),
            default=date.max,
        )

        items.append(
            {
                "project_id": project.id,
                "title": project.title,
                "has_delay": has_delay,
                "has_budget_alert": has_budget_alert,
                "can_complete_wait": can_complete_wait,
                "nearest_due_date": nearest_due_date,
                "is_current": project.id == current_project_id,
            }
        )

    items.sort(
        key=lambda item: (
            0 if item["has_delay"] else 1,
            0 if item["has_budget_alert"] else 1,
            item["nearest_due_date"],
            1 if item["can_complete_wait"] else 0,
            item["project_id"],
        )
    )
    return items


def validate_applicant_progress_form(form_data, project: Project) -> tuple[list[str], dict]:
    """案件進捗管理画面のPOST値を検証する。"""
    errors: list[str] = []
    payload: dict = {
        "budget_actual_amount": None,
        "monthly_report_comment": (form_data.get("monthly_report_comment") or "").strip(),
        "task_updates": {},
    }

    if (form_data.get("confirmed") or "").strip() != "1":
        errors.append("確認モーダルで「更新する」を押してから実行してください。")
        return errors, payload

    if len(payload["monthly_report_comment"]) > 500:
        errors.append("月次進捗報告は500文字以内で入力してください。")
        return errors, payload

    budget_raw = (form_data.get("budget_actual_amount") or "").strip()
    if budget_raw:
        if not re.fullmatch(r"[0-9]+", budget_raw):
            errors.append("予算実績額は1円以上の半角数字で入力してください。")
            return errors, payload
        budget_value = int(budget_raw)
        if budget_value < 1 or budget_value > 999_999_999:
            errors.append("予算実績額は1〜999,999,999円の範囲で入力してください。")
            return errors, payload
        payload["budget_actual_amount"] = budget_value

    project_task_ids = {task.id for task in project.tasks}
    posted_task_ids: list[int] = []
    for raw_task_id in form_data.getlist("task_ids"):
        if not str(raw_task_id).isdigit():
            errors.append("タスク情報の送信内容が不正です。")
            return errors, payload
        posted_task_ids.append(int(raw_task_id))

    if len(posted_task_ids) != len(project_task_ids) or set(posted_task_ids) != project_task_ids:
        errors.append("タスク情報の送信内容が不正です。")
        return errors, payload

    allowed_statuses = {"not_started", "in_progress", "done"}
    for task_id in posted_task_ids:
        status_raw = (form_data.get(f"task_status_{task_id}") or "").strip()
        progress_raw = (form_data.get(f"task_progress_{task_id}") or "").strip()
        if status_raw not in allowed_statuses:
            errors.append("タスクステータスの指定が不正です。")
            return errors, payload
        if not re.fullmatch(r"-?[0-9]+", progress_raw):
            errors.append("タスク進捗率は整数で入力してください。")
            return errors, payload
        progress_rate = int(progress_raw)
        if progress_rate < 0 or progress_rate > 100:
            errors.append("タスク進捗率は0〜100の範囲で入力してください。")
            return errors, payload
        normalized_status = normalize_task_status_by_progress(progress_rate)
        payload["task_updates"][task_id] = {"status": normalized_status, "progress_rate": progress_rate}

    return errors, payload


def validate_applicant_task_modal_form(form_data):
    """案件進捗のタスク追加・編集モーダル入力を検証する。"""
    errors: list[str] = []
    title = (form_data.get("task_title") or "").strip()
    assignee_name = (form_data.get("task_assignee_name") or "").strip()
    start_date_raw = (form_data.get("task_start_date") or "").strip()
    due_date_raw = (form_data.get("task_due_date") or "").strip()

    start_date = None
    due_date = None

    if not title:
        errors.append("タスク名を入力してください。")
    elif len(title) > 200:
        errors.append("タスク名は200文字以内で入力してください。")

    if not assignee_name:
        errors.append("担当者名を入力してください。")
    elif len(assignee_name) > 100:
        errors.append("担当者名は100文字以内で入力してください。")

    if start_date_raw:
        start_date, start_date_err = parse_date_value(start_date_raw)
        if start_date_err:
            errors.append("日付の形式が正しくありません。")

    if not due_date_raw:
        errors.append("期限日を入力してください。")
    else:
        due_date, due_date_err = parse_date_value(due_date_raw)
        if due_date_err:
            errors.append("日付の形式が正しくありません。")

    if start_date and due_date and start_date > due_date:
        errors.append("開始日は期限日以前の日付にしてください。")

    normalized = {
        "title": title,
        "assignee_name": assignee_name,
        "start_date": start_date,
        "due_date": due_date,
    }
    return errors, normalized


@app.route("/applicant/projects/<int:project_id>/tasks/create", methods=["POST"])
@login_required
def applicant_project_task_create(project_id):
    access_error = require_applicant()
    if access_error:
        return jsonify({"ok": False, "message": "この案件ではタスクを追加できません。"}), 403

    project = (
        Project.query.filter(
            Project.id == project_id,
            Project.applicant_id == current_user.id,
            Project.status == "in_progress",
            Project.approval_stage == "approved",
        )
        .first()
    )
    if project is None:
        return jsonify({"ok": False, "message": "この案件ではタスクを追加できません。"}), 403

    errors, normalized = validate_applicant_task_modal_form(request.form)
    if errors:
        return jsonify({"ok": False, "message": errors[0]}), 400

    task = Task(
        project_id=project.id,
        title=normalized["title"],
        assignee_name=normalized["assignee_name"],
        start_date=normalized["start_date"],
        due_date=normalized["due_date"],
        status="not_started",
        progress_rate=0,
    )
    db.session.add(task)

    try:
        db.session.commit()
    except SQLAlchemyError:
        db.session.rollback()
        return jsonify({"ok": False, "message": "タスク追加に失敗しました。時間をおいてもう一度お試しください。"}), 500

    return jsonify(
        {
            "ok": True,
            "message": "タスクを追加しました。",
            "redirect_url": url_for("applicant_project_progress_detail", project_id=project.id),
        }
    )


@app.route("/applicant/projects/<int:project_id>/tasks/<int:task_id>/update", methods=["POST"])
@login_required
def applicant_project_task_update(project_id, task_id):
    access_error = require_applicant()
    if access_error:
        return jsonify({"ok": False, "message": "この案件ではタスクを編集できません。"}), 403

    project = (
        Project.query.filter(
            Project.id == project_id,
            Project.applicant_id == current_user.id,
            Project.status == "in_progress",
            Project.approval_stage == "approved",
        )
        .first()
    )
    if project is None:
        return jsonify({"ok": False, "message": "この案件ではタスクを編集できません。"}), 403

    task = Task.query.filter(Task.id == task_id, Task.project_id == project.id).first()
    if task is None:
        return jsonify({"ok": False, "message": "対象のタスクが見つかりません。"}), 404

    errors, normalized = validate_applicant_task_modal_form(request.form)
    if errors:
        return jsonify({"ok": False, "message": errors[0]}), 400

    task.title = normalized["title"]
    task.assignee_name = normalized["assignee_name"]
    task.start_date = normalized["start_date"]
    task.due_date = normalized["due_date"]

    try:
        db.session.commit()
    except SQLAlchemyError:
        db.session.rollback()
        return jsonify({"ok": False, "message": "タスク保存に失敗しました。時間をおいてもう一度お試しください。"}), 500

    return jsonify(
        {
            "ok": True,
            "message": "タスクを保存しました。",
            "redirect_url": url_for("applicant_project_progress_detail", project_id=project.id),
        }
    )


@app.route("/applicant/projects/<int:project_id>/tasks/<int:task_id>/delete", methods=["POST"])
@login_required
def applicant_project_task_delete(project_id, task_id):
    """申請者の進捗管理画面からタスクを削除する。"""
    access_error = require_applicant()
    if access_error:
        return jsonify({"ok": False, "message": "このタスクは削除できません。"}), 403

    project = (
        Project.query.filter(
            Project.id == project_id,
            Project.applicant_id == current_user.id,
            Project.status == "in_progress",
            Project.approval_stage == "approved",
        )
        .first()
    )
    if project is None:
        return jsonify({"ok": False, "message": "このタスクは削除できません。"}), 403

    task = Task.query.filter(Task.id == task_id, Task.project_id == project.id).first()
    if task is None:
        return jsonify({"ok": False, "message": "このタスクは削除できません。"}), 403

    task_count = Task.query.filter(Task.project_id == project.id).count()
    if task_count <= 1:
        return jsonify({"ok": False, "message": "最後の1件のタスクは削除できません。"}), 400

    try:
        db.session.delete(task)
        project.updated_at = utc_now()
        db.session.commit()
        flash("タスクを削除しました。", "success")
        return jsonify(
            {
                "ok": True,
                "message": "タスクを削除しました。",
                "redirect_url": url_for("applicant_project_progress_detail", project_id=project.id),
            }
        )
    except SQLAlchemyError:
        db.session.rollback()
        return jsonify({"ok": False, "message": "タスク削除に失敗しました。時間をおいてもう一度お試しください。"}), 500


@app.route("/applicant/projects/<int:project_id>/progress", methods=["GET", "POST"])
@login_required
def applicant_project_progress_detail(project_id):
    access_error = require_applicant()
    if access_error:
        return access_error

    progress_projects = get_applicant_progress_projects(current_user.id)
    project = (
        Project.query.options(
            joinedload(Project.department),
            joinedload(Project.tasks),
            joinedload(Project.budget_actual_logs),
        )
        .filter(
            Project.id == project_id,
            Project.applicant_id == current_user.id,
        )
        .first()
    )

    if project is None:
        flash("対象の案件が見つかりません。", "danger")
        return redirect(url_for("applicant_top"))
    if project.status != "in_progress" or project.approval_stage != "approved":
        flash("この画面で更新できる開発中案件ではありません。", "danger")
        return redirect(url_for("applicant_top"))

    if request.method == "POST":
        errors, payload = validate_applicant_progress_form(request.form, project)
        if errors:
            flash(errors[0], "danger")
            return redirect(url_for("applicant_project_progress_detail", project_id=project.id))

        before_all_done = is_all_tasks_done(project.tasks)
        changed = False

        if payload["budget_actual_amount"] is not None:
            changed = True
            db.session.add(
                BudgetActualLog(
                    project_id=project.id,
                    amount=Decimal(payload["budget_actual_amount"]),
                    memo="申請者の進捗管理画面から登録",
                    recorded_on=jst_today(),
                )
            )

        if (project.monthly_report_comment or "") != payload["monthly_report_comment"]:
            changed = True
            project.monthly_report_comment = payload["monthly_report_comment"]
            project.monthly_report_updated_at = utc_now()

        task_map = {task.id: task for task in project.tasks}
        for task_id, update_data in payload["task_updates"].items():
            task = task_map.get(task_id)
            if task is None:
                flash("タスク情報の送信内容が不正です。", "danger")
                return redirect(url_for("applicant_project_progress_detail", project_id=project.id))
            if task.status != update_data["status"] or int(task.progress_rate) != int(update_data["progress_rate"]):
                changed = True
                task.status = update_data["status"]
                task.progress_rate = int(update_data["progress_rate"])

        if not changed:
            flash("更新する変更はありません。", "warning")
            return redirect(url_for("applicant_project_progress_detail", project_id=project.id))

        try:
            project.updated_at = utc_now()
            after_all_done = is_all_tasks_done(project.tasks)
            if should_notify_all_tasks_done(before_all_done, after_all_done, project):
                managers = User.query.filter(
                    User.role == "manager",
                    User.department_id == project.department_id,
                    User.is_active.is_(True),
                ).all()
                for manager in managers:
                    db.session.add(
                        Notification(
                            user_id=manager.id,
                            project_id=project.id,
                            type="completed",
                            message=f"「{project.title}」の全タスクが完了しました。案件完了の確認を行ってください。",
                            is_read=False,
                            created_at=utc_now(),
                        )
                    )
            db.session.commit()
            flash("進捗情報を更新しました。", "success")
        except SQLAlchemyError:
            db.session.rollback()
            flash("進捗情報の更新に失敗しました。時間をおいてもう一度お試しください。", "danger")
        return redirect(url_for("applicant_project_progress_detail", project_id=project.id))

    view_data = build_applicant_progress_view_data(project, progress_projects)
    progress_switcher_projects = build_applicant_progress_switcher_data(progress_projects, project.id)
    return render_template(
        "applicant_project_progress.html",
        view_data=view_data,
        progress_switcher_projects=progress_switcher_projects,
        current_progress_project_id=project.id,
        login_success_toast=None,
        unread_notifications_count=get_unread_notifications_count(),
    )


# =============================
# ■ 部門管理者：トップ画面
# =============================
@app.route("/top/manager")
@login_required
def manager_top():
    access_error = require_manager()
    if access_error:
        return access_error

    view_data = build_manager_top_view_data(current_user.department_id)
    return render_template(
        "manager_top.html",
        view_data=view_data,
        unread_notifications_count=get_unread_notifications_count(),
    )


def _jst_date_from_datetime(dt: datetime | None) -> date | None:
    """UTC保存の日時をJST日付へ変換して返す。"""
    if dt is None:
        return None
    return dt.astimezone(ZoneInfo("Asia/Tokyo")).date()


def _get_latest_action_datetime(project: Project, action: str) -> datetime | None:
    """案件ログから指定actionの最新日時を返す。"""
    acted_ats = [log.acted_at for log in project.project_status_logs if log.action == action and log.acted_at is not None]
    return max(acted_ats) if acted_ats else None


def _build_manager_empty_top_view_data() -> dict:
    return {
        "summary": {
            "project_total": 0,
            "project_meta": "進行中0/完了0/申請中0",
            "approval_total": 0,
            "approval_wait3_total": 0,
            "completion_total": 0,
            "completion_wait3_total": 0,
            "high_load_total": 0,
            "over_load_total": 0,
            "load_total": 0,
            "delay_total": 0,
            "max_delay_days": 0,
            "budget_caution_total": 0,
            "budget_over_total": 0,
        },
        "review_requests": [],
        "completion_requests": [],
        "project_items": [],
        "resource_items": [],
        "resource_has_tasks": False,
        "budget": {
            "is_empty": True,
            "usage_percent": Decimal("0"),
            "usage_percent_value": 0.0,
            "used_arc_percent": 0.0,
            "over_arc_percent": 0.0,
            "usage_percent_display": "0%",
            "usage_class": "normal",
            "annual_budget_display": format_decimal_amount(Decimal("0")),
            "actual_display": format_decimal_amount(Decimal("0")),
            "over_display": format_decimal_amount(Decimal("0")),
            "remaining_display": format_decimal_amount(Decimal("0")),
        },
    }


def build_manager_top_view_data(department_id: int | None) -> dict:
    """部門管理者トップ画面の表示データをまとめて作成する。"""
    if not department_id:
        return _build_manager_empty_top_view_data()

    today = jst_today()
    fiscal_year = get_fiscal_year(today)
    fiscal_start = date(fiscal_year, 4, 1)
    fiscal_end = date(fiscal_year + 1, 3, 31)

    projects = (
        Project.query.options(
            joinedload(Project.tasks),
            joinedload(Project.applicant),
            joinedload(Project.budget_actual_logs),
            joinedload(Project.project_status_logs),
        )
        .filter(
            Project.department_id == department_id,
            Project.status != "rejected",
        )
        .all()
    )

    project_ids = [p.id for p in projects]
    manager_user_ids = [
        uid
        for (uid,) in db.session.query(User.id).filter(
            User.department_id == department_id,
            User.role == "manager",
        )
    ]

    completion_notifs = []
    if project_ids and manager_user_ids:
        completion_notifs = (
            Notification.query.filter(
                Notification.user_id.in_(manager_user_ids),
                Notification.project_id.in_(project_ids),
                Notification.type == "completed",
            )
            .all()
        )
    latest_completion_notif_by_project: dict[int, datetime] = {}
    for notif in completion_notifs:
        if notif.project_id is None or notif.created_at is None:
            continue
        prev = latest_completion_notif_by_project.get(notif.project_id)
        if prev is None or notif.created_at > prev:
            latest_completion_notif_by_project[notif.project_id] = notif.created_at

    in_progress_projects = [p for p in projects if p.status == "in_progress"]
    completed_projects = [p for p in projects if p.status == "completed"]
    pending_projects = [p for p in projects if p.status in {"department_pending", "hq_pending"}]

    review_requests = []
    approval_wait3_total = 0
    for p in projects:
        if not (p.status == "department_pending" and p.approval_stage == "department_pending"):
            continue
        submitted_at = _get_manager_review_submitted_at(p)
        submitted_jst_date = _jst_date_from_datetime(submitted_at)
        wait_days = (today - submitted_jst_date).days if submitted_jst_date else 0
        if wait_days >= 3:
            approval_wait3_total += 1
        review_requests.append(
            {
                "project_id": p.id,
                "submitted_date": format_jst_date(submitted_at, "%m/%d") if submitted_at else "—",
                "submitted_sort_key": submitted_at or p.created_at,
                "project_name": p.title,
                "applicant_name": p.applicant.display_name if p.applicant else "—",
                "budget_display": format_decimal_amount(Decimal(p.estimated_budget_amount or 0)),
                "is_waiting_long": wait_days >= 3,
                "status_label": f"{wait_days}日待機" if wait_days >= 3 else "部門承認待ち",
            }
        )
    review_requests.sort(key=lambda item: (item["submitted_sort_key"], item["project_id"]))
    for item in review_requests:
        item.pop("submitted_sort_key", None)

    completion_requests = []
    completion_wait3_total = 0
    for p in in_progress_projects:
        task_total = len(p.tasks)
        done_count = sum(1 for task in p.tasks if task.status == "done")
        if task_total == 0 or done_count != task_total:
            continue
        request_at = latest_completion_notif_by_project.get(p.id) or p.updated_at
        request_jst_date = _jst_date_from_datetime(request_at)
        wait_days = (today - request_jst_date).days if request_jst_date else 0
        if wait_days >= 3:
            completion_wait3_total += 1
        budget_rate = p.budget_consumption_rate or Decimal("0")
        completion_requests.append(
            {
                "project_id": p.id,
                "request_date": format_jst_date(request_at, "%m/%d") if request_at else "—",
                "request_sort_key": request_at or p.updated_at or p.created_at,
                "project_name": p.title,
                "owner_name": p.applicant.display_name if p.applicant else "—",
                "budget_rate_value": float(budget_rate),
                "budget_rate_display": f"{format_percent_value(budget_rate)}%",
            }
        )
    # 完了認定依頼も、待機が長いものから確認できるよう依頼日が古い順に並べる
    completion_requests.sort(key=lambda item: (item["request_sort_key"], item["project_id"]))
    for item in completion_requests:
        item.pop("request_sort_key", None)

    delay_project_ids: set[int] = set()
    max_delay_days = 0
    for p in in_progress_projects:
        has_delay = False
        for task in p.tasks:
            if task.due_date and task.status != "done" and task.due_date < today:
                has_delay = True
                max_delay_days = max(max_delay_days, (today - task.due_date).days)
        if has_delay:
            delay_project_ids.add(p.id)

    budget_caution_total = 0
    budget_over_total = 0
    budget_state_by_project: dict[int, str] = {}
    for p in in_progress_projects:
        rate = p.budget_consumption_rate or Decimal("0")
        if rate >= Decimal("100"):
            budget_over_total += 1
            budget_state_by_project[p.id] = "over"
        elif rate >= Decimal("80"):
            budget_caution_total += 1
            budget_state_by_project[p.id] = "warn"
        else:
            budget_state_by_project[p.id] = "ok"

    project_items = []
    for p in projects:
        if p.status not in {"in_progress", "completed"} or p.approval_stage != "approved":
            continue
        total_tasks = len(p.tasks)
        done_tasks = sum(1 for task in p.tasks if task.status == "done")
        progress_pct = int((done_tasks / total_tasks) * 100) if total_tasks else 0
        progress_width = min(max(progress_pct, 0), 100)
        budget_rate = p.budget_consumption_rate or Decimal("0")
        budget_pct = float(budget_rate)
        budget_width = min(max(budget_pct, 0), 100)
        is_completion_waiting = p.status == "in_progress" and total_tasks > 0 and done_tasks == total_tasks
        is_delayed = p.id in delay_project_ids
        budget_state = budget_state_by_project.get(p.id, "ok")

        status_labels = []
        if p.status == "completed":
            status_labels.append({"label": "完了", "class": "bp-done bp-done-outline"})
        else:
            if is_completion_waiting:
                status_labels.append({"label": "完了認定待ち", "class": "bp-done"})
            if is_delayed:
                status_labels.append({"label": "遅延", "class": "bp-delay"})
            if budget_state == "over":
                status_labels.append({"label": "予算超過", "class": "bp-delay"})
            elif budget_state == "warn":
                status_labels.append({"label": "予算注意", "class": "bp-budget"})
            if not status_labels:
                status_labels.append({"label": "進行中", "class": "bp-prog"})

        if p.status == "completed" or is_completion_waiting or progress_pct >= 100:
            progress_class = "gmf-ok"
            progress_text_class = "gmp-ok"
        elif is_delayed:
            progress_class = "gmf-danger"
            progress_text_class = "gmp-danger"
        else:
            progress_class = "gmf-purple"
            progress_text_class = "gmp-purple"

        if budget_pct >= 100:
            budget_class = "gmf-danger"
            budget_text_class = "gmp-danger"
        elif budget_pct >= 80:
            budget_class = "gmf-warn"
            budget_text_class = "gmp-warn"
        else:
            budget_class = "gmf-ok"
            budget_text_class = "gmp-ok"

        if p.status == "completed":
            sort_priority = 5
        elif is_completion_waiting:
            sort_priority = 0
        elif is_delayed:
            sort_priority = 1
        elif budget_state == "over":
            sort_priority = 2
        elif budget_state == "warn":
            sort_priority = 3
        else:
            sort_priority = 4

        project_items.append(
            {
                "project_id": p.id,
                "project_name": p.title,
                "owner_name": p.applicant.display_name if p.applicant else "—",
                "status": p.status,
                "is_completed": p.status == "completed",
                "status_labels": status_labels,
                "progress_pct": progress_pct,
                "progress_width": progress_width,
                "progress_class": progress_class,
                "progress_text_class": progress_text_class,
                "budget_pct": budget_pct,
                "budget_display": f"{format_percent_value(budget_rate)}%",
                "budget_width": budget_width,
                "budget_class": budget_class,
                "budget_text_class": budget_text_class,
                "is_delayed": is_delayed,
                "sort_priority": sort_priority,
                "updated_at": p.updated_at or p.created_at,
            }
        )

    project_items.sort(
        key=lambda item: (
            item["sort_priority"],
            -(item["updated_at"].timestamp() if item["updated_at"] else 0),
            -item["project_id"],
        )
    )

    applicants = (
        User.query.filter(
            User.department_id == department_id,
            User.role == "applicant",
            User.is_active.is_(True),
        )
        .order_by(User.id.asc())
        .all()
    )
    active_applicant_names = {u.display_name for u in applicants}
    resource_map: dict[str, dict] = {
        u.display_name: {
            "user_id": u.id,
            "member_name": u.display_name,
            "not_done_count": 0,
            "in_progress_count": 0,
            "delayed_count": 0,
            "not_started_count": 0,
        }
        for u in applicants
    }
    for p in in_progress_projects:
        for t in p.tasks:
            if t.status == "done" or t.assignee_name not in active_applicant_names:
                continue
            row = resource_map[t.assignee_name]
            row["not_done_count"] += 1
            is_delayed_task = bool(t.due_date and t.status != "done" and t.due_date < today)
            if is_delayed_task:
                row["delayed_count"] += 1
            elif t.status == "not_started":
                row["not_started_count"] += 1
            elif t.status == "in_progress":
                row["in_progress_count"] += 1

    resource_items = []
    high_load_total = 0
    over_load_total = 0
    for name, row in resource_map.items():
        count = row["not_done_count"]
        if count >= 9:
            load_class = "mbf-over"
            load_label = "過負荷"
            over_load_total += 1
        elif count >= 6:
            load_class = "mbf-high"
            load_label = "高負荷"
            high_load_total += 1
        elif count >= 3:
            load_class = "mbf-mid"
            load_label = "適正"
        else:
            load_class = "mbf-low"
            load_label = "余裕あり"
        load_width = min((count / 9) * 100, 100) if count > 0 else 0
        resource_items.append(
            {
                "user_id": row["user_id"],
                "member_name": name,
                "not_done_count": count,
                "load_label": load_label,
                "load_class": load_class,
                "load_width": load_width,
                "in_progress_count": row["in_progress_count"],
                "delayed_count": row["delayed_count"],
                "not_started_count": row["not_started_count"],
            }
        )
    resource_items.sort(key=lambda item: (-item["not_done_count"], -item["delayed_count"], item["user_id"]))
    resource_has_tasks = any(item["not_done_count"] > 0 for item in resource_items)

    yearly_budget = (
        DepartmentYearlyBudget.query.filter(
            DepartmentYearlyBudget.department_id == department_id,
            DepartmentYearlyBudget.fiscal_year == fiscal_year,
        )
        .first()
    )
    annual_budget = Decimal(yearly_budget.annual_budget_amount or 0) if yearly_budget else Decimal("0")
    actual_sum = (
        db.session.query(func.coalesce(func.sum(BudgetActualLog.amount), 0))
        .join(Project, Project.id == BudgetActualLog.project_id)
        .filter(
            Project.department_id == department_id,
            BudgetActualLog.recorded_on >= fiscal_start,
            BudgetActualLog.recorded_on <= fiscal_end,
        )
        .scalar()
    )
    actual_amount = Decimal(actual_sum or 0)
    usage_percent = ((actual_amount / annual_budget) * Decimal("100")) if annual_budget > 0 else Decimal("0")
    over_amount = max(actual_amount - annual_budget, Decimal("0")) if annual_budget > 0 else Decimal("0")
    remaining_amount = max(annual_budget - actual_amount, Decimal("0")) if annual_budget > 0 else Decimal("0")
    usage_class = "danger" if usage_percent >= Decimal("100") else ("warn" if usage_percent >= Decimal("80") else "normal")
    usage_percent_value = float(max(usage_percent, Decimal("0")))
    used_arc_percent = float(min(max(usage_percent, Decimal("0")), Decimal("100")))
    over_arc_percent = float(min(max(usage_percent - Decimal("100"), Decimal("0")), Decimal("100")))

    return {
        "summary": {
            "project_total": len(projects),
            "project_meta": f"進行中{len(in_progress_projects)}/完了{len(completed_projects)}/申請中{len(pending_projects)}",
            "approval_total": len(review_requests),
            "approval_wait3_total": approval_wait3_total,
            "completion_total": len(completion_requests),
            "completion_wait3_total": completion_wait3_total,
            "high_load_total": high_load_total,
            "over_load_total": over_load_total,
            "load_total": high_load_total + over_load_total,
            "delay_total": len(delay_project_ids),
            "max_delay_days": max_delay_days,
            "budget_caution_total": budget_caution_total,
            "budget_over_total": budget_over_total,
        },
        "review_requests": review_requests,
        "completion_requests": completion_requests,
        "project_items": project_items,
        "resource_items": resource_items,
        "resource_has_tasks": resource_has_tasks,
        "budget": {
            "is_empty": annual_budget <= 0,
            "usage_percent": usage_percent,
            "usage_percent_value": usage_percent_value,
            "used_arc_percent": used_arc_percent,
            "over_arc_percent": over_arc_percent,
            "usage_percent_display": f"{format_percent_value(usage_percent)}%",
            "usage_class": usage_class,
            "annual_budget_display": format_decimal_amount(annual_budget),
            "actual_display": format_decimal_amount(actual_amount),
            "over_display": format_decimal_amount(over_amount),
            "remaining_display": format_decimal_amount(remaining_amount),
        },
    }


# =============================
# ■ 部門管理者：承認審査画面
# =============================
def create_notification(user_id: int, project_id: int | None, notif_type: str, message: str):
    db.session.add(
        Notification(
            user_id=user_id,
            project_id=project_id,
            type=notif_type,
            message=message,
            is_read=False,
            created_at=utc_now(),
        )
    )


def _get_latest_submit_log(project: Project) -> ProjectStatusLog | None:
    submit_logs = [log for log in project.project_status_logs if log.action == "submit"]
    if not submit_logs:
        return None
    return max(submit_logs, key=lambda log: (log.acted_at, log.id))


def _get_manager_review_submitted_at(project: Project) -> datetime | None:
    """部門承認待ち案件の申請起算日を返す。"""
    submit_log = _get_latest_submit_log(project)
    return (submit_log.acted_at if submit_log else None) or project.created_at


def get_manager_review_projects(department_id: int) -> list[Project]:
    projects = (
        Project.query.options(
            joinedload(Project.applicant),
            joinedload(Project.department),
            joinedload(Project.project_status_logs).joinedload(ProjectStatusLog.actor),
        )
        .filter(
            Project.department_id == department_id,
            Project.status == "department_pending",
            Project.approval_stage == "department_pending",
        )
        .all()
    )
    projects.sort(
        key=lambda project: (
            _get_manager_review_submitted_at(project) or project.created_at,
            project.id,
        )
    )
    return projects


def find_next_manager_review_project(department_id: int, exclude_project_id: int | None = None) -> Project | None:
    projects = get_manager_review_projects(department_id)
    for project in projects:
        if exclude_project_id is None or project.id != exclude_project_id:
            return project
    return None


def build_department_budget_simulation(project: Project) -> dict:
    fiscal_year = get_fiscal_year(project.planned_start_date)
    fiscal_start = date(fiscal_year, 4, 1)
    fiscal_end = date(fiscal_year + 1, 3, 31)

    yearly_budget = (
        DepartmentYearlyBudget.query.filter_by(
            department_id=project.department_id,
            fiscal_year=fiscal_year,
        ).first()
    )
    annual_budget = Decimal(yearly_budget.annual_budget_amount or 0) if yearly_budget else Decimal("0")

    actual_sum = (
        db.session.query(func.coalesce(func.sum(BudgetActualLog.amount), 0))
        .join(Project, Project.id == BudgetActualLog.project_id)
        .filter(
            Project.department_id == project.department_id,
            Project.planned_start_date >= fiscal_start,
            Project.planned_start_date <= fiscal_end,
            Project.status != "rejected",
        )
        .scalar()
    )
    actual_amount = Decimal(actual_sum or 0)
    this_project_amount = Decimal(project.estimated_budget_amount or 0)
    remaining_amount = annual_budget - actual_amount - this_project_amount

    consume_rate = Decimal("0")
    occupy_rate = Decimal("0")
    remaining_rate = Decimal("0")
    if annual_budget > 0:
        consume_rate = ((actual_amount + this_project_amount) / annual_budget) * Decimal("100")
        occupy_rate = (this_project_amount / annual_budget) * Decimal("100")
        remaining_rate = (remaining_amount / annual_budget) * Decimal("100")

    if annual_budget <= 0 or remaining_amount < 0:
        result_class = "danger"
    elif consume_rate >= Decimal("80"):
        result_class = "warn"
    else:
        result_class = "ok"

    consume_rate_class = "ibv-ok"
    remaining_amount_class = "ibv-ok"
    if result_class == "danger":
        consume_rate_class = "ibv-danger"
        remaining_amount_class = "ibv-danger"
    elif result_class == "warn":
        consume_rate_class = "ibv-warn"
        remaining_amount_class = "ibv-warn"

    if occupy_rate >= Decimal("30"):
        occupy_rate_class = "ibv-danger"
    elif occupy_rate >= Decimal("20"):
        occupy_rate_class = "ibv-warn"
    else:
        occupy_rate_class = "ibv-ok"

    remaining_amount_display = format_decimal_amount(remaining_amount)
    remaining_result_display = remaining_amount_display
    if remaining_amount < 0:
        remaining_amount_display = f"-{format_decimal_amount(abs(remaining_amount))}"
        remaining_result_display = remaining_amount_display

    consume_rate_display = format_percent_value(consume_rate)
    occupy_rate_display = format_percent_value(occupy_rate)
    remaining_rate_display = format_percent_value(remaining_rate)

    if result_class == "ok":
        result_title = f"承認後の予算残高：{remaining_result_display}（{remaining_rate_display}%）"
        result_message = "本案件を承認しても、部門年間予算には十分な残余があります。"
    elif result_class == "warn":
        result_title = f"承認後の予算残高：{remaining_result_display}（{remaining_rate_display}%）"
        result_message = f"本案件を承認すると予算消化率が{consume_rate_display}%になります。年度内の追加申請に備え、残高を確認してください。"
    else:
        result_title = f"承認後の予算残高：{remaining_result_display}（予算超過）"
        result_message = "本案件を承認すると部門年間予算を超過します。本部承認前に予算調整が必要です。"

    if annual_budget > 0:
        axis_labels = []
        for pct in [0, 25, 50, 75, 100]:
            if pct == 0:
                axis_labels.append("0")
                continue
            amount = (annual_budget * Decimal(pct)) / Decimal("100")
            man_yen = int(amount / Decimal("10000"))
            axis_labels.append(f"{pct}%（{man_yen:,}万円）")
    else:
        axis_labels = ["0", "25%", "50%", "75%", "100%"]

    return {
        "annual_budget_display": format_decimal_amount(annual_budget),
        "actual_amount_display": format_decimal_amount(actual_amount),
        "this_project_amount_display": format_decimal_amount(this_project_amount),
        "remaining_amount_display": remaining_amount_display,
        "remaining_result_display": remaining_result_display,
        "consume_rate": consume_rate_display,
        "occupy_rate": occupy_rate_display,
        "remaining_rate": remaining_rate_display,
        "seg_used": float(max(Decimal("0"), min(Decimal("100"), (actual_amount / annual_budget * Decimal("100")) if annual_budget > 0 else Decimal("0")))),
        "seg_this": float(max(Decimal("0"), min(Decimal("100"), (this_project_amount / annual_budget * Decimal("100")) if annual_budget > 0 else Decimal("0")))),
        "seg_remaining": float(max(Decimal("0"), min(Decimal("100"), (remaining_amount / annual_budget * Decimal("100")) if annual_budget > 0 else Decimal("0")))),
        "result_class": result_class,
        "result_title": result_title,
        "result_message": result_message,
        "consume_rate_class": consume_rate_class,
        "remaining_amount_class": remaining_amount_class,
        "occupy_rate_class": occupy_rate_class,
        "axis_labels": axis_labels,
    }


def build_manager_review_view_data(
    project: Project,
    queue_projects: list[Project],
    rejection_comment: str = "",
    force_reject_mode: bool = False,
) -> dict:
    today = jst_today()
    submitted_at = _get_manager_review_submitted_at(project)
    submitted_jst_date = _jst_date_from_datetime(submitted_at)
    waiting_days = (today - submitted_jst_date).days if submitted_jst_date else 0

    current_index = next((idx for idx, p in enumerate(queue_projects) if p.id == project.id), 0)
    total_count = len(queue_projects)
    prev_project_id = queue_projects[current_index - 1].id if current_index > 0 else None
    next_project_id = queue_projects[current_index + 1].id if current_index < total_count - 1 else None

    queue_slice_start = max(0, current_index - 1)
    queue_slice_end = min(total_count, queue_slice_start + 4)
    queue_slice_start = max(0, queue_slice_end - 4)
    queue_slice = queue_projects[queue_slice_start:queue_slice_end]

    queue_items = []
    for idx, item in enumerate(queue_slice, start=queue_slice_start + 1):
        item_submitted = _get_manager_review_submitted_at(item)
        item_submitted_jst_date = _jst_date_from_datetime(item_submitted)
        item_wait_days = (today - item_submitted_jst_date).days if item_submitted_jst_date else 0
        queue_items.append(
            {
                "project_id": item.id,
                "index": idx,
                "title": item.title,
                "submitted_date": format_jst_date(item_submitted, "%m/%d") if item_submitted else "—",
                "is_current": item.id == project.id,
                "wait_badge_text": f"{item_wait_days}日待機" if item_wait_days >= 3 else "",
            }
        )

    budget_sim = build_department_budget_simulation(project)
    fiscal_year = get_fiscal_year(project.planned_start_date)
    fiscal_start = date(fiscal_year, 4, 1)
    fiscal_end = date(fiscal_year + 1, 3, 31)
    dept_project_amounts = (
        db.session.query(Project.id, Project.estimated_budget_amount, Project.approved_budget_amount)
        .filter(
            Project.department_id == project.department_id,
            Project.planned_start_date >= fiscal_start,
            Project.planned_start_date <= fiscal_end,
            Project.status != "rejected",
        )
        .all()
    )
    sorted_by_amount = sorted(
        dept_project_amounts,
        key=lambda row: Decimal(
            row.approved_budget_amount if row.approved_budget_amount is not None else (row.estimated_budget_amount or 0)
        ),
        reverse=True,
    )
    rank_map = {row.id: idx + 1 for idx, row in enumerate(sorted_by_amount)}
    budget_rank = rank_map.get(project.id, 1)
    department_project_count = len(sorted_by_amount)

    return {
        "project_id": project.id,
        "project_name": project.title or "—",
        "project_code": project.project_code or "—",
        "purpose": project.purpose or "—",
        "applicant_name": project.applicant.display_name if project.applicant else "—",
        "department_name": project.department.name if project.department else "—",
        "submitted_date": format_jst_date(submitted_at),
        "submitted_date_ja": format_jst_date_ja(submitted_at),
        "wait_badge_text": f"{waiting_days}日待機" if waiting_days >= 3 else "",
        "estimated_budget_display": format_decimal_amount(Decimal(project.estimated_budget_amount or 0)),
        "estimated_person_months_display": format_person_months(project.estimated_person_months),
        "planned_period_display": f"{format_business_date(project.planned_start_date)} ～ {format_business_date(project.planned_end_date)}",
        "queue_position": current_index + 1,
        "queue_total_count": total_count,
        "prev_project_id": prev_project_id,
        "next_project_id": next_project_id,
        "queue_items": queue_items,
        "queue_total_label": f"審査待ち案件（{total_count}件）",
        "budget_rank": budget_rank,
        "department_project_count": department_project_count,
        "budget_rank_subtext": f"{project.department.name if project.department else '—'} {department_project_count}件中（審査中も含む）",
        "budget_simulation": budget_sim,
        "rejection_comment": rejection_comment,
        "initial_verdict": "reject" if force_reject_mode else "approve",
    }


@app.route("/manager/projects/review")
@login_required
def manager_project_review_entry():
    access_error = require_manager()
    if access_error:
        return access_error

    queue_projects = get_manager_review_projects(current_user.department_id)
    if not queue_projects:
        return render_template(
            "manager_project_review_empty.html",
            unread_notifications_count=get_unread_notifications_count(),
        )
    return redirect(url_for("manager_project_review", project_id=queue_projects[0].id))


@app.route("/manager/projects/<int:project_id>/review", methods=["GET", "POST"])
@login_required
def manager_project_review(project_id: int):
    access_error = require_manager()
    if access_error:
        return access_error

    project = (
        Project.query.options(
            joinedload(Project.applicant),
            joinedload(Project.department),
            joinedload(Project.project_status_logs).joinedload(ProjectStatusLog.actor),
        )
        .filter(Project.id == project_id)
        .first()
    )
    if project is None:
        flash("指定された案件が見つかりません。", "danger")
        return redirect(url_for("manager_top"))
    if project.department_id != current_user.department_id:
        flash("この案件を審査する権限がありません。", "danger")
        return redirect(url_for("manager_top"))

    queue_projects = get_manager_review_projects(current_user.department_id)
    is_pending_target = (
        project.status == "department_pending"
        and project.approval_stage == "department_pending"
    )

    if request.method == "GET":
        if not is_pending_target:
            flash("この案件は現在、部門承認の対象ではありません。", "danger")
            return redirect(url_for("manager_top"))

        review_data = build_manager_review_view_data(project, queue_projects)
        return render_template(
            "manager_project_review.html",
            review_data=review_data,
            unread_notifications_count=get_unread_notifications_count(),
        )

    action = (request.form.get("action") or "").strip()
    confirmed = (request.form.get("confirmed") or "").strip()
    rejection_comment = (request.form.get("rejection_comment") or "").strip()

    if action not in {"approve", "reject"}:
        flash("不正な操作が行われました。もう一度操作してください。", "danger")
        return redirect(url_for("manager_project_review", project_id=project_id))
    if confirmed != "1":
        flash("確認操作が完了していません。もう一度操作してください。", "danger")
        return redirect(url_for("manager_project_review", project_id=project_id))

    if not is_pending_target:
        flash("この案件はすでに審査済みです。", "warning")
        next_project = find_next_manager_review_project(current_user.department_id, exclude_project_id=project.id)
        if next_project:
            return redirect(url_for("manager_project_review", project_id=next_project.id))
        return redirect(url_for("manager_top"))

    if action == "reject":
        if not rejection_comment:
            flash("却下理由は必須です。コメントを入力してください。", "danger")
            review_data = build_manager_review_view_data(
                project,
                queue_projects,
                rejection_comment=rejection_comment,
                force_reject_mode=True,
            )
            return render_template(
                "manager_project_review.html",
                review_data=review_data,
                unread_notifications_count=get_unread_notifications_count(),
            )
        if len(rejection_comment) > 500:
            flash("却下理由は500文字以内で入力してください。", "danger")
            review_data = build_manager_review_view_data(
                project,
                queue_projects,
                rejection_comment=rejection_comment,
                force_reject_mode=True,
            )
            return render_template(
                "manager_project_review.html",
                review_data=review_data,
                unread_notifications_count=get_unread_notifications_count(),
            )

    try:
        if action == "approve":
            project.status = "hq_pending"
            project.approval_stage = "hq_pending"
            project.rejection_comment = None
            project.final_rejected_at = None

            db.session.add(
                ProjectStatusLog(
                    project_id=project.id,
                    actor_id=current_user.id,
                    from_status="department_pending",
                    to_status="hq_pending",
                    action="approve_department",
                    comment=None,
                    acted_at=utc_now(),
                )
            )

            hq_users = User.query.filter_by(role="hq", is_active=True).all()
            for user in hq_users:
                if user.id == current_user.id:
                    continue
                create_notification(
                    user_id=user.id,
                    project_id=project.id,
                    notif_type="hq_pending",
                    message=f"部門承認済み案件「{project.title}」が本部承認待ちになりました。",
                )

            if project.applicant_id != current_user.id:
                create_notification(
                    user_id=project.applicant_id,
                    project_id=project.id,
                    notif_type="hq_pending",
                    message=f"申請した案件「{project.title}」が部門承認を通過しました。本部承認待ちです。",
                )

            db.session.commit()
            flash(f"「{project.title}」を承認し、本部管理者へ送付しました。", "success")
        else:
            project.status = "rejected"
            project.approval_stage = "rejected"
            project.rejection_comment = rejection_comment
            project.final_rejected_at = utc_now()

            db.session.add(
                ProjectStatusLog(
                    project_id=project.id,
                    actor_id=current_user.id,
                    from_status="department_pending",
                    to_status="rejected",
                    action="reject_department",
                    comment=rejection_comment,
                    acted_at=utc_now(),
                )
            )

            if project.applicant_id != current_user.id:
                create_notification(
                    user_id=project.applicant_id,
                    project_id=project.id,
                    notif_type="rejected",
                    message=f"申請した案件「{project.title}」が部門審査で却下されました。理由を確認してください。",
                )

            db.session.commit()
            flash(f"「{project.title}」を却下し、申請者へ通知しました。", "success")

    except SQLAlchemyError:
        db.session.rollback()
        flash("審査処理に失敗しました。時間をおいて再度お試しください。", "danger")
        review_data = build_manager_review_view_data(
            project,
            queue_projects,
            rejection_comment=rejection_comment if action == "reject" else "",
            force_reject_mode=(action == "reject"),
        )
        return render_template(
            "manager_project_review.html",
            review_data=review_data,
            unread_notifications_count=get_unread_notifications_count(),
        )

    next_project = find_next_manager_review_project(current_user.department_id, exclude_project_id=project.id)
    if next_project:
        return redirect(url_for("manager_project_review", project_id=next_project.id))
    return redirect(url_for("manager_project_review_entry"))


# =============================
# ■ 部門管理者：案件モニタリング画面
# =============================
def is_manager_monitoring_project_complete_ready(project: Project) -> bool:
    """完了認定可能な案件かを判定する。"""
    if project.status != "in_progress" or project.approval_stage != "approved":
        return False
    tasks = list(project.tasks or [])
    if not tasks:
        return False
    return all(task.status == "done" and int(task.progress_rate or 0) == 100 for task in tasks)


def _get_monitoring_budget_metrics(project: Project) -> dict:
    base_budget = project.approved_budget_amount if project.approved_budget_amount is not None else project.estimated_budget_amount
    budget_base = Decimal(base_budget or 0)
    actual_total = sum((Decimal(log.amount or 0) for log in project.budget_actual_logs), Decimal("0"))
    budget_pct = 0
    if budget_base > 0:
        budget_pct = int(round((actual_total / budget_base) * Decimal("100")))
    return {
        "budget_base": budget_base,
        "actual_total": actual_total,
        "budget_pct": max(0, budget_pct),
    }


def _get_monitoring_overdue_metrics(project: Project, today: date) -> dict:
    overdue_tasks = [task for task in project.tasks if task.status != "done" and task.due_date and task.due_date < today]
    max_overdue_days = max(((today - task.due_date).days for task in overdue_tasks), default=0)
    return {
        "overdue_count": len(overdue_tasks),
        "max_overdue_days": max_overdue_days,
    }


def _get_monitoring_last_progress_metrics(project: Project, today: date) -> dict:
    candidate_timestamps = [
        project.updated_at,
        project.monthly_report_updated_at,
        max((log.created_at for log in project.budget_actual_logs if log.created_at), default=None),
    ]
    latest_updated_at = max((dt for dt in candidate_timestamps if dt is not None), default=None)
    if latest_updated_at is None:
        return {
            "is_initial": True,
            "days_since": None,
            "display_label": "未更新",
            "display_sub": "開発開始後、進捗更新はまだありません",
            "display_meta": "開発開始後",
            "is_stale": False,
        }

    updated_jst_date = latest_updated_at.astimezone(ZoneInfo("Asia/Tokyo")).date()
    days_since = (today - updated_jst_date).days
    if days_since <= 0:
        label = "本日"
    elif days_since == 1:
        label = "1日前"
    else:
        label = f"{days_since}日前"
    return {
        "is_initial": False,
        "days_since": days_since,
        "display_label": label,
        "display_sub": f"{format_jst_date(latest_updated_at)} 更新",
        "display_meta": f"{project.applicant.display_name if project.applicant else '主担当未設定'}・{format_jst_date(latest_updated_at)}",
        "is_stale": days_since >= 3,
    }


def _get_monitoring_latest_due_date(project: Project) -> date | None:
    incomplete_due_dates = [task.due_date for task in project.tasks if task.status != "done" and task.due_date]
    if not incomplete_due_dates:
        return None
    return max(incomplete_due_dates)


def get_manager_monitoring_sort_key(project: Project):
    """モニタリング案件一覧の優先順キーを返す。"""
    today = jst_today()
    can_complete = is_manager_monitoring_project_complete_ready(project)
    overdue_metrics = _get_monitoring_overdue_metrics(project, today)
    budget_metrics = _get_monitoring_budget_metrics(project)
    last_progress_metrics = _get_monitoring_last_progress_metrics(project, today)
    latest_due_date = _get_monitoring_latest_due_date(project)
    return (
        0 if can_complete else 1,
        0 if overdue_metrics["overdue_count"] > 0 else 1,
        0 if budget_metrics["budget_pct"] >= 80 else 1,
        0 if last_progress_metrics["is_stale"] else 1,
        latest_due_date or date.max,
        project.id,
    )


def get_manager_monitoring_projects(department_id: int) -> list[Project]:
    """部門管理者向けに自部門の開発中案件を優先順で取得する。"""
    projects = (
        Project.query.options(
            joinedload(Project.applicant),
            joinedload(Project.department),
            joinedload(Project.tasks),
            joinedload(Project.budget_actual_logs),
        )
        .filter(
            Project.department_id == department_id,
            Project.status == "in_progress",
            Project.approval_stage == "approved",
        )
        .all()
    )
    return sorted(projects, key=get_manager_monitoring_sort_key)


def find_next_manager_monitoring_project(department_id: int, exclude_project_id: int | None = None) -> Project | None:
    projects = get_manager_monitoring_projects(department_id)
    for project in projects:
        if exclude_project_id is None or project.id != exclude_project_id:
            return project
    return None


def _build_manager_monitoring_task_data(task: Task, today: date) -> dict:
    status_rank = {"in_progress": 1, "not_started": 2, "done": 3}
    is_overdue = bool(task.due_date and task.status != "done" and task.due_date < today)

    if is_overdue:
        overdue_days = (today - task.due_date).days
        due_display = f"{task.due_date.month}/{task.due_date.day} +{overdue_days}日"
        due_class = "dl-over"
    elif task.due_date == today:
        due_display = f"{task.due_date.month}/{task.due_date.day} 今日"
        due_class = "dl-today"
    elif task.due_date == (today + timedelta(days=1)):
        due_display = f"{task.due_date.month}/{task.due_date.day} 明日"
        due_class = "dl-today"
    elif task.due_date:
        due_display = f"{task.due_date.month}/{task.due_date.day}"
        due_class = "dl-normal"
    else:
        due_display = "未設定"
        due_class = "dl-normal"

    status_label_map = {"not_started": "未着手", "in_progress": "進行中", "done": "完了"}
    status_badge_class_map = {"not_started": "sb-notstarted", "in_progress": "sb-progress", "done": "sb-done"}

    progress_rate = int(task.progress_rate or 0)
    if progress_rate >= 100:
        progress_fill_class = "tpf-high"
    elif progress_rate >= 50:
        progress_fill_class = "tpf-mid"
    else:
        progress_fill_class = "tpf-low"

    if is_overdue:
        row_class = "tr-delay"
        filter_status = "delay"
        status_label = "遅延"
        status_badge_class = "sb-delay"
    else:
        row_class = "tr-done" if task.status == "done" else ""
        filter_status = "done" if task.status == "done" else "progress" if task.status == "in_progress" else "notstarted"
        status_label = status_label_map.get(task.status, "未着手")
        status_badge_class = status_badge_class_map.get(task.status, "sb-notstarted")

    return {
        "id": task.id,
        "title": task.title,
        "assignee_name": task.assignee_name,
        "status": task.status,
        "status_label": status_label,
        "status_badge_class": status_badge_class,
        "row_class": row_class,
        "filter_status": filter_status,
        "is_overdue": is_overdue,
        "due_display": due_display,
        "due_class": due_class,
        "progress_rate": progress_rate,
        "progress_fill_class": progress_fill_class,
        "is_done": task.status == "done",
        "sort_rank": (0 if is_overdue else 1, status_rank.get(task.status, 9), task.due_date or date.max, task.id),
    }


def build_manager_monitoring_view_data(project: Project, monitoring_projects: list[Project]) -> dict:
    """案件モニタリング画面の表示用データを作る。"""
    today = jst_today()
    budget_metrics = _get_monitoring_budget_metrics(project)
    overdue_metrics = _get_monitoring_overdue_metrics(project, today)
    last_progress_metrics = _get_monitoring_last_progress_metrics(project, today)
    can_complete = is_manager_monitoring_project_complete_ready(project)

    tasks_data = [_build_manager_monitoring_task_data(task, today) for task in (project.tasks or [])]
    tasks_data.sort(key=lambda item: item["sort_rank"])

    total_tasks = len(tasks_data)
    done_tasks = sum(1 for item in tasks_data if item["status"] == "done")
    avg_progress = round(sum((item["progress_rate"] for item in tasks_data), 0) / total_tasks) if total_tasks else 0

    latest_due_date = _get_monitoring_latest_due_date(project)
    longest_due_display = "全タスク完了" if latest_due_date is None and total_tasks > 0 else (
        format_business_date(latest_due_date) if latest_due_date else "未設定"
    )

    report_month_label = f"{today.year}年{today.month}月分"
    report_comment = (project.monthly_report_comment or "").strip()
    report_updated_at = project.monthly_report_updated_at
    report_submitted = False
    report_updated_display = "—"
    if report_updated_at and report_comment:
        report_jst = report_updated_at.astimezone(ZoneInfo("Asia/Tokyo"))
        report_submitted = (report_jst.year == today.year and report_jst.month == today.month)
        report_updated_display = format_jst_date(report_updated_at)

    monitoring_projects_data = []
    for item in monitoring_projects:
        item_overdue = _get_monitoring_overdue_metrics(item, today)
        item_budget = _get_monitoring_budget_metrics(item)
        monitoring_projects_data.append(
            {
                "project_id": item.id,
                "title": item.title,
                "is_current": item.id == project.id,
                "can_complete": is_manager_monitoring_project_complete_ready(item),
                "has_delay": item_overdue["overdue_count"] > 0,
                "has_budget_alert": item_budget["budget_pct"] >= 80,
            }
        )

    budget_pct = budget_metrics["budget_pct"]
    budget_gauge_class = "hbs-over" if budget_pct >= 100 else "hbs-warn" if budget_pct >= 80 else "hbs-ok"
    budget_pct_class = "hbs-pct-over" if budget_pct >= 100 else "hbs-pct-warn" if budget_pct >= 80 else "hbs-pct-ok"

    return {
        "project_id": project.id,
        "project_name": project.title,
        "project_code": project.project_code,
        "applicant_name": project.applicant.display_name if project.applicant else "未設定",
        "department_name": project.department.name if project.department else "未設定",
        "overall_progress_pct": avg_progress,
        "done_count": done_tasks,
        "task_count": total_tasks,
        "budget_actual_display": format_decimal_amount(budget_metrics["actual_total"]),
        "budget_base_display": format_decimal_amount(budget_metrics["budget_base"]),
        "budget_pct": budget_pct,
        "budget_gauge_class": budget_gauge_class,
        "budget_pct_class": budget_pct_class,
        "budget_is_warn": 80 <= budget_pct < 100,
        "budget_is_over": budget_pct >= 100,
        "overdue_count": overdue_metrics["overdue_count"],
        "max_overdue_days": overdue_metrics["max_overdue_days"],
        "last_progress_label": last_progress_metrics["display_label"],
        "last_progress_sub": last_progress_metrics["display_sub"],
        "last_progress_meta": last_progress_metrics["display_meta"],
        "is_progress_stale": last_progress_metrics["is_stale"],
        "longest_due_display": longest_due_display,
        "report_month_label": report_month_label,
        "report_submitted": report_submitted,
        "report_updated_display": report_updated_display,
        "report_comment": report_comment,
        "tasks": tasks_data,
        "is_overall_progress_complete": avg_progress >= 100,
        "can_complete": can_complete,
        "complete_disabled_reason": "" if can_complete else "完了認定できる条件を満たしていません。全タスクが完了しているか確認してください。",
        "monitoring_projects": monitoring_projects_data,
    }


@app.route("/manager/projects/monitoring")
@login_required
def manager_project_monitoring():
    access_error = require_manager()
    if access_error:
        return access_error

    monitoring_projects = get_manager_monitoring_projects(current_user.department_id)
    if not monitoring_projects:
        return render_template(
            "manager_project_monitoring_empty.html",
            unread_notifications_count=get_unread_notifications_count(),
        )
    return redirect(url_for("manager_project_monitoring_detail", project_id=monitoring_projects[0].id))


@app.route("/manager/projects/<int:project_id>/monitoring", methods=["GET", "POST"])
@login_required
def manager_project_monitoring_detail(project_id: int):
    access_error = require_manager()
    if access_error:
        return access_error

    project = (
        Project.query.options(
            joinedload(Project.applicant),
            joinedload(Project.department),
            joinedload(Project.tasks),
            joinedload(Project.budget_actual_logs),
        )
        .filter(Project.id == project_id)
        .first()
    )

    if project is None or project.department_id != current_user.department_id:
        flash("対象の案件が見つかりません。", "danger")
        return redirect(url_for("manager_top"))
    if project.status == "completed":
        flash("完了済み案件は案件モニタリング画面では表示できません。", "danger")
        return redirect(url_for("manager_project_monitoring"))
    if project.status != "in_progress" or project.approval_stage != "approved":
        flash("この画面で確認できる開発中案件ではありません。", "danger")
        return redirect(url_for("manager_project_monitoring"))

    if request.method == "POST":
        if (request.form.get("confirm_complete") or "").strip() != "1":
            flash("完了認定の実行内容が不正です。", "danger")
            return redirect(url_for("manager_project_monitoring_detail", project_id=project.id))

        if not is_manager_monitoring_project_complete_ready(project):
            flash("完了認定できる条件を満たしていません。全タスクが完了しているか確認してください。", "danger")
            return redirect(url_for("manager_project_monitoring_detail", project_id=project.id))

        try:
            now_utc = utc_now()
            project.status = "completed"
            project.completed_at = now_utc
            project.updated_at = now_utc

            db.session.add(
                ProjectStatusLog(
                    project_id=project.id,
                    actor_id=current_user.id,
                    from_status="in_progress",
                    to_status="completed",
                    action="complete",
                    comment="部門管理者が案件を完了認定しました。",
                    acted_at=now_utc,
                )
            )

            db.session.add(
                Notification(
                    user_id=project.applicant_id,
                    project_id=project.id,
                    type="completed",
                    message=f"担当案件「{project.title}」が部門管理者により完了認定されました。",
                    is_read=False,
                    created_at=now_utc,
                )
            )
            db.session.commit()
            flash(f"「{project.title}」を完了認定し、主担当者へ通知しました。", "success")
        except SQLAlchemyError:
            db.session.rollback()
            flash("完了認定に失敗しました。時間をおいて再度お試しください。", "danger")
            return redirect(url_for("manager_project_monitoring_detail", project_id=project.id))

        next_project = find_next_manager_monitoring_project(current_user.department_id)
        if next_project:
            return redirect(url_for("manager_project_monitoring_detail", project_id=next_project.id))
        return redirect(url_for("manager_project_monitoring"))

    monitoring_projects = get_manager_monitoring_projects(current_user.department_id)
    view_data = build_manager_monitoring_view_data(project, monitoring_projects)
    return render_template(
        "manager_project_monitoring.html",
        view_data=view_data,
        monitoring_projects=view_data["monitoring_projects"],
        current_project_id=project.id,
        unread_notifications_count=get_unread_notifications_count(),
    )


# =============================
# ■ 本部管理者：トップ画面
# =============================
def _build_hq_top_empty_view_data() -> dict:
    """本部管理者トップ画面の空表示用データ。"""
    return {
        "summary": {
            "department_projects": {"value": 0, "unit": "件", "meta": "0部門合計", "number_class": "sb-number-normal"},
            "final_approval_requests": {"value": 0, "unit": "件", "meta": "待機中なし", "number_class": "sb-number-normal"},
            "budget_alert_departments": {"value": 0, "unit": "部門", "meta": "注意0/超過0", "number_class": "sb-number-normal"},
            "company_budget_rate": {"value": 0, "unit": "%", "meta": "¥0/¥0", "number_class": "sb-number-normal"},
            "delayed_projects": {"value": 0, "unit": "件", "meta": "最長遅延なし", "number_class": "sb-number-normal"},
            "budget_alert_projects": {"value": 0, "unit": "件", "meta": "注意0/超過0", "number_class": "sb-number-normal"},
        },
        "department_budgets": [],
        "company_budget": {"show_empty": True},
        "phase_distribution": {"total_count": 0, "segments": []},
        "final_approval_requests": [],
        "project_matrix": [],
        "departments": [],
    }


def _get_hq_status_view(project: Project, today: date) -> dict:
    """案件の表示用ステータス情報を返す。"""
    has_delay = any(task.due_date and task.status != "done" and task.due_date < today for task in project.tasks)

    if project.status == "department_pending":
        return {"key": "pending", "text": "部門承認待ち", "badge_class": "badge b-wait", "is_delay": False}
    if project.status == "hq_pending":
        return {"key": "pending", "text": "本部承認待ち", "badge_class": "badge badge-approval-hq", "is_delay": False}
    if project.status == "completed":
        return {"key": "completed", "text": "完了", "badge_class": "badge b-done", "is_delay": False}
    if project.status == "rejected":
        return {"key": "rejected", "text": "却下", "badge_class": "badge b-rejected", "is_delay": False}
    if project.status == "in_progress":
        if has_delay:
            return {"key": "delay", "text": "遅延", "badge_class": "badge b-delay", "is_delay": True}
        return {"key": "in_progress", "text": "進行中", "badge_class": "badge b-prog", "is_delay": False}
    return {"key": "unknown", "text": "不明", "badge_class": "badge", "is_delay": False}


def _get_hq_department_badge_class(department_name: str | None) -> str:
    """HQトップ画面用の部門バッジclass（badgeプレフィックスなし）。"""
    mapping = {
        "システム開発部": "badge-dept-system",
        "情報基盤部": "badge-dept-infra",
        "業務改革推進部": "badge-dept-reform",
    }
    return mapping.get(department_name or "", "badge-dept-muted")


def _normalize_single_line(text: str | None) -> str:
    """改行や連続空白を除去して1行テキストへ整形する。"""
    return " ".join((text or "").split())


def _truncate_with_ellipsis(text: str, limit: int) -> str:
    """指定文字数を超える場合のみ末尾を省略する。"""
    if len(text) <= limit:
        return text
    return f"{text[:limit]}…"


def _format_summary_amount_short(value: Decimal) -> str:
    """サマリー用の金額を短縮表記に整形する。"""
    amount = int(value or 0)
    if amount == 0:
        return "¥0"
    million = amount // 1_000_000
    if million > 0:
        return f"¥{million:,}M"
    return f"¥{amount:,}"


def build_hq_top_view_data() -> dict:
    """本部管理者トップ画面の表示用データを作る。"""
    today = jst_today()
    fiscal_year = get_fiscal_year(today)
    fiscal_start = date(fiscal_year, 4, 1)
    fiscal_end = date(fiscal_year + 1, 3, 31)

    departments = Department.query.order_by(Department.id.asc()).all()
    projects = (
        Project.query.options(
            joinedload(Project.department),
            joinedload(Project.applicant),
            joinedload(Project.tasks),
            joinedload(Project.budget_actual_logs),
            joinedload(Project.project_status_logs),
        )
        .order_by(Project.updated_at.desc(), Project.id.desc())
        .all()
    )
    allowed_hq_project_statuses = {
        "department_pending",
        "hq_pending",
        "in_progress",
        "completed",
        "rejected",
    }
    display_projects = [p for p in projects if p.status in allowed_hq_project_statuses]

    actual_rows = (
        db.session.query(
            Project.department_id,
            func.coalesce(func.sum(BudgetActualLog.amount), 0),
        )
        .join(Project, Project.id == BudgetActualLog.project_id)
        .filter(
            BudgetActualLog.recorded_on >= fiscal_start,
            BudgetActualLog.recorded_on <= fiscal_end,
        )
        .group_by(Project.department_id)
        .all()
    )
    actual_by_department = {int(dept_id): Decimal(amount or 0) for dept_id, amount in actual_rows if dept_id is not None}

    budget_rows = (
        DepartmentYearlyBudget.query.options(joinedload(DepartmentYearlyBudget.department))
        .filter(DepartmentYearlyBudget.fiscal_year == fiscal_year)
        .order_by(DepartmentYearlyBudget.department_id.asc())
        .all()
    )
    yearly_budget_by_department = {int(row.department_id): Decimal(row.annual_budget_amount or 0) for row in budget_rows}

    department_items: list[dict] = []
    department_caution = 0
    department_over = 0
    department_projects_count: dict[int, int] = {}
    delay_count_by_dept: dict[int, int] = {}
    project_budget_over_by_dept: dict[int, int] = {}
    project_budget_warn_by_dept: dict[int, int] = {}

    delayed_project_ids: set[int] = set()
    project_budget_state: dict[int, str] = {}
    final_approval_requests: list[dict] = []
    longest_final_wait_days = 0
    has_wait3_final_approval = False
    phase_counts = {"completed": 0, "in_progress": 0, "pending": 0, "delay": 0, "rejected": 0}
    project_matrix: list[dict] = []
    max_delay_days = 0

    for project in display_projects:
        dept_id = int(project.department_id) if project.department_id is not None else 0
        if dept_id and project.status != "rejected":
            department_projects_count[dept_id] = department_projects_count.get(dept_id, 0) + 1

        status_view = _get_hq_status_view(project, today)
        if status_view["key"] == "delay":
            delayed_project_ids.add(project.id)
            if dept_id:
                delay_count_by_dept[dept_id] = delay_count_by_dept.get(dept_id, 0) + 1
            for task in project.tasks:
                if task.due_date and task.status != "done" and task.due_date < today:
                    max_delay_days = max(max_delay_days, (today - task.due_date).days)

        phase_key = status_view["key"]
        if project.status == "rejected":
            phase_key = "rejected"
        phase_counts[phase_key] = phase_counts.get(phase_key, 0) + 1

        budget_rate = project.budget_consumption_rate or Decimal("0")
        budget_state = "ok"
        if project.status == "in_progress":
            if budget_rate >= Decimal("100"):
                budget_state = "over"
                if dept_id:
                    project_budget_over_by_dept[dept_id] = project_budget_over_by_dept.get(dept_id, 0) + 1
            elif budget_rate >= Decimal("80"):
                budget_state = "warn"
                if dept_id:
                    project_budget_warn_by_dept[dept_id] = project_budget_warn_by_dept.get(dept_id, 0) + 1
        project_budget_state[project.id] = budget_state

        if project.status == "hq_pending" and project.approval_stage == "hq_pending":
            dept_log = _get_latest_action_log(project, "approve_department")
            request_dt = (dept_log.acted_at if dept_log else None) or project.updated_at or project.created_at
            request_jst_date = _jst_date_from_datetime(request_dt)
            wait_days = (today - request_jst_date).days if request_jst_date else 0
            longest_final_wait_days = max(longest_final_wait_days, wait_days)
            if wait_days >= 3:
                has_wait3_final_approval = True
            final_approval_requests.append(
                {
                    "date_class": "urgent-cell" if wait_days >= 3 else "",
                    "department_approved_on": format_jst_date(request_dt, "%m/%d") if request_dt else "—",
                    "department_badge_class": _get_hq_department_badge_class(project.department.name if project.department else None),
                    "department_name": project.department.name if project.department else "未所属",
                    "project_name": project.title,
                    "estimated_budget_text": format_decimal_amount(
                        Decimal(
                            (
                                project.approved_budget_amount
                                if project.approved_budget_amount is not None
                                else project.estimated_budget_amount
                            )
                            or 0
                        )
                    ),
                    "status_badge_class": "badge-primary bp-urgent" if wait_days >= 3 else "badge badge-approval-hq",
                    "status_text": f"{wait_days}日待機" if wait_days >= 3 else "本部承認待ち",
                    "review_url": url_for("hq_project_final_review", project_id=project.id),
                    "project_id": project.id,
                    "sort_key": request_dt or project.created_at,
                }
            )

        progress_percent: int | None = 0
        if project.status == "completed":
            progress_percent = 100
        elif project.status == "rejected":
            progress_percent = None
        elif project.status in {"department_pending", "hq_pending"}:
            progress_percent = None
        elif project.tasks:
            done_count = sum(1 for task in project.tasks if task.status == "done")
            progress_percent = int(round((done_count / len(project.tasks)) * 100))

        progress_fill_class = "mf-prog" if progress_percent == 100 else "mf-ok"
        progress_text_class = "mp-blue"
        if progress_percent == 100:
            progress_text_class = "mp-ok"

        display_budget_state = "ok"
        if project.status in {"in_progress", "completed"}:
            if budget_rate >= Decimal("100"):
                display_budget_state = "over"
            elif budget_rate >= Decimal("80"):
                display_budget_state = "warn"

        budget_fill_class = "mf-ok"
        budget_text_class = "mp-blue"
        if display_budget_state == "over":
            budget_fill_class = "mf-over"
            budget_text_class = "mp-over"
        elif display_budget_state == "warn":
            budget_fill_class = "mf-warn"
            budget_text_class = "mp-warn"

        report_class = "matrix-report-normal"
        report_text = "—"
        updated_jst_date = _jst_date_from_datetime(project.monthly_report_updated_at)
        if project.status == "rejected":
            report_text = "—"
        elif project.monthly_report_updated_at:
            if project.status == "completed":
                report_text = "完了報告済"
            else:
                report_text = f"{format_jst_date(project.monthly_report_updated_at, '%m/%d')} 更新"

            if updated_jst_date and (updated_jst_date.year, updated_jst_date.month) < (today.year, today.month):
                report_class = "matrix-report-danger"
            elif updated_jst_date:
                days_since_update = (today - updated_jst_date).days
                report_class = "matrix-report-warn" if days_since_update >= 15 else "matrix-report-normal"

        if project.status in {"department_pending", "hq_pending", "rejected"}:
            detail_label = "申請概要"
            detail_base = _normalize_single_line(project.summary or project.purpose or "")
            if not detail_base:
                detail_text = "申請概要は登録されていません。"
            else:
                detail_text = _truncate_with_ellipsis(detail_base, 70)
        elif project.status == "completed":
            detail_label = "最終報告"
            detail_text = _normalize_single_line(project.monthly_report_comment or "")
            if not detail_text:
                detail_text = "最終報告はまだ登録されていません。"
        else:
            detail_text = _normalize_single_line(project.monthly_report_comment or "")
            if project.monthly_report_updated_at:
                updated_jst = project.monthly_report_updated_at.astimezone(ZoneInfo("Asia/Tokyo"))
                detail_label = f"最新月次報告（{updated_jst.year}年{updated_jst.month}月）"
            else:
                detail_label = "最新月次報告"
            if not detail_text:
                detail_text = "月次報告はまだ登録されていません。"

        project_name_class = ""
        row_class = "matrix-row-muted" if project.status in {"completed", "rejected"} else ""

        search_text = " ".join(
            (project.title or "",
             project.department.name if project.department else "",
             project.applicant.display_name if project.applicant else "",
             project.monthly_report_comment or "",
             status_view["text"] or "")
        )
        search_text = " ".join(search_text.split())

        if status_view["key"] == "delay":
            sort_priority = 1
        elif project.status == "in_progress" and budget_state == "over":
            sort_priority = 2
        elif project.status == "in_progress" and budget_state == "warn":
            sort_priority = 3
        elif project.status == "hq_pending":
            sort_priority = 4
        elif project.status == "department_pending":
            sort_priority = 5
        elif project.status == "in_progress":
            sort_priority = 6
        elif project.status == "completed":
            sort_priority = 7
        else:
            sort_priority = 8

        matrix_item = {
            "row_class": row_class,
            "dept_key": str(project.department_id) if project.department_id is not None else "",
            "status_key": status_view["key"],
            "search_text": search_text,
            "project_name_class": project_name_class,
            "project_name": project.title,
            "department_badge_class": _get_hq_department_badge_class(project.department.name if project.department else None),
            "department_name": project.department.name if project.department else "未所属",
            "owner_name": project.applicant.display_name if project.applicant else "主担当未設定",
            "status_badge_class": status_view["badge_class"],
            "status_text": status_view["text"],
            "progress_text": f"{progress_percent}%" if progress_percent is not None else "",
            "progress_fill_class": progress_fill_class,
            "progress_width": f"{min(progress_percent or 0, 100)}%" if progress_percent is not None else "0%",
            "progress_text_class": progress_text_class,
            "progress_fallback_text": "—" if project.status == "rejected" else "未着手",
            "budget_text": f"{_format_hq_percent_int(budget_rate)}%" if project.status in {"in_progress", "completed"} else "",
            "budget_fill_class": budget_fill_class,
            "budget_width": f"{min(float(budget_rate), 100.0):.0f}%",
            "budget_text_class": budget_text_class,
            "budget_fallback_text": "—" if project.status == "rejected" else "申請中",
            "report_class": report_class,
            "report_text": report_text,
            "detail_label": detail_label,
            "detail_text": detail_text,
            "sort_priority": sort_priority,
            "sort_planned_end_none": project.planned_end_date is None,
            "sort_planned_end_date": project.planned_end_date or date.max,
            "sort_project_id": project.id,
        }
        project_matrix.append(matrix_item)

    project_matrix.sort(
        key=lambda item: (
            item["sort_priority"],
            item["sort_planned_end_none"],
            item["sort_planned_end_date"],
            item["sort_project_id"],
        ),
    )
    for item in project_matrix:
        item.pop("sort_priority", None)
        item.pop("sort_planned_end_none", None)
        item.pop("sort_planned_end_date", None)
        item.pop("sort_project_id", None)

    final_approval_requests.sort(key=lambda item: (item["sort_key"], item["project_id"]))
    for item in final_approval_requests:
        item.pop("sort_key", None)

    for dept in departments:
        dept_id = int(dept.id)
        annual_amount = yearly_budget_by_department.get(dept_id, Decimal("0"))
        actual_amount = actual_by_department.get(dept_id, Decimal("0"))
        rate = Decimal("0")
        is_budget_unregistered = annual_amount <= 0
        if not is_budget_unregistered:
            rate = (actual_amount / annual_amount) * Decimal("100")

        fill_class = "dbf-success"
        rate_class = "dbl-pct-success" if not is_budget_unregistered else "dbl-pct-muted"
        state_rank = 2
        if is_budget_unregistered:
            fill_class = "dbf-muted"
            state_rank = 3
        elif rate >= Decimal("100"):
            fill_class = "dbf-over"
            rate_class = "dbl-pct-over"
            department_over += 1
            state_rank = 0
        elif rate >= Decimal("80"):
            fill_class = "dbf-warn"
            rate_class = "dbl-pct-warn"
            department_caution += 1
            state_rank = 1

        dept_delay = delay_count_by_dept.get(dept_id, 0)
        dept_over = project_budget_over_by_dept.get(dept_id, 0)
        dept_warn = project_budget_warn_by_dept.get(dept_id, 0)
        tags = [{"class": "dbt-count", "text": f"案件 {department_projects_count.get(dept_id, 0)}件"}]
        if dept_delay > 0:
            tags.append({"class": "dbt-danger", "text": f"遅延 {dept_delay}"})
        if dept_over > 0:
            tags.append({"class": "dbt-danger", "text": f"予算超過 {dept_over}"})
        if dept_warn > 0:
            tags.append({"class": "dbt-warn", "text": f"予算注意 {dept_warn}"})
        if is_budget_unregistered:
            tags.append({"class": "dbt-muted", "text": "年間予算未登録"})
        elif dept_over == 0 and dept_warn == 0:
            tags.append({"class": "dbt-success", "text": "予算健全"})

        department_items.append(
            {
                "department_name": dept.name,
                "amount_text": f"{format_decimal_amount(actual_amount)} / {format_decimal_amount(annual_amount)}",
                "rate_text": f"{_format_hq_percent_int(rate)}%",
                "rate_class": rate_class,
                "fill_class": fill_class,
                "fill_width": f"{min(float(rate), 100.0):.0f}%",
                "tags": tags,
                "sort_state_rank": state_rank,
                "sort_rate_value": float(rate),
            }
        )

    department_items.sort(key=lambda item: (item["sort_state_rank"], -item["sort_rate_value"]))
    for item in department_items:
        item.pop("sort_state_rank", None)
        item.pop("sort_rate_value", None)

    company_budget_total_sum = (
        db.session.query(func.coalesce(func.sum(DepartmentYearlyBudget.annual_budget_amount), 0))
        .filter(DepartmentYearlyBudget.fiscal_year == fiscal_year)
        .scalar()
    )
    company_budget_total = Decimal(company_budget_total_sum or 0)
    company_actual_sum = (
        db.session.query(func.coalesce(func.sum(BudgetActualLog.amount), 0))
        .join(Project, Project.id == BudgetActualLog.project_id)
        .filter(
            BudgetActualLog.recorded_on >= fiscal_start,
            BudgetActualLog.recorded_on <= fiscal_end,
        )
        .scalar()
    )
    company_actual = Decimal(company_actual_sum or 0)

    company_budget = {"show_empty": True}
    company_rate = Decimal("0")
    if company_budget_total > 0:
        company_rate = (company_actual / company_budget_total) * Decimal("100")
        over_amount = max(company_actual - company_budget_total, Decimal("0"))
        remaining_amount = max(company_budget_total - company_actual, Decimal("0"))
        circle = Decimal("87.96")
        used_pct = min(company_rate, Decimal("100"))
        over_pct = min(max(company_rate - Decimal("100"), Decimal("0")), Decimal("100"))
        used_dash = (circle * used_pct / Decimal("100")).quantize(Decimal("0.01"))
        over_dash = (circle * over_pct / Decimal("100")).quantize(Decimal("0.01"))
        over_dashoffset = "0" if used_dash == Decimal("0") else f"-{used_dash}"
        company_budget = {
            "show_empty": False,
            "rate_value": float(company_rate),
            "over_rate_value": float(over_pct),
            "main_dasharray": f"{used_dash} {(circle - used_dash).quantize(Decimal('0.01'))}",
            "over_dasharray": f"{over_dash} {(circle - over_dash).quantize(Decimal('0.01'))}",
            "over_dashoffset": over_dashoffset,
            "rate_class": "dp-danger" if company_rate >= Decimal("100") else ("dp-warn" if company_rate >= Decimal("80") else ""),
            "rate_text": f"{_format_hq_percent_int(company_rate)}%",
            "used_amount_text": format_decimal_amount(company_actual),
            "over_amount_text": format_decimal_amount(over_amount),
            "remaining_amount_text": format_decimal_amount(remaining_amount),
            "total_amount_text": format_decimal_amount(company_budget_total),
        }

    phase_segments = []
    project_total = len(display_projects)
    if project_total > 0:
        circle_value = Decimal("87.96")
        phase_order = [
            ("completed", "完了", "phase-stroke-completed", "phase-dot-completed"),
            ("in_progress", "開発進行中", "phase-stroke-progress", "phase-dot-progress"),
            ("pending", "承認待ち", "phase-stroke-pending", "phase-dot-pending"),
            ("delay", "遅延中", "phase-stroke-delayed", "phase-dot-delayed"),
            ("rejected", "却下", "phase-stroke-rejected", "phase-dot-rejected"),
        ]
        cumulative = Decimal("0")
        for key, label, stroke_class, dot_class in phase_order:
            count = phase_counts.get(key, 0)
            if count <= 0:
                pct = Decimal("0")
                arc = Decimal("0")
                dasharray = "0 87.96"
            else:
                pct = (Decimal(count) / Decimal(project_total)) * Decimal("100")
                arc = (circle_value * Decimal(count) / Decimal(project_total)).quantize(Decimal("0.01"))
                dasharray = f"{arc} {(circle_value - arc).quantize(Decimal('0.01'))}"
            phase_segments.append(
                {
                    "name": label,
                    "count_text": f"{count}件",
                    "pct_text": f"{_format_hq_percent_int(pct)}%",
                    "stroke_class": stroke_class,
                    "dot_class": dot_class,
                    "dasharray": dasharray,
                    "dashoffset": f"-{cumulative.quantize(Decimal('0.01'))}",
                }
            )
            cumulative += arc

    managed_projects = [p for p in display_projects if p.status in {"department_pending", "hq_pending", "in_progress", "completed"}]
    budget_project_over = sum(
        1 for p in display_projects if p.status == "in_progress" and project_budget_state.get(p.id) == "over"
    )
    budget_project_warn = sum(
        1 for p in display_projects if p.status == "in_progress" and project_budget_state.get(p.id) == "warn"
    )

    budget_alert_dept_number_class = "sb-number-normal"
    if department_over > 0:
        budget_alert_dept_number_class = "sb-number-red"
    elif department_caution > 0:
        budget_alert_dept_number_class = "sb-number-orange"

    company_budget_number_class = "sb-number-normal"
    if company_budget_total > 0:
        if company_rate >= Decimal("100"):
            company_budget_number_class = "sb-number-red"
        elif company_rate >= Decimal("80"):
            company_budget_number_class = "sb-number-orange"

    budget_alert_project_number_class = "sb-number-normal"
    if budget_project_over > 0:
        budget_alert_project_number_class = "sb-number-red"
    elif budget_project_warn > 0:
        budget_alert_project_number_class = "sb-number-orange"

    summary = {
        "department_projects": {
            "value": len(managed_projects),
            "unit": "件",
            "meta": f"{len(departments)}部門合計",
            "number_class": "sb-number-normal",
        },
        "final_approval_requests": {
            "value": len(final_approval_requests),
            "unit": "件",
            "meta": f"最長{longest_final_wait_days}日待機中" if final_approval_requests else "待機中なし",
            "number_class": "sb-number-yellow" if has_wait3_final_approval else "sb-number-normal",
        },
        "budget_alert_departments": {
            "value": department_caution + department_over,
            "unit": "部門",
            "meta": f"注意{department_caution}/超過{department_over}",
            "number_class": budget_alert_dept_number_class,
        },
        "company_budget_rate": {
            "value": _format_hq_percent_int(company_rate),
            "unit": "%",
            "meta": f"{_format_summary_amount_short(company_actual)}/{_format_summary_amount_short(company_budget_total)}",
            "number_class": company_budget_number_class,
        },
        "delayed_projects": {
            "value": len(delayed_project_ids),
            "unit": "件",
            "meta": f"最長遅延{max_delay_days}日" if delayed_project_ids else "最長遅延なし",
            "number_class": "sb-number-red" if delayed_project_ids else "sb-number-normal",
        },
        "budget_alert_projects": {
            "value": budget_project_warn + budget_project_over,
            "unit": "件",
            "meta": f"注意{budget_project_warn}/超過{budget_project_over}",
            "number_class": budget_alert_project_number_class,
        },
    }

    return {
        "summary": summary,
        "department_budgets": department_items,
        "company_budget": company_budget,
        "phase_distribution": {"total_count": project_total, "segments": phase_segments},
        "final_approval_requests": final_approval_requests,
        "project_matrix": project_matrix,
        "departments": [{"dept_key": str(d.id), "name": d.name} for d in departments],
    }


@app.route("/top/hq")
@login_required
def hq_top():
    access_error = require_hq()
    if access_error:
        return access_error

    try:
        view_data = build_hq_top_view_data()
    except SQLAlchemyError:
        flash("ダッシュボード情報の取得に失敗しました。時間をおいてもう一度お試しください。", "danger")
        return render_template(
            "hq_top_empty.html",
            unread_notifications_count=get_unread_notifications_count(),
        )

    return render_template(
        "hq_top.html",
        view_data=view_data,
        unread_notifications_count=get_unread_notifications_count(),
    )


# =============================
# ■ 本部管理者：最終承認審査画面
# =============================
def _get_latest_action_log(project: Project, action: str) -> ProjectStatusLog | None:
    logs = [log for log in project.project_status_logs if log.action == action]
    if not logs:
        return None
    return max(logs, key=lambda log: (log.acted_at, log.id))


def _get_hq_pending_projects() -> list[Project]:
    projects = (
        Project.query.options(
            joinedload(Project.applicant),
            joinedload(Project.department),
            joinedload(Project.project_status_logs).joinedload(ProjectStatusLog.actor),
        )
        .filter(
            Project.status == "hq_pending",
            Project.approval_stage == "hq_pending",
        )
        .all()
    )

    def sort_key(project: Project):
        dept_log = _get_latest_action_log(project, "approve_department")
        base_dt = (dept_log.acted_at if dept_log else None) or project.updated_at or project.created_at
        return (base_dt, project.id)

    return sorted(projects, key=sort_key)


def _get_department_badge_class(department_name: str | None) -> str:
    mapping = {
        "システム開発部": "badge badge-dept-system",
        "情報基盤部": "badge badge-dept-infra",
        "業務改革推進部": "badge badge-dept-reform",
    }
    return mapping.get(department_name or "", "badge")


def _format_axis_amount(value: Decimal) -> str:
    amount = int(value)
    oku = amount // 100_000_000
    man = (amount % 100_000_000) // 10_000
    if oku > 0 and man > 0:
        return f"{oku:,}億{man:,}万円"
    if oku > 0:
        return f"{oku:,}億円"
    if man > 0:
        return f"{man:,}万円"
    return f"¥{amount:,}"


def _build_hq_budget_simulation(project: Project) -> dict:
    fiscal_year = get_fiscal_year(project.planned_start_date)
    fiscal_start = date(fiscal_year, 4, 1)
    fiscal_end = date(fiscal_year + 1, 3, 31)

    annual_budget_sum = (
        db.session.query(func.coalesce(func.sum(DepartmentYearlyBudget.annual_budget_amount), 0))
        .filter(DepartmentYearlyBudget.fiscal_year == fiscal_year)
        .scalar()
    )
    annual_budget = Decimal(annual_budget_sum or 0)

    actual_sum = (
        db.session.query(func.coalesce(func.sum(BudgetActualLog.amount), 0))
        .join(Project, Project.id == BudgetActualLog.project_id)
        .filter(
            Project.planned_start_date >= fiscal_start,
            Project.planned_start_date <= fiscal_end,
            Project.status != "rejected",
        )
        .scalar()
    )
    actual_amount = Decimal(actual_sum or 0)
    this_project_amount = Decimal(project.estimated_budget_amount or 0)
    remaining_amount = annual_budget - actual_amount - this_project_amount

    consume_rate = Decimal("0")
    actual_rate = Decimal("0")
    occupy_rate = Decimal("0")
    remaining_rate = Decimal("0")
    if annual_budget > 0:
        consume_rate = ((actual_amount + this_project_amount) / annual_budget) * Decimal("100")
        actual_rate = (actual_amount / annual_budget) * Decimal("100")
        occupy_rate = (this_project_amount / annual_budget) * Decimal("100")
        remaining_rate = Decimal("100") - actual_rate - occupy_rate

    if annual_budget <= 0 or remaining_amount < 0:
        result_class = "danger"
    elif consume_rate >= Decimal("80"):
        result_class = "warn"
    else:
        result_class = "ok"

    consume_rate_class = "ibv-ok"
    remaining_amount_class = "ibv-ok"
    if result_class == "warn":
        consume_rate_class = "ibv-warn"
        remaining_amount_class = "ibv-warn"
    elif result_class == "danger":
        consume_rate_class = "ibv-danger"
        remaining_amount_class = "ibv-danger"

    if occupy_rate >= Decimal("30"):
        occupy_rate_class = "ibv-danger"
    elif occupy_rate >= Decimal("20"):
        occupy_rate_class = "ibv-warn"
    else:
        occupy_rate_class = "ibv-ok"

    consume_rate_display = format_percent_value(consume_rate)
    actual_rate_display = format_percent_value(actual_rate)
    occupy_rate_display = format_percent_value(occupy_rate)
    remaining_rate_display = format_percent_value(remaining_rate)
    remaining_amount_display = format_decimal_amount(remaining_amount)
    if remaining_amount < 0:
        remaining_amount_display = f"-{format_decimal_amount(abs(remaining_amount))}"

    if annual_budget <= 0:
        result_title = "全社年間予算が登録されていません"
        result_message = "予算シミュレーションを表示できません。年度予算データを確認してください。"
    elif result_class == "ok":
        result_title = f"承認後の予算残高：{remaining_amount_display}（{remaining_rate_display}%）"
        result_message = "本案件を承認しても、全社年間予算には十分な残余があります。"
    elif result_class == "warn":
        result_title = f"承認後の予算残高：{remaining_amount_display}（{remaining_rate_display}%）"
        result_message = f"本案件を承認すると予算消化率が{consume_rate_display}%になります。年度内の追加申請に備え、全社予算の残高を確認してください。"
    else:
        result_title = f"承認後の予算残高：{remaining_amount_display}（予算超過）"
        result_message = "本案件を承認すると全社年間予算を超過します。予算調整が必要です。"

    if annual_budget > 0:
        axis_labels = ["0"]
        for pct in [25, 50, 75, 100]:
            amount = (annual_budget * Decimal(pct)) / Decimal("100")
            axis_labels.append(f"{pct}%（{_format_axis_amount(amount)}）")
    else:
        axis_labels = ["0", "25%", "50%", "75%", "100%"]

    all_project_amounts = (
        db.session.query(Project.id, Project.estimated_budget_amount, Project.approved_budget_amount)
        .filter(
            Project.planned_start_date >= fiscal_start,
            Project.planned_start_date <= fiscal_end,
            Project.status != "rejected",
        )
        .all()
    )
    sorted_by_amount = sorted(
        all_project_amounts,
        key=lambda row: Decimal(
            row.approved_budget_amount if row.approved_budget_amount is not None else (row.estimated_budget_amount or 0)
        ),
        reverse=True,
    )
    rank_map = {row.id: idx + 1 for idx, row in enumerate(sorted_by_amount)}
    budget_rank = rank_map.get(project.id, 1)

    return {
        "annual_budget_display": format_decimal_amount(annual_budget),
        "actual_amount_display": format_decimal_amount(actual_amount),
        "this_project_amount_display": format_decimal_amount(this_project_amount),
        "remaining_amount_display": remaining_amount_display,
        "consume_rate_display": consume_rate_display,
        "actual_rate_display": actual_rate_display,
        "occupy_rate_display": occupy_rate_display,
        "remaining_rate_display": remaining_rate_display,
        "result_class": result_class,
        "result_title": result_title,
        "result_message": result_message,
        "consume_rate_class": consume_rate_class,
        "remaining_amount_class": remaining_amount_class,
        "occupy_rate_class": occupy_rate_class,
        "axis_labels": axis_labels,
        "seg_used": float(max(Decimal("0"), min(Decimal("100"), actual_rate))),
        "seg_this": float(max(Decimal("0"), min(Decimal("100"), occupy_rate))),
        "seg_remaining": float(max(Decimal("0"), min(Decimal("100"), remaining_rate))),
        "budget_rank": budget_rank,
        "project_count": len(sorted_by_amount),
    }


def _build_hq_final_review_view_data(
    project: Project,
    queue_projects: list[Project],
    rejection_comment: str = "",
    force_reject_mode: bool = False,
) -> dict:
    submit_log = _get_latest_submit_log(project)
    submitted_at = submit_log.acted_at if submit_log else project.created_at
    dept_approved_log = _get_latest_action_log(project, "approve_department")
    dept_approved_at = dept_approved_log.acted_at if dept_approved_log else None
    dept_approver_name = dept_approved_log.actor.display_name if (dept_approved_log and dept_approved_log.actor) else "—"

    today_jst = jst_today()
    waiting_days = 0
    if dept_approved_at:
        waiting_days = (today_jst - dept_approved_at.astimezone(ZoneInfo("Asia/Tokyo")).date()).days

    current_index = next((idx for idx, p in enumerate(queue_projects) if p.id == project.id), 0)
    total_count = len(queue_projects)
    prev_project_id = queue_projects[current_index - 1].id if current_index > 0 else None
    next_project_id = queue_projects[current_index + 1].id if current_index < total_count - 1 else None

    queue_items = []
    for idx, item in enumerate(queue_projects, start=1):
        item_dept_log = _get_latest_action_log(item, "approve_department")
        item_wait_days = 0
        item_dept_approved_date_display = "--/--"
        if item_dept_log:
            item_wait_days = (today_jst - item_dept_log.acted_at.astimezone(ZoneInfo("Asia/Tokyo")).date()).days
            item_dept_approved_date_display = format_jst_date(item_dept_log.acted_at, "%m/%d")
        queue_items.append(
            {
                "project_id": item.id,
                "index": idx,
                "title": item.title,
                "department_name": item.department.name if item.department else "—",
                "department_approved_date_display": item_dept_approved_date_display,
                "is_current": item.id == project.id,
                "wait_badge_text": f"{item_wait_days}日待機" if item_wait_days >= 3 else "",
            }
        )

    budget_sim = _build_hq_budget_simulation(project)
    duration_months = 0
    if project.planned_start_date and project.planned_end_date:
        duration_months = ((project.planned_end_date - project.planned_start_date).days // 30) + 1

    return {
        "project_id": project.id,
        "project_name": project.title,
        "project_code": project.project_code,
        "purpose": project.purpose,
        "applicant_name": project.applicant.display_name if project.applicant else "—",
        "department_name": project.department.name if project.department else "—",
        "department_badge_class": _get_department_badge_class(project.department.name if project.department else None),
        "submitted_date_display": format_jst_date(submitted_at),
        "submitted_date_ja": format_jst_date_ja(submitted_at),
        "dept_approved_display": f"{format_jst_date(dept_approved_at)}（{dept_approver_name}）" if dept_approved_at else "—",
        "wait_badge_text": f"{waiting_days}日待機" if waiting_days >= 3 else "",
        "estimated_budget_display": format_decimal_amount(Decimal(project.estimated_budget_amount or 0)),
        "estimated_person_months_display": format_person_months(project.estimated_person_months),
        "planned_period_display": f"{format_business_date_ja(project.planned_start_date)}〜{format_business_date_ja(project.planned_end_date)}（{duration_months}ヶ月）" if duration_months else "未設定",
        "queue_position": current_index + 1,
        "queue_total_count": total_count,
        "prev_project_id": prev_project_id,
        "next_project_id": next_project_id,
        "queue_items": queue_items,
        "queue_total_label": f"審査待ち案件（{total_count}件）",
        "budget_simulation": budget_sim,
        "rejection_comment": rejection_comment,
        "initial_verdict": "reject" if force_reject_mode else "approve",
    }


def _find_next_hq_pending_project(exclude_project_id: int | None = None) -> Project | None:
    queue_projects = _get_hq_pending_projects()
    if exclude_project_id is None:
        return queue_projects[0] if queue_projects else None
    for item in queue_projects:
        if item.id != exclude_project_id:
            return item
    return None


@app.route("/hq/projects/final-review")
@login_required
def hq_project_final_review_entry():
    """本部承認待ち案件の入口。先頭案件へ遷移する。"""
    access_error = require_hq()
    if access_error:
        return access_error

    queue_projects = _get_hq_pending_projects()
    if not queue_projects:
        return render_template(
            "hq_project_final_review_empty.html",
            unread_notifications_count=get_unread_notifications_count(),
        )
    return redirect(url_for("hq_project_final_review", project_id=queue_projects[0].id))


@app.route("/hq/projects/<int:project_id>/final-review", methods=["GET", "POST"])
@login_required
def hq_project_final_review(project_id: int):
    """本部管理者の最終承認審査画面。最終承認または却下を処理する。"""
    access_error = require_hq()
    if access_error:
        return access_error

    project = (
        Project.query.options(
            joinedload(Project.applicant),
            joinedload(Project.department),
            joinedload(Project.project_status_logs).joinedload(ProjectStatusLog.actor),
        )
        .filter(Project.id == project_id)
        .first()
    )
    if project is None:
        flash("指定された案件が見つかりません。", "danger")
        return redirect(url_for("hq_top"))

    queue_projects = _get_hq_pending_projects()
    is_pending_target = project.status == "hq_pending" and project.approval_stage == "hq_pending"

    if request.method == "GET":
        if not is_pending_target:
            flash("この案件は現在、本部承認の対象ではありません。", "danger")
            return redirect(url_for("hq_top"))
        review_data = _build_hq_final_review_view_data(project, queue_projects)
        return render_template(
            "hq_project_final_review.html",
            review_data=review_data,
            unread_notifications_count=get_unread_notifications_count(),
        )

    action = (request.form.get("action") or "").strip()
    confirmed = (request.form.get("confirmed") or "").strip()
    budget_confirmed = (request.form.get("budget_confirmed") or "").strip()
    rejection_comment = (request.form.get("rejection_comment") or "").strip()

    if not is_pending_target:
        flash("この案件はすでに審査済みです。", "warning")
        next_project = _find_next_hq_pending_project(exclude_project_id=project.id)
        if next_project:
            return redirect(url_for("hq_project_final_review", project_id=next_project.id))
        return redirect(url_for("hq_project_final_review_entry"))
    if action not in {"approve", "reject"}:
        flash("不正な操作が行われました。もう一度操作してください。", "danger")
        return redirect(url_for("hq_project_final_review", project_id=project_id))
    if confirmed != "1":
        flash("確認操作が完了していません。もう一度操作してください。", "danger")
        return redirect(url_for("hq_project_final_review", project_id=project_id))
    if action == "approve" and budget_confirmed != "1":
        flash("予算確定チェックを入れてから最終承認してください。", "danger")
        return redirect(url_for("hq_project_final_review", project_id=project_id))
    if action == "reject":
        if not rejection_comment:
            flash("却下理由は必須です。コメントを入力してください。", "danger")
            review_data = _build_hq_final_review_view_data(
                project,
                queue_projects,
                rejection_comment=rejection_comment,
                force_reject_mode=True,
            )
            return render_template(
                "hq_project_final_review.html",
                review_data=review_data,
                unread_notifications_count=get_unread_notifications_count(),
            )
        if len(rejection_comment) > 500:
            flash("却下理由は500文字以内で入力してください。", "danger")
            review_data = _build_hq_final_review_view_data(
                project,
                queue_projects,
                rejection_comment=rejection_comment,
                force_reject_mode=True,
            )
            return render_template(
                "hq_project_final_review.html",
                review_data=review_data,
                unread_notifications_count=get_unread_notifications_count(),
            )

    current_title = project.title
    try:
        if action == "approve":
            project.status = "in_progress"
            project.approval_stage = "approved"
            project.approved_budget_amount = project.estimated_budget_amount
            project.approved_at = utc_now()

            db.session.add(
                ProjectStatusLog(
                    project_id=project.id,
                    actor_id=current_user.id,
                    from_status="hq_pending",
                    to_status="in_progress",
                    action="approve_hq",
                    comment=None,
                    acted_at=utc_now(),
                )
            )
            create_notification(
                user_id=project.applicant_id,
                project_id=project.id,
                notif_type="approved",
                message=f"開発案件「{current_title}」が本部承認されました。開発管理フェーズへ進みます。",
            )
            flash(f"「{current_title}」を最終承認し、予算を確定しました。", "success")
        else:
            project.status = "rejected"
            project.approval_stage = "rejected"
            project.rejection_comment = rejection_comment
            project.final_rejected_at = utc_now()
            project.approved_budget_amount = None
            project.approved_at = None

            db.session.add(
                ProjectStatusLog(
                    project_id=project.id,
                    actor_id=current_user.id,
                    from_status="hq_pending",
                    to_status="rejected",
                    action="reject_hq",
                    comment=rejection_comment,
                    acted_at=utc_now(),
                )
            )
            create_notification(
                user_id=project.applicant_id,
                project_id=project.id,
                notif_type="rejected",
                message=f"開発案件「{current_title}」が本部で却下されました。却下理由を確認してください。",
            )
            flash(f"「{current_title}」を却下し、申請者へ通知しました。", "success")

        db.session.commit()
    except SQLAlchemyError:
        db.session.rollback()
        flash("審査結果の保存に失敗しました。時間をおいて再度お試しください。", "danger")
        review_data = _build_hq_final_review_view_data(
            project,
            queue_projects,
            rejection_comment=rejection_comment if action == "reject" else "",
            force_reject_mode=(action == "reject"),
        )
        return render_template(
            "hq_project_final_review.html",
            review_data=review_data,
            unread_notifications_count=get_unread_notifications_count(),
        )

    next_project = _find_next_hq_pending_project(exclude_project_id=project.id)
    if next_project:
        return redirect(url_for("hq_project_final_review", project_id=next_project.id))
    return redirect(url_for("hq_project_final_review_entry"))


# UI見本の通常ページ確認用ルート
@app.route("/ui-kit")
def ui_kit():
    return render_template("ui-kit.html")

# UI見本のダッシュボード確認用ルート
@app.route("/ui-kit-dashboard")
def ui_kit_dashboard():
    return render_template("ui-kit-dashboard.html")


@app.route("/sample/applicant")
def sample_applicant_top():
    return render_template("sample_applicant_dashboard.html", demo_role="applicant")


@app.route("/sample/manager")
def sample_manager_top():
    return render_template("sample_manager_dashboard.html", demo_role="manager")


@app.route("/sample/hq")
def sample_hq_top():
    return render_template("sample_hq_dashboard.html", demo_role="hq")


if __name__ == "__main__":
    app.run(debug=True)
