from datetime import date, datetime, timezone
from decimal import Decimal
from zoneinfo import ZoneInfo

from flask_login import UserMixin
from flask_sqlalchemy import SQLAlchemy


db = SQLAlchemy()


def utc_now() -> datetime:
    """UTCのaware datetimeを返す共通関数。"""
    return datetime.now(timezone.utc)


def jst_today() -> date:
    """日本時間(Asia/Tokyo)基準の業務日付を返す共通関数。"""
    return datetime.now(ZoneInfo("Asia/Tokyo")).date()


# 1. departments（部門）
class Department(db.Model):
    """部門マスタ。ユーザーと案件の所属先。"""

    __tablename__ = "departments"

    id = db.Column(db.BigInteger, primary_key=True, autoincrement=True)
    name = db.Column(db.String(100), unique=True, nullable=False)
    created_at = db.Column(db.DateTime(timezone=True), nullable=False, default=utc_now)
    updated_at = db.Column(
        db.DateTime(timezone=True),
        nullable=False,
        default=utc_now,
        onupdate=utc_now,
    )

    users = db.relationship("User", back_populates="department")
    memberships = db.relationship("DepartmentMembership", back_populates="department")
    projects = db.relationship("Project", back_populates="department")
    project_drafts = db.relationship("ProjectDraft", back_populates="department")
    yearly_budgets = db.relationship("DepartmentYearlyBudget", back_populates="department")


# 2. users（ユーザー）
class User(UserMixin, db.Model):
    """ログインユーザー。Flask-Login対応。"""

    __tablename__ = "users"
    __table_args__ = (
        db.CheckConstraint(
            "role IN ('applicant', 'manager', 'hq')",
            name="ck_users_role_allowed",
        ),
    )

    id = db.Column(db.BigInteger, primary_key=True, autoincrement=True)
    login_id = db.Column(db.String(100), unique=True, nullable=False)
    password_hash = db.Column(db.Text, nullable=False)
    display_name = db.Column(db.String(100), nullable=False)
    role = db.Column(db.String(20), nullable=False, index=True)
    department_id = db.Column(db.BigInteger, db.ForeignKey("departments.id"), nullable=True)
    is_active = db.Column(db.Boolean, nullable=False, default=True)
    created_at = db.Column(db.DateTime(timezone=True), nullable=False, default=utc_now)
    updated_at = db.Column(
        db.DateTime(timezone=True),
        nullable=False,
        default=utc_now,
        onupdate=utc_now,
    )

    department = db.relationship("Department", back_populates="users")
    member_profile = db.relationship("DepartmentMember", back_populates="user", uselist=False)
    projects_as_applicant = db.relationship(
        "Project",
        foreign_keys="Project.applicant_id",
        back_populates="applicant",
    )
    notifications = db.relationship("Notification", back_populates="user")
    project_drafts = db.relationship("ProjectDraft", back_populates="user")
    project_reports = db.relationship("ProjectReport", back_populates="reporter")
    project_status_logs = db.relationship("ProjectStatusLog", back_populates="actor")


# 3. department_members（部門メンバー）
class DepartmentMember(db.Model):
    """ログイン有無を問わず、タスク担当候補となる部門メンバー。"""

    __tablename__ = "department_members"

    id = db.Column(db.BigInteger, primary_key=True, autoincrement=True)
    user_id = db.Column(db.BigInteger, db.ForeignKey("users.id"), nullable=True, unique=True)
    display_name = db.Column(db.String(100), nullable=False)
    email = db.Column(db.String(255), nullable=True)
    can_assign_task = db.Column(db.Boolean, nullable=False, default=True)
    is_active = db.Column(db.Boolean, nullable=False, default=True)
    created_at = db.Column(db.DateTime(timezone=True), nullable=False, default=utc_now)
    updated_at = db.Column(
        db.DateTime(timezone=True),
        nullable=False,
        default=utc_now,
        onupdate=utc_now,
    )

    user = db.relationship("User", back_populates="member_profile")
    memberships = db.relationship("DepartmentMembership", back_populates="member")
    tasks = db.relationship("Task", back_populates="assignee_member")


