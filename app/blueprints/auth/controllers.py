from . import auth_bp
from datetime import timedelta
from app.utils.utils import logged_in_active_user_required, validate_payload
from flask import jsonify, request, current_app, make_response
from flask_wtf.csrf import generate_csrf
from flask_login import current_user, login_user, logout_user
from flask_mail import Message
from passlib.pwd import genword
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
    response.set_cookie("CSRF-TOKEN", generate_csrf(), samesite="None", secure=True)
    return response


@auth_bp.route("/login", methods=["POST"])
@validate_payload(LoginValidator)
def login(validated_payload):
    """
    Endpoint to login

    Requires JSON body with following keys:
    - email
    - password

    Requires X-CSRF-Token in header, obtained from cookie set by /get-csrf
    """

    email = validated_payload.email.data
    password = validated_payload.password.data

    user = User.query.filter_by(email=email).first()

    if user:
        if not user.is_active():
            return jsonify(message="INACTIVE_USER"), 403

        if user.verify_password(password):
            login_user(user, remember=True, duration=timedelta(days=7))
            return jsonify(message="Success: logged in"), 200
        else:
            return jsonify(message="UNAUTHORIZED"), 401
    else:
        return jsonify(message="UNAUTHORIZED"), 401


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
@validate_payload(ChangePasswordValidator)
def change_password(validated_payload):
    """
    Endpoint to change password, user must be logged in

    Requires JSON body with following keys:
    - cur_password
    - new_password
    - confirm

    Requires X-CSRF-Token in header, obtained from cookie set by /get-csrf
    """

    cur_password = validated_payload.cur_password.data
    new_password = validated_payload.new_password.data

    if current_user.verify_password(cur_password):
        current_user.change_password(new_password)
        return jsonify(message="Success: password changed"), 200
    else:
        return jsonify(message="Wrong password"), 403


@auth_bp.route("/forgot-password", methods=["POST"])
@validate_payload(ForgotPasswordValidator)
def forgot_password(validated_payload):
    """
    Endpoint to request reset password link by email
    User must not be logged in

    Requires JSON body with following keys:
    - email

    Requires X-CSRF-Token in header, obtained from cookie set by /get-csrf
    """
    if current_user.is_authenticated:
        return jsonify(message="Already logged in - use /change-password"), 400

    email = validated_payload.email.data

    user = User.query.filter_by(email=email).first()

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


@auth_bp.route("/reset-password", methods=["POST"])
@validate_payload(ResetPasswordValidator)
def reset_password(validated_payload):
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

    rpt_id = validated_payload.rpt_id.data
    rpt_token = validated_payload.rpt_token.data
    new_password = validated_payload.new_password.data

    rpt_to_check = ResetPasswordToken.query.get(rpt_id)
    if rpt_to_check and rpt_to_check.use_token(rpt_token):
        user = User.query.get(rpt_to_check.user_uid)
        user.change_password(new_password)
        db.session.delete(rpt_to_check)
        db.session.commit()
        return jsonify(message="Success: password reset"), 200
    else:
        return jsonify(message="Invalid link"), 404
