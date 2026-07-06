"""Shared goal form.

A goal can be linked to whole categories and/or individual accounts; when linked,
progress is auto-computed from their live value. The manual saved/stocks amounts
are a fallback used only when nothing is linked.
"""
from flask_wtf import FlaskForm
from wtforms import (
    DecimalField,
    SelectField,
    SelectMultipleField,
    StringField,
    SubmitField,
)
from wtforms.validators import DataRequired, Length, NumberRange, Optional

# Sentinel value in the owner <select> meaning "shared couple goal".
JOINT_OWNER_VALUE = "joint"


class GoalForm(FlaskForm):
    name = StringField(
        "목표 이름",
        validators=[DataRequired(), Length(max=120)],
        render_kw={"placeholder": "예) 전세 보증금, 유럽 여행"},
    )
    target_amount = DecimalField(
        "목표 금액 (₩)",
        places=0,
        validators=[DataRequired(), NumberRange(min=1, message="1 이상으로 입력하세요.")],
        render_kw={"placeholder": "0", "min": "1", "step": "1"},
    )
    owner = SelectField("목표 주체", validators=[DataRequired()])
    # Auto-linked sources (choices populated in the route).
    linked_categories = SelectMultipleField("연동 카테고리", coerce=int)
    linked_assets = SelectMultipleField("연동 개별 자산", coerce=int)

    # Manual fallback (used only when nothing is linked).
    saved_amount = DecimalField(
        "현재 저축액 (₩) — 수동",
        places=0, validators=[Optional(), NumberRange(min=0)], default=0,
        render_kw={"placeholder": "0", "min": "0", "step": "1"},
    )
    stocks_amount = DecimalField(
        "현재 투자액 (₩) — 수동",
        places=0, validators=[Optional(), NumberRange(min=0)], default=0,
        render_kw={"placeholder": "0", "min": "0", "step": "1"},
    )
    submit = SubmitField("저장")
