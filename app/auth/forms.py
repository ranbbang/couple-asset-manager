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


class AccountForm(FlaskForm):
    """Update the logged-in user's display name / email / password."""

    display_name = StringField(
        "이름", validators=[DataRequired(), Length(min=1, max=80)]
    )
    email = StringField("이메일", validators=[DataRequired(), Email(), Length(max=255)])
    current_password = PasswordField(
        "현재 비밀번호", validators=[DataRequired(message="변경하려면 현재 비밀번호를 입력해 주세요.")]
    )
    new_password = PasswordField(
        "새 비밀번호 (변경 시에만 입력)",
        validators=[Length(min=0, max=128)],
    )
    confirm_new_password = PasswordField(
        "새 비밀번호 확인",
        validators=[EqualTo("new_password", message="새 비밀번호가 일치하지 않습니다.")],
    )
    submit = SubmitField("저장")

    def validate_new_password(self, field):
        if field.data and len(field.data) < 8:
            raise ValidationError("새 비밀번호는 8자 이상이어야 합니다.")
