import os
import secrets
from hmac import compare_digest
from dotenv import load_dotenv  # .envファイルを読み込むライブラリ
from flask import Flask, flash, redirect, render_template, request, session, url_for  # Webアプリ本体を作るフレームワーク
from flask_migrate import Migrate  # DBマイグレーション（DB構造変更の履歴管理）ツール
from flask_login import LoginManager, current_user, login_user  # ログイン管理用ライブラリ
from werkzeug.security import check_password_hash

from models import db, User  # db = SQLAlchemy本体、User = ユーザーモデル

# .envファイルを読み込む
load_dotenv()

app = Flask(__name__)

# 基本設定
app.config["SECRET_KEY"] = os.getenv("SECRET_KEY", "dev-secret-key")
app.config["SQLALCHEMY_DATABASE_URI"] = os.getenv("DATABASE_URL")
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False

# 拡張機能（Flaskに追加機能を付けるライブラリ）を初期化
# app に db 情報を登録し、マイグレーションとログイン管理を有効化
db.init_app(app)
migrate = Migrate(app, db)
login_manager = LoginManager(app)

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


@app.route("/login", methods=["GET", "POST"])
def login():
    """ログイン画面とログイン処理。"""
    if current_user.is_authenticated:
        return redirect(get_post_login_redirect(current_user.role))

    if request.method == "POST":
        if not validate_csrf_token(request.form.get("csrf_token")):
            flash("セッションが無効です。もう一度ログインしてください。", "danger")
            return redirect(url_for("login"))

        login_id = (request.form.get("id") or "").strip()
        password = request.form.get("password") or ""
        remember = request.form.get("remember") == "1"

        user = User.query.filter_by(login_id=login_id).first()
        if user and user.is_active and check_password_hash(user.password_hash, password):
            login_user(user, remember=remember)
            return redirect(get_post_login_redirect(user.role))

        flash("IDまたはパスワードが正しくありません。", "danger")
        return render_template(
            "login.html",
            csrf_token=ensure_csrf_token(),
            entered_id=login_id,
            remember_checked=remember,
        )

    return render_template("login.html", csrf_token=ensure_csrf_token(), entered_id="", remember_checked=True)


def ensure_csrf_token() -> str:
    token = session.get("login_csrf_token")
    if not token:
        token = secrets.token_urlsafe(32)
        session["login_csrf_token"] = token
    return token


def validate_csrf_token(token: str | None) -> bool:
    session_token = session.get("login_csrf_token")
    if not token or not session_token:
        return False
    return compare_digest(token, session_token)


def get_post_login_redirect(role: str) -> str:
    if role == "applicant":
        return url_for("applicant_top")
    if role == "manager":
        return url_for("manager_top")
    if role == "hq":
        return url_for("hq_top")
    return url_for("index")

# UI見本の通常ページ確認用ルート
@app.route("/ui-kit")
def ui_kit():
    return render_template("ui-kit.html")

# UI見本のダッシュボード確認用ルート
@app.route("/ui-kit-dashboard")
def ui_kit_dashboard():
    return render_template("ui-kit-dashboard.html")


@app.route("/sample/applicant")
def applicant_top():
    return render_template("sample_applicant_dashboard.html", demo_role="applicant")


@app.route("/sample/manager")
def manager_top():
    return render_template("sample_manager_dashboard.html", demo_role="manager")


@app.route("/sample/hq")
def hq_top():
    return render_template("sample_hq_dashboard.html", demo_role="hq")


if __name__ == "__main__":
    app.run(debug=True)
