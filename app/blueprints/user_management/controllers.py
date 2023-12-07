from app.blueprints.user_management.models import Invite
from app.blueprints.user_management.utils import generate_invite_code, send_invite_email
from . import user_management_bp
from app.utils.utils import logged_in_active_user_required
from flask import jsonify, request, current_app
from flask_login import current_user
from flask_mail import Message
from passlib.pwd import genword
from app import db, mail
from app.blueprints.auth.models import ResetPasswordToken, User
from .validators import (
    AddUserValidator,
    CompleteRegistrationValidator,
    RegisterValidator,
    WelcomeUserValidator
)
@user_management_bp.route("/register", methods=["POST"])
@logged_in_active_user_required
def register():
    """
    Endpoint to register users
    Requires JSON body with following keys:
    - email
    - password
    Requires X-CSRF-Token in header, obtained from cookie set by /get-csrf
    """

    form = RegisterValidator.from_json(request.get_json())
    if "X-CSRF-Token" in request.headers:
        form.csrf_token.data = request.headers.get("X-CSRF-Token")
    else:
        return jsonify(message="X-CSRF-Token required in header"), 403

    if form.validate():
        if current_user.email == "registration_user":
            user_with_email = User.query.filter_by(email=form.email.data).first()
            if not user_with_email:
                User(form.email.data, form.password.data)
                return jsonify(message="Success: registered"), 200
            else:
                return jsonify(message="User already exists with email"), 422
        else:
            return jsonify(message="Unauthorized"), 401
    else:
        return jsonify(message=form.errors), 422


@user_management_bp.route("/welcome-user", methods=["POST"])
@logged_in_active_user_required
def welcome_user():
    """
    Endpoint to send welcome email with password reset to new user

    Requires JSON body with following keys:
    - email

    Requires X-CSRF-Token in header, obtained from cookie set by /get-csrf
    """

    form = WelcomeUserValidator.from_json(request.get_json())
    if "X-CSRF-Token" in request.headers:
        form.csrf_token.data = request.headers.get("X-CSRF-Token")
    else:
        return jsonify(message="X-CSRF-Token required in header"), 403

    if form.validate():
        if current_user.email == "registration_user":
            user = User.query.filter_by(email=form.email.data).first()

            if user:
                email_token = genword(length=32, charset="ascii_62")
                rpt = ResetPasswordToken(user.user_uid, email_token)

                # Add this rpt, delete all other rpts for this user
                ResetPasswordToken.query.filter_by(user_uid=user.user_uid).delete()
                db.session.add(rpt)
                db.session.commit()

                rp_message = Message(
                    subject="Welcome to SurveyStream - Password Reset Required",
                    html="Welcome to SurveyStream! Your login email is %s. Please reset your password by clicking <a href='%s/reset-password/%s/%s'>here</a>.<br><br>The link will expire in 24 hours."
                    % (
                        user.email,
                        current_app.config["REACT_BASE_URL"],
                        rpt.reset_uid,
                        email_token,
                    ),
                    recipients=[user.email],
                )
                mail.send(rp_message)
                return jsonify(message="Request processed"), 200
            else:
                return jsonify(message="Record not found"), 404

        else:
            return jsonify(message="Unauthorized"), 401

    else:
        return jsonify(message=form.errors), 422

##############################################################################
# INVITE / REGISTRATION / USER MANAGEMENT
##############################################################################

@user_management_bp.route("/add-user", methods=["POST"])
@logged_in_active_user_required
def add_user():
    """
    Endpoint to invite a user by email, The endpoint will create a user without a password and send the user an email

    Requires JSON body with the following keys:
    - email
    - first_name
    - last_name
    - role

    This will not require a password
    Requires X-CSRF-Token in the header, obtained from the cookie set by /get-csrf
    """
    form = AddUserValidator.from_json(request.get_json())
    if "X-CSRF-Token" in request.headers:
        form.csrf_token.data = request.headers.get("X-CSRF-Token")
    else:
        return jsonify(message="X-CSRF-Token required in header"), 403

    if form.validate():
        if current_user.email == "registration_user":
            user_with_email = User.query.filter_by(email=form.email.data).first()
            if not user_with_email:
                # Create the user without a password
                new_user = User(
                    email=form.email.data,
                    first_name=form.first_name.data,
                    last_name=form.last_name.data,
                    password=None,  # No password for invited users
                )

                # Add logic to assign roles based on the form input
                db.session.add(new_user)
                db.session.commit()
                
                invite_code = generate_invite_code()

                # Create an invite record
                invite = Invite(
                    invite_code=invite_code,
                    email=form.email.data,
                    user_uid=new_user.user_uid,
                    is_active=True,
                )

                # Commit changes to the database
                db.session.add(invite)
                db.session.commit()

                # send an invitation email to the user
                send_invite_email(form.email.data,invite_code)
               
                return jsonify(message="Success: user invited"), 200
            else:
                return jsonify(message="User already exists with email"), 422
        else:
            return jsonify(message="Unauthorized"), 401
    else:
        return jsonify(message=form.errors), 422


