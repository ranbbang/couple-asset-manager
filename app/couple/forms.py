"""Forms for creating and joining a household."""
from flask_wtf import FlaskForm
from wtforms import StringField, SubmitField
from wtforms.validators import DataRequired, Length, Optional


class CreateCoupleForm(FlaskForm):
    name = StringField(
        "가구 이름", validators=[Optional(), Length(max=120)],
        render_kw={"placeholder": "예) 우리집"},
    )
    submit = SubmitField("가구 만들기")


class JoinCoupleForm(FlaskForm):
    invite_code = StringField(
        "초대 코드",
        validators=[DataRequired(), Length(min=4, max=16)],
        render_kw={"placeholder": "파트너에게 받은 코드", "autocomplete": "off"},
    )
    submit = SubmitField("파트너와 연결하기")