# 4. department_memberships（部門所属）
class DepartmentMembership(db.Model):
    """部門メンバーと部門の所属関係。兼務と主所属を表現する。"""

    __tablename__ = "department_memberships"
    __table_args__ = (
        db.UniqueConstraint(
            "member_id",
            "department_id",
            name="uq_department_memberships_member_department",
        ),
    )

    id = db.Column(db.BigInteger, primary_key=True, autoincrement=True)
    member_id = db.Column(
        db.BigInteger,
        db.ForeignKey("department_members.id"),
        nullable=False,
        index=True,
    )
    department_id = db.Column(
        db.BigInteger,
        db.ForeignKey("departments.id"),
        nullable=False,
        index=True,
    )
    is_primary = db.Column(db.Boolean, nullable=False, default=False)
    role_label = db.Column(db.String(50), nullable=True)
    joined_on = db.Column(db.Date, nullable=True)
    left_on = db.Column(db.Date, nullable=True)
    created_at = db.Column(db.DateTime(timezone=True), nullable=False, default=utc_now)

    member = db.relationship("DepartmentMember", back_populates="memberships")
    department = db.relationship("Department", back_populates="memberships")


# 5. projects（案件）
class Project(db.Model):
    """申請〜承認〜進行〜完了までを管理する案件。"""

    __tablename__ = "projects"
    __table_args__ = (
        db.CheckConstraint(
            "status IN ('department_pending', 'hq_pending', 'in_progress', 'completed', 'rejected')",
            name="ck_projects_status_allowed",
        ),
        db.CheckConstraint(
            "approval_stage IN ('department_pending', 'hq_pending', 'approved', 'rejected')",
            name="ck_projects_approval_stage_allowed",
        ),
        db.CheckConstraint(
            "estimated_person_months >= 0",
            name="ck_projects_estimated_person_months_non_negative",
        ),
        db.CheckConstraint(
            "estimated_budget_amount >= 0",
            name="ck_projects_estimated_budget_amount_non_negative",
        ),
        db.CheckConstraint(
            "approved_budget_amount IS NULL OR approved_budget_amount >= 0",
            name="ck_projects_approved_budget_amount_non_negative",
        ),
    )

    id = db.Column(db.BigInteger, primary_key=True, autoincrement=True)
    project_code = db.Column(db.String(20), unique=True, nullable=False, index=True)
    title = db.Column(db.String(200), nullable=False)
    purpose = db.Column(db.Text, nullable=False)
    summary = db.Column(db.Text, nullable=True)
    estimated_person_months = db.Column(db.Numeric(12, 2), nullable=False)
    estimated_budget_amount = db.Column(db.Numeric(12, 2), nullable=False)
    approved_budget_amount = db.Column(db.Numeric(12, 2), nullable=True)
    applicant_id = db.Column(db.BigInteger, db.ForeignKey("users.id"), nullable=False, index=True)
    department_id = db.Column(db.BigInteger, db.ForeignKey("departments.id"), nullable=False, index=True)
    status = db.Column(db.String(30), nullable=False, index=True)
    approval_stage = db.Column(db.String(30), nullable=False, index=True)
    rejection_comment = db.Column(db.Text, nullable=True)
    planned_start_date = db.Column(db.Date, nullable=False)
    planned_end_date = db.Column(db.Date, nullable=True)
    monthly_report_comment = db.Column(db.Text, nullable=True)
    monthly_report_updated_at = db.Column(db.DateTime(timezone=True), nullable=True)
    final_rejected_at = db.Column(db.DateTime(timezone=True), nullable=True)
    approved_at = db.Column(db.DateTime(timezone=True), nullable=True)
    completed_at = db.Column(db.DateTime(timezone=True), nullable=True)
    created_at = db.Column(db.DateTime(timezone=True), nullable=False, default=utc_now)
    updated_at = db.Column(
        db.DateTime(timezone=True),
        nullable=False,
        default=utc_now,
        onupdate=utc_now,
    )

    applicant = db.relationship(
        "User",
        foreign_keys=[applicant_id],
        back_populates="projects_as_applicant",
    )
    department = db.relationship("Department", back_populates="projects")
    tasks = db.relationship("Task", back_populates="project")
    notifications = db.relationship("Notification", back_populates="project")
    budget_actual_logs = db.relationship("BudgetActualLog", back_populates="project")
    project_reports = db.relationship("ProjectReport", back_populates="project")
    project_status_logs = db.relationship("ProjectStatusLog", back_populates="project")

    @property
    def total_actual_amount(self) -> Decimal:
        """予算実績ログの累計額を返す。"""
        return sum(((log.amount or Decimal("0")) for log in self.budget_actual_logs), Decimal("0"))

    @property
    def budget_consumption_rate(self) -> Decimal | None:
        """予算消費率(%)。分母は承認後予算を優先し、なければ申請予算を使う。"""
        base_budget = self.approved_budget_amount
        if base_budget is None:
            base_budget = self.estimated_budget_amount

        if not base_budget or base_budget <= 0:
            return None

        return (self.total_actual_amount / base_budget) * Decimal("100")

    @property
    def task_summary(self) -> dict[str, int]:
        """タスク件数サマリー。"""
        counts = {"total": 0, "not_started": 0, "in_progress": 0, "done": 0}
        for task in self.tasks:
            counts["total"] += 1
            if task.status in counts:
                counts[task.status] += 1
        return counts

    @property
    def has_overdue_task(self) -> bool:
        """期限切れ未完了タスクがあるか。"""
        today = jst_today()
        return any(task.due_date < today and task.status != "done" for task in self.tasks)


