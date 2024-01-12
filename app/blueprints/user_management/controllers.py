from . import user_management_bp
from flask import jsonify, request, current_app
from flask_login import current_user
from flask_mail import Message
from passlib.pwd import genword
from sqlalchemy.orm import aliased, subqueryload
from sqlalchemy import or_, func, exists, and_

from app import db, mail
from app.blueprints.auth.models import ResetPasswordToken, User
from app.blueprints.roles.models import Role
from .models import Invite
from .utils import generate_invite_code, send_invite_email
from .validators import (
    AddUserValidator,
    CompleteRegistrationValidator,
    RegisterValidator,
    WelcomeUserValidator,
    EditUserValidator,
    CheckUserValidator
)
from app.utils.utils import logged_in_active_user_required
from ..surveys.models import Survey


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
            user_with_email = User.query.filter_by(
                email=form.email.data).first()
            if not user_with_email:
                new_user = User(
                    email=form.email.data,
                    first_name="",
                    last_name="",
                    password=form.password.data,
                    roles=[],
                    is_super_admin=True
                )
                db.session.add(new_user)
                db.session.commit()
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
                ResetPasswordToken.query.filter_by(
                    user_uid=user.user_uid).delete()
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


@user_management_bp.route("/users/check-email-availability", methods=["POST"])
@logged_in_active_user_required
def check_user():
    """
    Endpoint to check a user by email, The endpoint will check if a user exists and then return the user details
    Requires JSON body with the following keys:
    - email
    Requires X-CSRF-Token in the header, obtained from the cookie set by /get-csrf
    """
    form = CheckUserValidator.from_json(request.get_json())
    if "X-CSRF-Token" in request.headers:
        form.csrf_token.data = request.headers.get("X-CSRF-Token")
    else:
        return jsonify(message="X-CSRF-Token required in header"), 403

    if form.validate():
        user_with_email = User.query.filter_by(email=form.email.data).first()
        if not user_with_email:
            return jsonify(message="User not found"), 404
        else:
            return jsonify(message="User already exists", user=user_with_email.to_dict()), 200
    else:
        return jsonify(message=form.errors), 422


