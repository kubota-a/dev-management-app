from flask_wtf import FlaskForm
from wtforms import BooleanField, PasswordField, StringField, SubmitField
from wtforms.validators import DataRequired


class LoginForm(FlaskForm):
    login_id = StringField("ID", validators=[DataRequired(message="IDを入力してください")])
    password = PasswordField("パスワード", validators=[DataRequired(message="パスワードを入力してください")])
    remember = BooleanField("ログイン状態を保持", default=True)
    submit = SubmitField("ログイン")