# 6. tasks（タスク）
class Task(db.Model):
    """案件配下の作業タスク。"""

    __tablename__ = "tasks"
    __table_args__ = (
        db.CheckConstraint(
            "status IN ('not_started', 'in_progress', 'done')",
            name="ck_tasks_status_allowed",
        ),
        db.CheckConstraint(
            "progress_rate >= 0 AND progress_rate <= 100",
            name="ck_tasks_progress_rate_range",
        ),
    )

    id = db.Column(db.BigInteger, primary_key=True, autoincrement=True)
    project_id = db.Column(db.BigInteger, db.ForeignKey("projects.id"), nullable=False, index=True)
    assignee_member_id = db.Column(
        db.BigInteger,
        db.ForeignKey("department_members.id"),
        nullable=True,
        index=True,
    )
    title = db.Column(db.String(200), nullable=False)
    assignee_name = db.Column(db.String(100), nullable=False)
    status = db.Column(db.String(20), nullable=False, index=True)
    progress_rate = db.Column(db.Integer, nullable=False)
    start_date = db.Column(db.Date, nullable=True)
    due_date = db.Column(db.Date, nullable=False, index=True)
    created_at = db.Column(db.DateTime(timezone=True), nullable=False, default=utc_now)
    updated_at = db.Column(
        db.DateTime(timezone=True),
        nullable=False,
        default=utc_now,
        onupdate=utc_now,
    )

    project = db.relationship("Project", back_populates="tasks")
    assignee_member = db.relationship("DepartmentMember", back_populates="tasks")