@user_management_bp.route("/users", methods=["POST"])
@logged_in_active_user_required
def add_user():
    """
    Endpoint to invite a user by email, The endpoint will create a user without a password and send the user an email

    Requires JSON body with the following keys:
    - email
    - first_name
    - last_name
    - role
    - is_super_admin

    This will not require a password
    Requires X-CSRF-Token in the header, obtained from the cookie set by /get-csrf
    """
    form = AddUserValidator.from_json(request.get_json())
    if "X-CSRF-Token" in request.headers:
        form.csrf_token.data = request.headers.get("X-CSRF-Token")
    else:
        return jsonify(message="X-CSRF-Token required in header"), 403

    if form.validate():
        user_with_email = User.query.filter_by(email=form.email.data).first()
        if not user_with_email:
            # Create the user without a password
            new_user = User(
                email=form.email.data,
                first_name=form.first_name.data,
                last_name=form.last_name.data,
                password=None,
                roles=form.roles.data,
                is_super_admin=form.is_super_admin.data  # No password for invited users
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
            send_invite_email(form.email.data, invite_code)

            return jsonify(message="Success: user invited", user=new_user.to_dict(), invite=invite.to_dict()), 200
        else:
            return jsonify(message="User already exists with email"), 422
    else:
        return jsonify(message=form.errors), 422


@user_management_bp.route("/users/complete-registration", methods=["POST"])
def complete_registration():
    """
    Endpoint to complete user registration using an invite code.

    Requires JSON body with the following keys:
    - invite_code
    - new_password
    - confirm_password
    """
    form = CompleteRegistrationValidator.from_json(request.get_json())

    # Add the CSRF token to be checked by the validator
    if "X-CSRF-Token" in request.headers:
        form.csrf_token.data = request.headers.get("X-CSRF-Token")
    else:
        return jsonify(message="X-CSRF-Token required in header"), 403

    if form.validate():
        invite_code = form.invite_code.data
        new_password = form.new_password.data

        # Find the invite with the provided invite code
        invite = Invite.query.filter_by(
            invite_code=invite_code, is_active=True).first()

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


@user_management_bp.route("/users/<int:user_id>", methods=["PUT"])
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

    Requires X-CSRF-Token in the header, obtained from the cookie set by /get-csrf
    """
    form = EditUserValidator.from_json(request.get_json())
    if "X-CSRF-Token" in request.headers:
        form.csrf_token.data = request.headers.get("X-CSRF-Token")
    else:
        return jsonify(message="X-CSRF-Token required in header"), 403

    if form.validate():
        user_to_edit = User.query.get(user_id)

        if user_to_edit:
            # Update user information based on the form input
            user_to_edit.email = form.email.data
            user_to_edit.first_name = form.first_name.data
            user_to_edit.last_name = form.last_name.data
            user_to_edit.roles = form.roles.data
            user_to_edit.is_super_admin = form.is_super_admin.data

            db.session.commit()
            user_data = user_to_edit.to_dict()
            return jsonify(message="User updated", user_data=user_data), 200
        else:
            return jsonify(message="User not found"), 404
    else:
        return jsonify(message=form.errors), 422


@user_management_bp.route("/users/<int:user_id>", methods=["GET"])
@logged_in_active_user_required
def get_user(user_id):
    """
    Endpoint to get information for a single user.
    """
    user = User.query.filter(
        (User.user_uid == user_id) & ((User.to_delete == False) | (User.to_delete.is_(None)))
    ).first()

    if user:
        user_data = {
            "user_id": user.user_uid,
            "email": user.email,
            "first_name": user.first_name,
            "last_name": user.last_name,
            "roles": user.roles,
            "is_super_admin": user.is_super_admin
        }
        return jsonify(user_data), 200
    else:
        return jsonify(message="User not found"), 404


@user_management_bp.route("/users", methods=["GET"])
@logged_in_active_user_required
def get_all_users():
    """
    Endpoint to get information for all users.
    """

    survey_id = request.args.get('survey_id')
    if  survey_id is None and not current_user.is_super_admin:
        return jsonify(message="Survey ID is required for non-super-admin users"), 400

    invite_subquery = (
        db.session.query(Invite)
        .filter(Invite.user_uid == User.user_uid)
        .order_by(Invite.invite_uid.desc())
        .limit(1)
        .subquery()
    )

    roles_subquery = (
        db.session.query(
            Role.role_name,
            Role.role_uid,
            Role.survey_uid,
        )
        .distinct()
        .subquery()
    )


    user_query = (
        db.session.query(
            User,
            invite_subquery.c.is_active.label("invite_is_active"),
            func.array_agg(roles_subquery.c.role_name.distinct()).label("user_role_names"),
            func.array_agg(Survey.survey_name.distinct()).label("user_survey_names")
        )
        .filter(or_(User.to_delete == False, User.to_delete.is_(None)))
        .outerjoin(invite_subquery, User.user_uid == invite_subquery.c.user_uid)
        .outerjoin(
            roles_subquery,
            roles_subquery.c.role_uid == func.any(User.roles)
        )
        .outerjoin(Survey, Survey.survey_uid == roles_subquery.c.survey_uid)
        .group_by(
            User.user_uid,
            invite_subquery.c.is_active,
        )
    )

    # Apply conditions based on current_user.is_super_admin
    if current_user.is_super_admin and survey_id is None:
        users = user_query.all()
    else:
        users = user_query.filter(roles_subquery.c.survey_uid == survey_id).all()

    user_list = []

    for user, invite_is_active,user_role_names,user_survey_names  in users:
        user_data = {
            "user_id": user.user_uid,
            "email": user.email,
            "first_name": user.first_name,
            "last_name": user.last_name,
            "roles": user.roles,
            "user_survey_names": user_survey_names,
            "user_role_names": user_role_names,
            "is_super_admin": user.is_super_admin,
            "status": "Active" if user.active else ("Invite pending" if invite_is_active else "Deactivated"),
        }

        user_list.append(user_data)

    return jsonify(user_list), 200


@user_management_bp.route("/users/<int:user_id>", methods=["DELETE"])
@logged_in_active_user_required
def delete_user(user_id):
    """
    Endpoint to delete a user.
    """
    user = User.query.get(user_id)
    """
        Endpoint to delete a user.
        """
    user = User.query.get(user_id)
    if user:
        try:
            # Set user as deleted and update active field
            user.to_delete = True
            user.active = False
            db.session.commit()
            return jsonify(message="User deleted successfully"), 200
        except Exception as e:
            db.session.rollback()
            return jsonify(message=f"Error deleting user: {str(e)}"), 500
    else:
        return jsonify(message="User not found"), 404