"""Authentication routes."""
from flask import Blueprint, flash, redirect, render_template, request, url_for
from flask_login import current_user, login_required, login_user, logout_user

from ..extensions import db
from ..models import User
from .forms import AccountForm, LoginForm, SignupForm

auth_bp = Blueprint("auth", __name__)


@auth_bp.route("/signup", methods=["GET", "POST"])
def signup():
    if current_user.is_authenticated:
        return redirect(url_for("main.dashboard"))

    form = SignupForm()
    if form.validate_on_submit():
        email = form.email.data.strip().lower()
        if User.query.filter_by(email=email).first():
            flash("이미 가입된 이메일입니다.", "error")
            return render_template("auth/signup.html", form=form)

        user = User(email=email, display_name=form.display_name.data.strip())
        user.set_password(form.password.data)
        db.session.add(user)
        db.session.commit()

        login_user(user)
        flash(f"환영합니다, {user.display_name}님! 이제 가구를 설정해 주세요.", "success")
        return redirect(url_for("couple.setup"))

    return render_template("auth/signup.html", form=form)


@auth_bp.route("/login", methods=["GET", "POST"])
def login():
    if current_user.is_authenticated:
        return redirect(url_for("main.dashboard"))

    form = LoginForm()
    if form.validate_on_submit():
        email = form.email.data.strip().lower()
        user = User.query.filter_by(email=email).first()
        if user is None or not user.check_password(form.password.data):
            flash("이메일 또는 비밀번호가 올바르지 않습니다.", "error")
            return render_template("auth/login.html", form=form)

        login_user(user, remember=True)
        # Respect ?next= but only for local paths (open-redirect guard).
        next_page = request.args.get("next")
        if not next_page or not next_page.startswith("/") or next_page.startswith("//"):
            next_page = url_for("main.dashboard")
        return redirect(next_page)

    return render_template("auth/login.html", form=form)


@auth_bp.route("/logout", methods=["POST"])
@login_required
def logout():
    logout_user()
    flash("로그아웃되었습니다.", "info")
    return redirect(url_for("auth.login"))


@auth_bp.route("/account", methods=["GET", "POST"])
@login_required
def account():
    form = AccountForm(obj=current_user)
    if form.validate_on_submit():
        if not current_user.check_password(form.current_password.data):
            flash("현재 비밀번호가 올바르지 않습니다.", "error")
            return render_template("auth/account.html", form=form)

        email = form.email.data.strip().lower()
        if email != current_user.email:
            if User.query.filter(User.email == email, User.id != current_user.id).first():
                flash("이미 사용 중인 이메일입니다.", "error")
                return render_template("auth/account.html", form=form)
            current_user.email = email

        current_user.display_name = form.display_name.data.strip()

        if form.new_password.data:
            current_user.set_password(form.new_password.data)

        db.session.commit()
        flash("계정 정보가 저장되었습니다.", "success")
        return redirect(url_for("auth.account"))

    return render_template("auth/account.html", form=form)
