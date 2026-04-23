import os
from dotenv import load_dotenv  # .envファイルを読み込むライブラリ
from flask import Flask, render_template  # Webアプリ本体を作るフレームワーク
from flask_migrate import Migrate  # DBマイグレーション（DB構造変更の履歴管理）ツール
from flask_login import LoginManager  # ログイン管理用ライブラリ

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


@app.route("/login")
def login():
    """仮のログイン画面。後で本実装に置き換える。"""
    return "Login page"

# UI見本の通常ページ確認用ルート
@app.route("/ui-kit")
def ui_kit():
    return render_template("ui-kit.html")

# UI見本のダッシュボード確認用ルート
@app.route("/ui-kit-dashboard")
def ui_kit_dashboard():
    return render_template("ui-kit-dashboard.html")


if __name__ == "__main__":
    app.run(debug=True)
