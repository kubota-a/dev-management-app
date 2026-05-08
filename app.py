import os
import re
from datetime import date, datetime, timedelta
from decimal import Decimal, InvalidOperation
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

    return render_template("login.html", form=form, inline_error=inline_error)


def redirect_by_role(role: str):
    if role == "applicant":
        return url_for("applicant_top")
    if role == "manager":
        return url_for("manager_top")
    if role == "hq":
        return url_for("hq_top")
    return url_for("index")


def require_applicant():
    """申請者ロールのみ通す。権限外はロール別トップへ戻す。"""
    if current_user.role != "applicant":
        flash("この画面を表示する権限がありません。", "danger")
        return redirect(redirect_by_role(current_user.role))
    return None


def require_manager():
    """部門管理者ロールのみ許可する。"""
    if current_user.role != "manager":
        flash("この画面を表示する権限がありません。", "danger")
        return redirect(redirect_by_role(current_user.role))
    return None


def require_hq():
    """本部管理者ロールのみ許可する。"""
    if current_user.role != "hq":
        flash("この画面を表示する権限がありません。", "danger")
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
    flash("ログアウトしました。", "success")
    return redirect(url_for("login"))


# =============================
# ■ 申請者：トップ画面
# =============================
@app.route("/top/applicant")
@login_required
def applicant_top():
    return render_template("applicant_top.html", demo_role="applicant")


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
        Project.query.options(joinedload(Project.department))
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
        "report_month_label": f"{today.year}年{today.month}月",
        "current_position": current_index + 1 if current_index >= 0 else 0,
        "total_projects": len(progress_projects),
        "prev_project_id": prev_project_id,
        "next_project_id": next_project_id,
        "footer_project_name": project.title,
        "base_budget_amount": int(base_budget),
        "current_actual_amount": int(current_actual),
    }


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
            errors.append("予算実績額は半角数字で入力してください。")
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
    login_success_toast = session.pop("login_success_toast", None)
    return render_template(
        "applicant_project_progress.html",
        view_data=view_data,
        login_success_toast=login_success_toast,
        unread_notifications_count=get_unread_notifications_count(),
    )


# =============================
# ■ 部門管理者：トップ画面
# =============================
@app.route("/top/manager")
@login_required
def manager_top():
    return render_template("manager_top.html", demo_role="manager")


# =============================
# ■ 部門管理者：承認審査画面
# =============================
def get_fiscal_year(target_date: date) -> int:
    """Date型（業務日付）から日本の年度を返す。"""
    return target_date.year if target_date.month >= 4 else target_date.year - 1


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


def get_manager_review_projects(department_id: int) -> list[Project]:
    return (
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
        .order_by(Project.created_at.asc(), Project.id.asc())
        .all()
    )


def find_next_manager_review_project(department_id: int, exclude_project_id: int | None = None) -> Project | None:
    q = (
        Project.query.filter(
            Project.department_id == department_id,
            Project.status == "department_pending",
            Project.approval_stage == "department_pending",
        )
        .order_by(Project.created_at.asc(), Project.id.asc())
    )
    if exclude_project_id is not None:
        q = q.filter(Project.id != exclude_project_id)
    return q.first()


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
    submit_log = _get_latest_submit_log(project)
    submitted_at = submit_log.acted_at if submit_log else project.created_at
    submitted_jst = submitted_at.astimezone(ZoneInfo("Asia/Tokyo"))
    waiting_days = (datetime.now(ZoneInfo("Asia/Tokyo")).date() - submitted_jst.date()).days

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
        item_submit_log = _get_latest_submit_log(item)
        item_submitted = item_submit_log.acted_at if item_submit_log else item.created_at
        item_wait_days = (datetime.now(ZoneInfo("Asia/Tokyo")).date() - item_submitted.astimezone(ZoneInfo("Asia/Tokyo")).date()).days
        queue_items.append(
            {
                "project_id": item.id,
                "index": idx,
                "title": item.title,
                "submitted_date": format_jst_date(item_submitted, "%m/%d"),
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
# ■ 本部管理者：トップ画面
# =============================
@app.route("/top/hq")
@login_required
def hq_top():
    return render_template("hq_top.html", demo_role="hq")


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
        submit_log = _get_latest_submit_log(project)
        base_dt = (dept_log.acted_at if dept_log else None) or (submit_log.acted_at if submit_log else None) or project.created_at
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