@user_management_bp.route("/complete-registration", methods=["POST"])
@logged_in_active_user_required
def complete_registration():
    """
    Endpoint to complete user registration using an invite code.

    Requires JSON body with the following keys:
    - invite_code
    - new_password
    - confirm_password
    """
    form = CompleteRegistrationValidator(request.form)

    if form.validate():
        invite_code = form.invite_code.data
        new_password = form.new_password.data

        # Find the invite with the provided invite code
        invite = Invite.query.filter_by(invite_code=invite_code, is_active=True).first()

        if not invite:
            return jsonify(message="Invalid or expired invite code"), 404

        # Update user password and set invite status to inactive
        user = User.query.get(invite.user_uid)
        user.change_password(new_password)

        # Update invite status to inactive
        invite.is_active = False
        db.session.commit()

        return jsonify(message="Success: registration completed"), 200
    else:
        return jsonify(message=form.errors), 422


@user_management_bp.route("/edit-user/<int:user_id>", methods=["PUT"])
@logged_in_active_user_required
def edit_user(user_id):
    """
    Endpoint to edit a user's information.

    Requires JSON body with the following keys:
    - email
    - first_name
    - last_name
    - roles
    - is_super_admin
    - permissions

    Requires X-CSRF-Token in the header, obtained from the cookie set by /get-csrf
    """
    form = EditUserValidator.from_json(request.get_json())
    if "X-CSRF-Token" in request.headers:
        form.csrf_token.data = request.headers.get("X-CSRF-Token")
    else:
        return jsonify(message="X-CSRF-Token required in header"), 403

    if form.validate():
        if current_user.email == "registration_user":
            user_to_edit = User.query.get(user_id)

            if user_to_edit:
                # Update user information based on the form input
                user_to_edit.email = form.email.data
                user_to_edit.first_name = form.first_name.data
                user_to_edit.last_name = form.last_name.data
                user_to_edit.roles = form.roles.data
                user_to_edit.is_super_admin = form.is_super_admin.data
                user_to_edit.permissions = form.permissions.data

                db.session.commit()

                # Return updated user information with roles and permissions
                user_data = {
                    "user_id": user_to_edit.user_uid,
                    "email": user_to_edit.email,
                    "first_name": user_to_edit.first_name,
                    "last_name": user_to_edit.last_name,
                    "roles": user_to_edit.roles,
                    "is_super_admin": user_to_edit.is_super_admin,
                    "permissions": user_to_edit.permissions,
                }
                return jsonify(user_data), 200
            else:
                return jsonify(message="User not found"), 404
        else:
            return jsonify(message="Unauthorized"), 401
    else:
        return jsonify(message=form.errors), 422


@user_management_bp.route("/get-user/<int:user_id>", methods=["GET"])
@logged_in_active_user_required
def get_user(user_id):
    """
    Endpoint to get information for a single user.
    """
    if current_user.email == "registration_user":
        user = User.query.get(user_id)
        if user:
            user_data = {
                "user_id": user.user_uid,
                "email": user.email,
                "first_name": user.first_name,
                "last_name": user.last_name,
                "role": user.role,
            }
            return jsonify(user_data), 200
        else:
            return jsonify(message="User not found"), 404
    else:
        return jsonify(message="Unauthorized"), 401


@user_management_bp.route("/get-all-users", methods=["GET"])
@logged_in_active_user_required
def get_all_users():
    """
    Endpoint to get information for all users.
    """
    if current_user.email == "registration_user":
        # Check if the user is a super admin
        if current_user.is_super_admin:
            users = User.query.all()
        else:
            # Get the survey_id from the query parameters
            survey_id = request.args.get("survey_id")

            # Add the necessary logic to fetch users based on survey_id
            if survey_id:
                # Example: Fetch users based on survey_id (modify this based on your actual logic)
                users = User.query.filter_by(survey_id=survey_id).all()
            else:
                return jsonify(message="Survey ID is required for non-super-admin users"), 400

        user_list = []

        for user in users:
            user_data = {
                "user_id": user.user_uid,
                "email": user.email,
                "first_name": user.first_name,
                "last_name": user.last_name,
                "role": user.role,
            }
            user_list.append(user_data)

        return jsonify(user_list), 200
    else:
        return jsonify(message="Unauthorized"), 401
