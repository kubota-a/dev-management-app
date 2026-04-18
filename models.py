from datetime import datetime, timezone  # timezone = タイムゾーン情報
from flask_sqlalchemy import SQLAlchemy  # ORM（表のデータをPythonクラスで扱う仕組み）
from flask_login import UserMixin  # Flask-Login用の基本機能

db = SQLAlchemy()


class User(UserMixin, db.Model):
    """ユーザーテーブル。今はログイン土台用の最小構成。"""

    __tablename__ = "users"

    id = db.Column(db.Integer, primary_key=True)
    login_id = db.Column(db.String(50), unique=True, nullable=False)
    password_hash = db.Column(db.String(255), nullable=False)
    display_name = db.Column(db.String(100), nullable=False)
    role = db.Column(db.String(20), nullable=False)
    department_id = db.Column(db.Integer, db.ForeignKey("departments.id"), nullable=True)
    is_active_user = db.Column(db.Boolean, nullable=False, default=True)
    created_at = db.Column(
        db.DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
    )

    # Flask-Loginは is_active という名前の属性を見るので、
    # DBカラム名 is_active_user を返すプロパティ（見かけ上の属性）を用意する
    @property
    def is_active(self):
        return self.is_active_user


class Department(db.Model):
    """部門テーブル。PoC（概念検証）用に最小構成で持つ。"""

    __tablename__ = "departments"

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), unique=True, nullable=False)

    users = db.relationship("User", backref="department", lazy=True)