# 7. notifications（通知）
class Notification(db.Model):
    """ユーザー向け通知。ヘッダードロップダウン表示向けに単一メッセージで管理。"""

    __tablename__ = "notifications"
    __table_args__ = (
        db.CheckConstraint(
            """
            (
              (
                type IN (
                  'application_received',
                  'department_pending',
                  'hq_pending',
                  'approved',
                  'rejected',
                  'completed'
                )
                AND project_id IS NOT NULL
              )
              OR
              (
                type IN ('system', 'announcement')
                AND project_id IS NULL
              )
            )
            """,
            name="ck_notifications_type_project_required",
        ),
    )

    id = db.Column(db.BigInteger, primary_key=True, autoincrement=True)
    user_id = db.Column(db.BigInteger, db.ForeignKey("users.id"), nullable=False, index=True)
    project_id = db.Column(db.BigInteger, db.ForeignKey("projects.id"), nullable=True, index=True)
    type = db.Column(db.String(30), nullable=False, index=True)
    message = db.Column(db.Text, nullable=False)
    is_read = db.Column(db.Boolean, nullable=False, default=False, index=True)
    created_at = db.Column(db.DateTime(timezone=True), nullable=False, default=utc_now, index=True)

    user = db.relationship("User", back_populates="notifications")
    project = db.relationship("Project", back_populates="notifications")


# 8. budget_actual_logs（予算実績ログ）
class BudgetActualLog(db.Model):
    """案件の予算実績を積み上げ記録するログ。"""

    __tablename__ = "budget_actual_logs"
    __table_args__ = (
        db.CheckConstraint("amount >= 0", name="ck_budget_actual_logs_amount_non_negative"),
    )

    id = db.Column(db.BigInteger, primary_key=True, autoincrement=True)
    project_id = db.Column(db.BigInteger, db.ForeignKey("projects.id"), nullable=False, index=True)
    amount = db.Column(db.Numeric(12, 2), nullable=False)
    memo = db.Column(db.Text, nullable=True)
    recorded_on = db.Column(db.Date, nullable=False, index=True)
    created_at = db.Column(db.DateTime(timezone=True), nullable=False, default=utc_now)

    project = db.relationship("Project", back_populates="budget_actual_logs")


# 9. project_reports（案件報告履歴）
class ProjectReport(db.Model):
    """案件の月次報告・完了報告の履歴を管理する。"""

    __tablename__ = "project_reports"
    __table_args__ = (
        db.CheckConstraint(
            "report_type IN ('monthly', 'completion')",
            name="ck_project_reports_report_type_allowed",
        ),
        db.CheckConstraint(
            """
            (
              report_type = 'monthly'
              AND report_month IS NOT NULL
            )
            OR
            (
              report_type = 'completion'
              AND report_month IS NULL
            )
            """,
            name="ck_project_reports_month_rule",
        ),
    )

    id = db.Column(db.BigInteger, primary_key=True, autoincrement=True)
    project_id = db.Column(db.BigInteger, db.ForeignKey("projects.id"), nullable=False, index=True)
    reporter_id = db.Column(db.BigInteger, db.ForeignKey("users.id"), nullable=False, index=True)
    report_type = db.Column(db.String(20), nullable=False, index=True)
    report_month = db.Column(db.Date, nullable=True, index=True)
    comment = db.Column(db.Text, nullable=False)
    submitted_at = db.Column(db.DateTime(timezone=True), nullable=False, default=utc_now, index=True)
    created_at = db.Column(db.DateTime(timezone=True), nullable=False, default=utc_now)
    updated_at = db.Column(
        db.DateTime(timezone=True),
        nullable=False,
        default=utc_now,
        onupdate=utc_now,
    )

    project = db.relationship("Project", back_populates="project_reports")
    reporter = db.relationship("User", back_populates="project_reports")


