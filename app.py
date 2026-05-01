import os
from dotenv import load_dotenv  # .envファイルを読み込むライブラリ
from flask import Flask, flash, redirect, render_template, url_for  # Webアプリ本体を作るフレームワーク
from flask_migrate import Migrate  # DBマイグレーション（DB構造変更の履歴管理）ツール
from flask_login import LoginManager, current_user, login_required, login_user, logout_user  # ログイン管理用ライブラリ
from flask_wtf import CSRFProtect
from werkzeug.security import check_password_hash

from forms import LoginForm
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
        return redirect(redirect_by_role(current_user))

    form = LoginForm()
    inline_error = None

    # 入力チェックを通過した場合のみ認証処理を行う
    if form.validate_on_submit():
        user = User.query.filter_by(login_id=form.login_id.data).first()

        # 認証可否に関わらず同じエラーメッセージを返す
        if user and user.is_active and check_password_hash(user.password_hash, form.password.data):
            login_user(user, remember=form.remember.data)
            flash("ログインに成功しました。", "success")
            return redirect(redirect_by_role(user))

        inline_error = "IDまたはパスワードが正しくありません"
    elif form.is_submitted():
        # 複数エラー時でも最初の1件だけ表示する
        for field in (form.login_id, form.password):
            if field.errors:
                inline_error = field.errors[0]
                break

    return render_template("login.html", form=form, inline_error=inline_error)


def redirect_by_role(user):
    if user.role == "applicant":
        return url_for("applicant_top")
    if user.role == "manager":
        return url_for("manager_top")
    if user.role == "hq":
        return url_for("hq_top")
    return url_for("index")


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
