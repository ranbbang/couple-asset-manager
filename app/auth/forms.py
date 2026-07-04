"""WTForms definitions for authentication."""
from flask_wtf import FlaskForm
from wtforms import PasswordField, StringField, SubmitField
from wtforms.validators import (
    DataRequired,
    Email,
    EqualTo,
    Length,
    ValidationError,
)


class SignupForm(FlaskForm):
    display_name = StringField(
        "이름", validators=[DataRequired(), Length(min=1, max=80)]
    )
    email = StringField("이메일", validators=[DataRequired(), Email(), Length(max=255)])
    password = PasswordField(
        "비밀번호", validators=[DataRequired(), Length(min=8, max=128)]
    )
    confirm = PasswordField(
        "비밀번호 확인",
        validators=[DataRequired(), EqualTo("password", message="비밀번호가 일치하지 않습니다.")],
    )
    submit = SubmitField("회원가입")


class LoginForm(FlaskForm):
    email = StringField("이메일", validators=[DataRequired(), Email()])
    password = PasswordField("비밀번호", validators=[DataRequired()])
    submit = SubmitField("로그인")
