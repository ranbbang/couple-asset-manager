"""Category create/edit form."""
from flask_wtf import FlaskForm
from wtforms import BooleanField, SelectField, StringField, SubmitField
from wtforms.validators import DataRequired, Length, Optional, ValidationError

from ..constants import REPORT_GROUPS

# Sentinel for "no report group" (used by liabilities).
NO_GROUP = ""


class CategoryForm(FlaskForm):
    name = StringField(
        "이름", validators=[DataRequired(), Length(max=60)],
        render_kw={"placeholder": "예) 비상금, 부동산"},
    )
    icon = StringField(
        "아이콘 (이모지)", validators=[Optional(), Length(max=8)],
        render_kw={"placeholder": "💡", "autocomplete": "off"},
    )
    color = StringField(
        "색상", validators=[Optional(), Length(max=9)],
        default="#9DBE8A", render_kw={"type": "color"},
    )
    is_liability = BooleanField("부채 (순자산에서 차감)")
    is_real_estate = BooleanField("부동산 (‘부동산 제외 순자산’ 계산에서 빠짐)")
    is_liquid = BooleanField("유동자산 (당장 현금화 가능 — 비상금 계산에 포함)")
    report_group = SelectField(
        "리포트 그룹", validators=[Optional()],
        choices=[(NO_GROUP, "— (부채는 그룹 없음)")]
        + [(k, v["label"]) for k, v in REPORT_GROUPS.items()],
    )
    submit = SubmitField("저장")

    def validate_report_group(self, field):
        # Asset (non-liability) categories must belong to a report group.
        if not self.is_liability.data and not field.data:
            raise ValidationError("자산 카테고리는 리포트 그룹을 선택해야 합니다.")