# 10. project_status_logs（案件ステータス履歴）
class ProjectStatusLog(db.Model):
    """案件ステータス変更の監査ログ。"""

    __tablename__ = "project_status_logs"
    __table_args__ = (
        db.CheckConstraint(
            "action IN ('submit', 'approve_department', 'approve_hq', 'reject_department', 'reject_hq', 'complete')",
            name="ck_project_status_logs_action_allowed",
        ),
        db.CheckConstraint(
            "from_status IS NULL OR from_status IN ('department_pending', 'hq_pending', 'in_progress', 'completed', 'rejected')",
            name="ck_project_status_logs_from_status_allowed",
        ),
        db.CheckConstraint(
            "to_status IN ('department_pending', 'hq_pending', 'in_progress', 'completed', 'rejected')",
            name="ck_project_status_logs_to_status_allowed",
        ),
    )

    id = db.Column(db.BigInteger, primary_key=True, autoincrement=True)
    project_id = db.Column(db.BigInteger, db.ForeignKey("projects.id"), nullable=False, index=True)
    actor_id = db.Column(db.BigInteger, db.ForeignKey("users.id"), nullable=False, index=True)
    from_status = db.Column(db.String(30), nullable=True)
    to_status = db.Column(db.String(30), nullable=False, index=True)
    action = db.Column(db.String(30), nullable=False, index=True)
    comment = db.Column(db.Text, nullable=True)
    acted_at = db.Column(db.DateTime(timezone=True), nullable=False, default=utc_now, index=True)

    project = db.relationship("Project", back_populates="project_status_logs")
    actor = db.relationship("User", back_populates="project_status_logs")


# 11. project_drafts（案件下書き）
class ProjectDraft(db.Model):
    """申請フォームの一時保存データ。"""

    __tablename__ = "project_drafts"

    id = db.Column(db.BigInteger, primary_key=True, autoincrement=True)
    user_id = db.Column(db.BigInteger, db.ForeignKey("users.id"), nullable=False, index=True)
    title = db.Column(db.String(200), nullable=True)
    purpose = db.Column(db.Text, nullable=True)
    department_id = db.Column(db.BigInteger, db.ForeignKey("departments.id"), nullable=True, index=True)
    estimated_person_months = db.Column(db.Numeric(12, 2), nullable=True)
    estimated_budget_amount = db.Column(db.Numeric(12, 2), nullable=True)
    planned_start_date = db.Column(db.Date, nullable=True)
    planned_end_date = db.Column(db.Date, nullable=True)
    created_at = db.Column(db.DateTime(timezone=True), nullable=False, default=utc_now, index=True)
    updated_at = db.Column(
        db.DateTime(timezone=True),
        nullable=False,
        default=utc_now,
        onupdate=utc_now,
    )

    user = db.relationship("User", back_populates="project_drafts")
    department = db.relationship("Department", back_populates="project_drafts")


# 12. department_yearly_budgets（部門年間予算）
class DepartmentYearlyBudget(db.Model):
    """部門ごとの年間予算を年度単位で管理する。"""

    __tablename__ = "department_yearly_budgets"
    __table_args__ = (
        db.CheckConstraint(
            "annual_budget_amount >= 0",
            name="ck_department_yearly_budgets_annual_budget_amount_non_negative",
        ),
        db.CheckConstraint(
            "fiscal_year >= 2000",
            name="ck_department_yearly_budgets_fiscal_year_min",
        ),
        db.UniqueConstraint(
            "department_id",
            "fiscal_year",
            name="uq_department_yearly_budgets_department_id_fiscal_year",
        ),
    )

    id = db.Column(db.BigInteger, primary_key=True, autoincrement=True)
    department_id = db.Column(db.BigInteger, db.ForeignKey("departments.id"), nullable=False, index=True)
    fiscal_year = db.Column(db.Integer, nullable=False, index=True)
    annual_budget_amount = db.Column(db.Numeric(12, 2), nullable=False)
    created_at = db.Column(db.DateTime(timezone=True), nullable=False, default=utc_now)
    updated_at = db.Column(
        db.DateTime(timezone=True),
        nullable=False,
        default=utc_now,
        onupdate=utc_now,
    )

    # 部門との紐づき（部門1 : 年度予算N）
    department = db.relationship("Department", back_populates="yearly_budgets")
