import os
from datetime import date, datetime
from decimal import Decimal, InvalidOperation
from zoneinfo import ZoneInfo
from dotenv import load_dotenv  # .envファイルを読み込むライブラリ
from flask import Flask, flash, jsonify, redirect, render_template, request, url_for  # Webアプリ本体を作るフレームワーク
from flask_migrate import Migrate  # DBマイグレーション（DB構造変更の履歴管理）ツール
from flask_login import LoginManager, current_user, login_required, login_user, logout_user  # ログイン管理用ライブラリ
from flask_wtf import CSRFProtect
from sqlalchemy.orm import joinedload
from werkzeug.security import check_password_hash

from forms import LoginForm
from models import (
    Department,
    Notification,
    Project,
    ProjectDraft,
    ProjectStatusLog,
    User,
    db,
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
            flash("ログインに成功しました。", "success")
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


def format_business_date(d: date | None, pattern: str = "%Y/%m/%d") -> str:
    """Date型を業務日付として表示整形する。"""
    if d is None:
        return "未設定"
    return d.strftime(pattern)


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
        "status_meta": f"申請日：{format_jst_date(project.created_at)} ／ {project.project_code}",
        "created_at_display": format_jst_date(project.created_at, "%Y/%m/%d %H:%M"),
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
                "date": format_jst_date(
                    submit_log.acted_at if submit_log else project.created_at,
                    "%m/%d",
                ),
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
    if start_err or end_err:
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
        active_menu="applicant_new",
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
        active_menu="applicant_confirm",
        status_view=build_project_status_view_data(project),
        switcher_options=switcher_options,
        switcher_count=len(switcher_options),
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
# ■ 本部管理者：トップ画面
# =============================
@app.route("/top/hq")
@login_required
def hq_top():
    return render_template("hq_top.html", demo_role="hq")


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
