from . import auth_bp
from datetime import timedelta
from app.utils.utils import logged_in_active_user_required
from flask import jsonify, request, current_app, make_response
from flask_wtf.csrf import generate_csrf
from flask_login import current_user, login_user, logout_user
from flask_mail import Message
from passlib.pwd import genword
from flask_cors import CORS, cross_origin
from app import db, mail
from app.blueprints.auth.models import ResetPasswordToken, User
from .validators import (
    ChangePasswordValidator,
    ForgotPasswordValidator,
    LoginValidator,
    ResetPasswordValidator,
)


##############################################################################
# LOGIN / LOGOUT
##############################################################################


@auth_bp.route("/get-csrf", methods=["GET"])
def set_xsrf_cookie():
    """
    Sets CSRF-TOKEN cookie
    """
    response = make_response(jsonify({"message": "success"}), 200)
    response.set_cookie("CSRF-TOKEN", generate_csrf(),samesite='None', secure=True)
    return response


@auth_bp.route("/login", methods=["POST"])
def login():
    """
    Endpoint to login

    Requires JSON body with following keys:
    - email
    - password

    Requires X-CSRF-Token in header, obtained from cookie set by /get-csrf
    """

    form = LoginValidator.from_json(request.get_json())
    if "X-CSRF-Token" in request.headers:
        form.csrf_token.data = request.headers.get("X-CSRF-Token")
    else:
        return jsonify(message="X-CSRF-Token required in header"), 403

    if form.validate():
        user = User.query.filter_by(email=form.email.data).first()

        if user:
            if not user.is_active():
                return jsonify(message="INACTIVE_USER"), 403

            if user.verify_password(form.password.data):
                login_user(user, remember=True, duration=timedelta(days=7))
                return jsonify(message="Success: logged in"), 200
            else:
                return jsonify(message="UNAUTHORIZED"), 401
        else:
            return jsonify(message="UNAUTHORIZED"), 401

    else:
        return jsonify(message=form.errors), 422


@auth_bp.route("/logout", methods=["GET"])
@logged_in_active_user_required
def logout():
    logout_user()
    return jsonify(message="Success: logged out"), 200


##############################################################################
# PASSWORD MANAGEMENT
##############################################################################


@auth_bp.route("/change-password", methods=["POST"])
@logged_in_active_user_required
def change_password():
    """
    Endpoint to change password, user must be logged in

    Requires JSON body with following keys:
    - cur_password
    - new_password
    - confirm

    Requires X-CSRF-Token in header, obtained from cookie set by /get-csrf
    """
    form = ChangePasswordValidator.from_json(request.get_json())
    if "X-CSRF-Token" in request.headers:
        form.csrf_token.data = request.headers.get("X-CSRF-Token")
    else:
        return jsonify(message="X-CSRF-Token required in header"), 403

    if form.validate():
        if current_user.verify_password(form.cur_password.data):
            current_user.change_password(form.new_password.data)
            return jsonify(message="Success: password changed"), 200
        else:
            return jsonify(message="Wrong password"), 403
    else:
        return jsonify(message=form.errors), 422


@auth_bp.route("/forgot-password", methods=["POST"])
def forgot_password():
    """
    Endpoint to request reset password link by email
    User must not be logged in

    Requires JSON body with following keys:
    - email

    Requires X-CSRF-Token in header, obtained from cookie set by /get-csrf
    """
    if current_user.is_authenticated:
        return jsonify(message="Already logged in - use /change-password"), 400

    form = ForgotPasswordValidator.from_json(request.get_json())
    if "X-CSRF-Token" in request.headers:
        form.csrf_token.data = request.headers.get("X-CSRF-Token")
    else:
        return jsonify(message="X-CSRF-Token required in header"), 403

    if form.validate():
        user = User.query.filter_by(email=form.email.data).first()

        if user:
            email_token = genword(length=32, charset="ascii_62")
            rpt = ResetPasswordToken(user.user_uid, email_token)

            # Add this rpt, delete all other rpts for this user
            ResetPasswordToken.query.filter_by(user_uid=user.user_uid).delete()
            db.session.add(rpt)
            db.session.commit()

            rp_message = Message(
                subject="SurveyStream Reset Password",
                html="Reset your SurveyStream password by clicking <a href='%s/reset-password/%s/%s'>here</a>.<br><br>The link will expire in one hour."
                % (current_app.config["REACT_BASE_URL"], rpt.reset_uid, email_token),
                recipients=[user.email],
            )
            mail.send(rp_message)

        # For security, return 200/Success in any situation!
        # Don't let people figure out if they entered a valid email or not
        return jsonify(message="Request processed"), 200

    else:
        return jsonify(message=form.errors), 422


@auth_bp.route("/reset-password", methods=["POST"])
def reset_password():
    """
    Endpoint to reset password
    User must not be logged in

    Requires JSON body with following keys:
    - rpt_id
    - rpt_token
    - new_password
    - confirm

    Requires X-CSRF-Token in header, obtained from cookie set by /get-csrf
    """
    if current_user.is_authenticated:
        return jsonify(message="Already logged in - use /change-password"), 400

    form = ResetPasswordValidator.from_json(request.get_json())
    if "X-CSRF-Token" in request.headers:
        form.csrf_token.data = request.headers.get("X-CSRF-Token")
    else:
        return jsonify(message="X-CSRF-Token required in header"), 403

    if form.validate():
        rpt_to_check = ResetPasswordToken.query.get(form.rpt_id.data)
        if rpt_to_check and rpt_to_check.use_token(form.rpt_token.data):
            user = User.query.get(rpt_to_check.user_uid)
            user.change_password(form.new_password.data)
            db.session.delete(rpt_to_check)
            db.session.commit()
            return jsonify(message="Success: password reset"), 200
        else:
            return jsonify(message="Invalid link"), 404
    else:
        return jsonify(message=form.errors), 422
