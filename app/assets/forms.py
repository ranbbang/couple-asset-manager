"""Account (asset) entry form.

An account's value comes from its holdings (cash / stock), which are parsed
manually from the request in the route (dynamic rows). This form only covers the
account-level fields; category/owner choices are populated in the route.
"""
from flask_wtf import FlaskForm
from wtforms import BooleanField, SelectField, StringField, SubmitField, TextAreaField
from wtforms.validators import DataRequired, Length, Optional

# Sentinel value used in the owner <select> to mean "jointly owned".
JOINT_OWNER_VALUE = "joint"


class AssetForm(FlaskForm):
    name = StringField(
        "계좌 / 자산 이름",
        validators=[DataRequired(), Length(max=120)],
        render_kw={"placeholder": "예) 토스증권, 카카오뱅크 입출금"},
    )
    category = SelectField("카테고리", coerce=int, validators=[DataRequired()])
    owner = SelectField("소유자", validators=[DataRequired()])
    institution = StringField(
        "기관 / 메모",
        validators=[Optional(), Length(max=120)],
        render_kw={"placeholder": "예) 토스증권"},
    )
    notes = TextAreaField(
        "상세 메모", validators=[Optional(), Length(max=500)], render_kw={"rows": 2}
    )
    exclude_from_stats = BooleanField("통계에서 제외 (목록에는 표시되지만 합계·차트·추이에서 빠집니다)")
    submit = SubmitField("저장")
