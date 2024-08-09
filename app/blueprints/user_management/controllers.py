from flask import current_app, jsonify, request
from flask_login import current_user
from flask_mail import Message
from passlib.pwd import genword
from sqlalchemy import case, distinct, func, or_
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import aliased

from app import db, mail
from app.blueprints.auth.models import ResetPasswordToken, User
from app.blueprints.forms.models import Form
# from app.blueprints.mapping.errors import MappingError
# from app.blueprints.mapping.utils import TargetMapping
from app.blueprints.roles.models import Role, SurveyAdmin
from app.blueprints.surveys.models import Survey
from app.utils.utils import (
    custom_permissions_required,
    logged_in_active_user_required,
    validate_payload,
    validate_query_params,
)

from . import user_management_bp
from .models import Invite, UserLanguage, UserLocation
from .utils import generate_invite_code, send_invite_email
from .validators import (
    AddUserValidator,
    CheckUserValidator,
    CompleteRegistrationValidator,
    EditUserValidator,
    GetUsersQueryParamValidator,
    RegisterValidator,
    UserLocationsParamValidator,
    UserLocationsPayloadValidator,
    WelcomeUserValidator,
)


@user_management_bp.route("/register", methods=["POST"])
@logged_in_active_user_required
@validate_payload(RegisterValidator)
def register(validated_payload):
    """
    Endpoint to register users
    Requires JSON body with following keys:
    - email
    - password
    Requires X-CSRF-Token in header, obtained from cookie set by /get-csrf
    """

    email = validated_payload.email.data
    password = validated_payload.password.data

    if current_user.email == "registration_user":
        user_with_email = User.query.filter_by(email=email).first()
        if not user_with_email:
            new_user = User(
                email=email,
                first_name="",
                last_name="",
                password=password,
                roles=[],
                is_super_admin=True,
            )
            db.session.add(new_user)
            db.session.commit()
            return jsonify(message="Success: registered"), 200
        else:
            return jsonify(message="User already exists with email"), 422
    else:
        return jsonify(message="Unauthorized"), 401


@user_management_bp.route("/welcome-user", methods=["POST"])
@logged_in_active_user_required
@validate_payload(WelcomeUserValidator)
def welcome_user(validated_payload):
    """
    Endpoint to send welcome email with password reset to new user

    Requires JSON body with following keys:
    - email

    Requires X-CSRF-Token in header, obtained from cookie set by /get-csrf
    """

    email = validated_payload.email.data

    if current_user.email == "registration_user":
        user = User.query.filter_by(email=email).first()

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


##############################################################################
# INVITE / REGISTRATION / USER MANAGEMENT
##############################################################################


@user_management_bp.route("/users/check-email-availability", methods=["POST"])
@logged_in_active_user_required
@validate_payload(CheckUserValidator)
def check_user(validated_payload):
    """
    Endpoint to check a user by email, The endpoint will check if a user exists and then return the user details
    Requires JSON body with the following keys:
    - email
    Requires X-CSRF-Token in the header, obtained from the cookie set by /get-csrf
    """

    user_with_email = User.query.filter_by(email=validated_payload.email.data).first()
    if not user_with_email:
        return jsonify(message="User not found"), 404
    else:
        return (
            jsonify(message="User already exists", user=user_with_email.to_dict()),
            200,
        )


@user_management_bp.route("/users", methods=["POST"])
@logged_in_active_user_required
@validate_payload(AddUserValidator)
@custom_permissions_required("ADMIN", "body", "survey_uid")
def add_user(validated_payload):
    """
    Endpoint to invite a user by email, The endpoint will create a user without a password and send the user an email

    Requires JSON body with the following keys:
    - email
    - first_name
    - last_name
    - roles
    - gender
    - languages
    - locations
    - is_super_admin
    - can_create_survey

    This will not require a password
    Requires X-CSRF-Token in the header, obtained from the cookie set by /get-csrf
    """

    user_with_email = User.query.filter_by(email=validated_payload.email.data).first()
    if user_with_email:
        return jsonify(message="User already exists with email"), 422

    # Create the user without a password
    new_user = User(
        email=validated_payload.email.data,
        first_name=validated_payload.first_name.data,
        last_name=validated_payload.last_name.data,
        password=None,
        roles=validated_payload.roles.data,
        gender=validated_payload.gender.data,
        is_super_admin=validated_payload.is_super_admin.data,
        can_create_survey=validated_payload.can_create_survey.data,
    )

    db.session.add(new_user)
    db.session.flush()

    # Check if user is supposed to be a survey admin and add them to the list
    if validated_payload.is_survey_admin.data:
        survey_admin_entry = SurveyAdmin(
            survey_uid=validated_payload.survey_uid.data,
            user_uid=new_user.user_uid,
        )
        db.session.add(survey_admin_entry)

    # Check if locations data + survey_uid is provided, add them to the user location table
    if validated_payload.locations.data and validated_payload.survey_uid.data:
        for location_uid in validated_payload.locations.data:
            user_location = UserLocation(
                survey_uid=validated_payload.survey_uid.data,
                user_uid=new_user.user_uid,
                location_uid=location_uid,
            )
            db.session.add(user_location)
    db.session.commit()

    # Check if language data + survey_uid is provided, add them to the user location table
    if validated_payload.languages.data and validated_payload.survey_uid.data:
        for language in validated_payload.languages.data:
            user_language = UserLanguage(
                survey_uid=validated_payload.survey_uid.data,
                user_uid=new_user.user_uid,
                language=language,
            )
            db.session.add(user_language)

    # Update user to target and user to surveyor mappings for that survey if user is being added at survey level
    # New user added at global level doesn't affect any mappings because they are not yet part of a survey
    # if validated_payload.survey_uid.data:
    #     # Find user's role in the survey
    #     user_role = (
    #         db.session.query(Role.role_uid)
    #         .filter(
    #             Role.survey_uid == validated_payload.survey_uid.data,
    #             Role.role_uid == func.any(new_user.roles),
    #         )
    #         .first()
    #     )

    #     # Find all parent forms for the survey since mapping is a form level data
    #     forms = (
    #         db.session.query(Form.form_uid)
    #         .filter(
    #             Form.survey_uid == validated_payload.survey_uid.data,
    #             Form.form_type == "parent",
    #         )
    #         .all()
    #     )

    #     for form in forms:
    #         try:
    #             target_mapping = TargetMapping(form.form_uid)
    #         except MappingError as e:
    #             return (
    #                 jsonify(
    #                     {
    #                         "success": False,
    #                         "errors": {
    #                             "mapping_errors": e.mapping_errors,
    #                         },
    #                     }
    #                 ),
    #                 422,
    #             )
    #         # Mapping is only affected if the user is a bottom level supervisor in the survey
    #         if target_mapping.bottom_level_role_uid != user_role:
    #             continue

    #         mappings = target_mapping.generate_mappings()
    #         if mappings:
    #             target_mapping.save_mappings(mappings)

    invite_code = generate_invite_code()
    invite = Invite(
        invite_code=invite_code,
        email=validated_payload.email.data,
        user_uid=new_user.user_uid,
        is_active=True,
    )

    db.session.add(invite)
    db.session.commit()

    # send an invitation email to the user
    send_invite_email(validated_payload.email.data, invite_code)

    return (
        jsonify(
            message="Success: user invited",
            user=new_user.to_dict(),
            invite=invite.to_dict(),
        ),
        200,
    )


@user_management_bp.route("/users/complete-registration", methods=["POST"])
@validate_payload(CompleteRegistrationValidator)
def complete_registration(validated_payload):
    """
    Endpoint to complete user registration using an invite code.

    Requires JSON body with the following keys:
    - invite_code
    - new_password
    - confirm_password
    """

    try:
        invite_code = validated_payload.invite_code.data
        new_password = validated_payload.new_password.data

        # Find the invite with the provided invite code
        invite = Invite.query.filter_by(invite_code=invite_code, is_active=True).first()

        if not invite:
            return jsonify(message="Invalid or expired invite code"), 404

        # Update user password and set invite status to inactive
        user = User.query.get(invite.user_uid)
        # update user in case it was deactivated
        user.active = True
        user.change_password(new_password)

        # Update invite status to inactive
        invite.is_active = False
        db.session.commit()

        return jsonify(message="Success: registration completed"), 200
    except Exception as e:
        db.session.rollback()
        return jsonify(message="An error occurred while processing your request"), 500


@user_management_bp.route("/users/<int:user_uid>", methods=["PUT"])
@logged_in_active_user_required
@validate_payload(EditUserValidator)
def edit_user(user_uid, validated_payload):
    """
    Endpoint to edit a user's information.

    Requires JSON body with the following keys:
    - email
    - first_name
    - last_name
    - roles
    - gender
    - languages
    - locations
    - is_super_admin
    - is_survey_admin
    - active

    Requires X-CSRF-Token in the header, obtained from the cookie set by /get-csrf
    """
    user_to_edit = User.query.get(user_uid)
    if not user_to_edit:
        return jsonify(message="User not found"), 404

    # Update user information based on the form input
    user_to_edit.email = validated_payload.email.data
    user_to_edit.first_name = validated_payload.first_name.data
    user_to_edit.last_name = validated_payload.last_name.data
    user_to_edit.roles = validated_payload.roles.data
    user_to_edit.gender = validated_payload.gender.data
    user_to_edit.is_super_admin = validated_payload.is_super_admin.data
    user_to_edit.can_create_survey = validated_payload.can_create_survey.data
    user_to_edit.active = validated_payload.active.data

    # Check if roles are being removed as part of the edit since this affects mappings
    roles_removed = [
        role for role in user_to_edit.roles if role not in validated_payload.roles.data
    ]
    
    # Add or remove survey admin privileges based on is_survey_admin field
    if validated_payload.is_survey_admin.data:
        survey_uid = validated_payload.survey_uid.data
        # Only proceed if survey_uid is provided
        if survey_uid:
            user_to_edit.can_create_survey = True
            survey_admin_entry = SurveyAdmin.query.filter_by(
                user_uid=user_uid, survey_uid=survey_uid
            ).first()
            if not survey_admin_entry:
                survey_admin_entry = SurveyAdmin(
                    survey_uid=survey_uid, user_uid=user_uid
                )
                db.session.add(survey_admin_entry)
    else:
        survey_uid = validated_payload.survey_uid.data
        # Only proceed if survey_uid is provided
        if survey_uid:
            # Remove survey admin entry
            survey_admin_entry = SurveyAdmin.query.filter_by(
                user_uid=user_uid, survey_uid=survey_uid
            ).first()
            if survey_admin_entry:
                db.session.delete(survey_admin_entry)
                db.session.commit()  # Commit the deletion

    # Update user locations if locations data is provided
    if validated_payload.locations.data:
        survey_uid = validated_payload.survey_uid.data
        # Only proceed if survey_uid is provided
        if survey_uid:
            # Delete existing user locations
            UserLocation.query.filter_by(
                user_uid=user_uid, survey_uid=survey_uid
            ).delete()
            # Add new user locations
            for location_uid in validated_payload.locations.data:
                user_location = UserLocation(
                    survey_uid=survey_uid,
                    user_uid=user_uid,
                    location_uid=location_uid,
                )
                db.session.add(user_location)

    # Update user languages if languages data is provided
    if validated_payload.languages.data:
        survey_uid = validated_payload.survey_uid.data
        # Only proceed if survey_uid is provided
        if survey_uid:
            # Delete existing user languages
            UserLanguage.query.filter_by(
                user_uid=user_uid, survey_uid=survey_uid
            ).delete()
            # Add new user languages
            for language in validated_payload.languages.data:
                user_language = UserLanguage(
                    survey_uid=survey_uid,
                    user_uid=user_uid,
                    language=language,
                )
                db.session.add(user_language)

    # If user is editted,
    # 1. Update user to target and user to surveyor mappings for all surveys the user is currently a part of

    # # Find all surveys this user is part of along with roles
    # survey_roles = (
    #     db.session.query(distinct(Survey.survey_uid, Role.role_uid))
    #     .join(Role, Role.role_uid == func.any(User.roles))
    #     .join(Survey, Survey.survey_uid == Role.survey_uid)
    #     .filter(
    #         User.user_uid == user_uid,
    #     )
    #     .all()
    # )

    # for survey_uid, role_uid in survey_roles:
    #     # Find all parent forms for the survey since mapping is a form level data
    #     forms = (
    #         db.session.query(Form.form_uid)
    #         .filter(Form.survey_uid == survey_uid, Form.form_type == "parent")
    #         .all()
    #     )

    #     for form in forms:
    #         try:
    #             target_mapping = TargetMapping(form.form_uid)
    #         except MappingError as e:
    #             return (
    #                 jsonify(
    #                     {
    #                         "success": False,
    #                         "errors": {
    #                             "mapping_errors": e.mapping_errors,
    #                         },
    #                     }
    #                 ),
    #                 422,
    #             )

    #         # Mapping is only affected if the user is a bottom level supervisor in the survey
    #         if target_mapping.bottom_level_role_uid != role_uid:
    #             continue

    #         mappings = target_mapping.generate_mappings()
    #         if mappings:
    #             target_mapping.save_mappings(mappings)

    # # If roles are removed from the user, mappings need to be updated for surveys with the removed role as well
    # for role_uid in roles_removed:
    #     # Find the survey correspoding to this role
    #     survey_uid = Role.query.filter_by(role_uid=role_uid).first().survey_uid

    #     # Find all parent forms for the survey since mapping is a form level data
    #     forms = (
    #         db.session.query(Form.form_uid)
    #         .filter(Form.survey_uid == survey_uid, Form.form_type == "parent")
    #         .all()
    #     )

    #     for form in forms:
    #         try:
    #             target_mapping = TargetMapping(form.form_uid)
    #         except MappingError as e:
    #             return (
    #                 jsonify(
    #                     {
    #                         "success": False,
    #                         "errors": {
    #                             "mapping_errors": e.mapping_errors,
    #                         },
    #                     }
    #                 ),
    #                 422,
    #             )

    #         # Mapping is only affected if the user was a bottom level supervisor in the survey
    #         if target_mapping.bottom_level_role_uid != role_uid:
    #             continue

    #         mappings = target_mapping.generate_mappings()
    #         if mappings:
    #             target_mapping.save_mappings(mappings)

    db.session.commit()
    user_data = user_to_edit.to_dict()
    return jsonify(message="User updated", user_data=user_data), 200


@user_management_bp.route("/users/<int:user_uid>", methods=["GET"])
@logged_in_active_user_required
def get_user(user_uid):
    """
    Endpoint to get information for a single user.
    """
    user = User.query.filter(User.user_uid == user_uid).first()

    if user:
        user_data = {
            "user_uid": user.user_uid,
            "email": user.email,
            "first_name": user.first_name,
            "last_name": user.last_name,
            "roles": user.roles,
            "gender": user.gender,
            "is_super_admin": user.is_super_admin,
            "can_create_survey": user.can_create_survey,
            "active": user.active,
        }
        return jsonify(user_data), 200
    else:
        return jsonify(message="User not found"), 404


@user_management_bp.route("/users", methods=["GET"])
@logged_in_active_user_required
@validate_query_params(GetUsersQueryParamValidator)
@custom_permissions_required("ADMIN", "query", "survey_uid")
def get_all_users(validated_query_params):
    """
    Endpoint to get information for all users.
    """

    # TO DO:
    # 1. Fetch supervisor hierarchy and location information when survey uid is provided
    # 2. Fix the query to get survey wise user role information. Currently it is returning
    # all roles for the user and all surveys for the user in separate arrays and combining them
    # on frontend. This should be done in the query itself.

    survey_uid = validated_query_params.survey_uid.data

    if survey_uid is None and not current_user.is_super_admin:
        return jsonify(message="Survey UID is required for non-super-admin users"), 400

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

    survey_admin_subquery = (
        db.session.query(
            SurveyAdmin,
            SurveyAdmin.user_uid,
            SurveyAdmin.survey_uid,
            Survey.survey_name,
        )
        .join(Survey, SurveyAdmin.survey_uid == Survey.survey_uid)
        .distinct()
        .subquery()
    )

    user_query = (
        db.session.query(
            User,
            invite_subquery.c.is_active.label("invite_is_active"),
            func.array_agg(roles_subquery.c.role_name.distinct()).label(
                "user_role_names"
            ),
            func.array_agg(Survey.survey_name.distinct()).label("user_survey_names"),
            func.array_agg(survey_admin_subquery.c.survey_uid.distinct()).label(
                "user_admin_surveys"
            ),
            func.array_agg(survey_admin_subquery.c.survey_name.distinct()).label(
                "user_admin_survey_names"
            ),
        )
        .outerjoin(invite_subquery, User.user_uid == invite_subquery.c.user_uid)
        .outerjoin(
            survey_admin_subquery, survey_admin_subquery.c.user_uid == User.user_uid
        )
        .outerjoin(roles_subquery, roles_subquery.c.role_uid == func.any(User.roles))
        .outerjoin(Survey, Survey.survey_uid == roles_subquery.c.survey_uid)
        .group_by(
            User.user_uid,
            invite_subquery.c.is_active,
        )
    )

    # Apply conditions based on current_user.is_super_admin
    if current_user.is_super_admin and survey_uid is None:
        users = user_query.all()
    else:
        users = user_query.filter(
            or_(
                roles_subquery.c.survey_uid == survey_uid,
                survey_admin_subquery.c.survey_uid == survey_uid,
            )
        ).all()

    user_list = []

    for (
        user,
        invite_is_active,
        user_role_names,
        user_survey_names,
        user_admin_surveys,
        user_admin_survey_names,
    ) in users:
        user_data = {
            "user_uid": user.user_uid,
            "email": user.email,
            "first_name": user.first_name,
            "last_name": user.last_name,
            "roles": user.roles,
            "gender": user.gender,
            "user_survey_names": user_survey_names,
            "user_role_names": user_role_names,
            "user_admin_surveys": [
                survey_uid
                for survey_uid in user_admin_surveys
                if survey_uid is not None
            ],
            "user_admin_survey_names": [
                survey_name
                for survey_name in user_admin_survey_names
                if survey_name is not None
            ],
            "is_super_admin": user.is_super_admin,
            "can_create_survey": user.can_create_survey,
            "status": (
                "Active"
                if user.active
                else ("Invite pending" if invite_is_active else "Deactivated")
            ),
        }

        user_list.append(user_data)

    return jsonify(user_list), 200


@user_management_bp.route("/users/<int:user_uid>", methods=["DELETE"])
@logged_in_active_user_required
@custom_permissions_required("ADMIN")
def deactivate_user(user_uid):
    """
    Endpoint to deactivate a user.
    """
    user = User.query.get(user_uid)
    if user:
        try:
            # Set user as deactivated
            user.active = False
            db.session.commit()
            return jsonify(message="User deactivated successfully"), 200
        except Exception as e:
            db.session.rollback()
            return jsonify(message=f"Error deactivating user: {str(e)}"), 500
    else:
        return jsonify(message="User not found"), 404


# User Locations
@user_management_bp.route("/user-locations", methods=["GET"])
@logged_in_active_user_required
@validate_query_params(UserLocationsParamValidator)
def get_user_locations(validated_query_params):
    """Function to get user locations"""

    survey_uid = validated_query_params.survey_uid.data
    user_uid = request.args.get("user_uid")

    user_locations = UserLocation.query.filter_by(
        survey_uid=survey_uid, user_uid=user_uid
    ).all()

    if user_locations:
        return (
            jsonify(
                {
                    "success": True,
                    "data": [
                        user_location.to_dict() for user_location in user_locations
                    ],
                }
            ),
            200,
        )
    else:
        return jsonify(message="User locations not found"), 404


@user_management_bp.route("/user-locations", methods=["PUT"])
@logged_in_active_user_required
@validate_payload(UserLocationsPayloadValidator)
@custom_permissions_required("ADMIN", "body", "survey_uid")
def update_user_locations(validated_payload):
    """Function to update user locations"""

    survey_uid = validated_payload.survey_uid.data
    user_uid = validated_payload.user_uid.data
    locations = validated_payload.locations.data

    UserLocation.query.filter_by(survey_uid=survey_uid, user_uid=user_uid).delete()

    for location_uid in locations:
        user_location = UserLocation(
            survey_uid=survey_uid,
            user_uid=user_uid,
            location_uid=location_uid,
        )
        db.session.add(user_location)

    # Update user to target and user to surveyor mappings for that survey
    # if user is a bottom level supervisor in the survey and location is a mapping criteria
    # Find user's role in the survey
    # user_role = (
    #     db.session.query(Role.role_uid)
    #     .join(User, Role.role_uid == func.any(User.roles))
    #     .filter(
    #         Role.survey_uid == survey_uid,
    #     )
    #     .first()
    # )

    # # Find all parent forms for the survey since mapping is a form level data
    # forms = (
    #     db.session.query(Form.form_uid)
    #     .filter(
    #         Form.survey_uid == validated_payload.survey_uid.data,
    #         Form.form_type == "parent",
    #     )
    #     .all()
    # )

    # for form in forms:
    #     try:
    #         target_mapping = TargetMapping(form.form_uid)
    #     except MappingError as e:
    #         return (
    #             jsonify(
    #                 {
    #                     "success": False,
    #                     "errors": {
    #                         "mapping_errors": e.mapping_errors,
    #                     },
    #                 }
    #             ),
    #             422,
    #         )
    #     # Mapping is only affected if the user is a bottom level supervisor in the survey
    #     if target_mapping.bottom_level_role_uid != user_role:
    #         continue

    #     # Mapping is only affected if the location is a mapping criteria
    #     if "Location" not in target_mapping.mapping_criteria:
    #         continue

    #     mappings = target_mapping.generate_mappings()
    #     if mappings:
    #         target_mapping.save_mappings(mappings)

    try:
        db.session.commit()
    except IntegrityError as e:
        db.session.rollback()
        return jsonify(message=str(e)), 500

    return jsonify({"success": True}), 200


@user_management_bp.route("/user-locations", methods=["DELETE"])
@logged_in_active_user_required
@validate_query_params(UserLocationsParamValidator)
@custom_permissions_required("ADMIN", "query", "survey_uid")
def delete_user_locations(validated_query_params):
    """Function to delete user locations"""

    survey_uid = validated_query_params.survey_uid.data
    user_uid = validated_query_params.user_uid.data

    if (
        UserLocation.query.filter_by(survey_uid=survey_uid, user_uid=user_uid).first()
        is None
    ):
        return jsonify({"error": "User locations not found"}), 404

    UserLocation.query.filter_by(survey_uid=survey_uid, user_uid=user_uid).delete()

    # Update user to target and user to surveyor mappings for that survey
    # if user is a bottom level supervisor in the survey and location is a mapping criteria
    # Find user's role in the survey
    # user_role = (
    #     db.session.query(Role.role_uid)
    #     .join(User, Role.role_uid == func.any(User.roles))
    #     .filter(
    #         Role.survey_uid == survey_uid,
    #     )
    #     .first()
    # )

    # # Find all parent forms for the survey since mapping is a form level data
    # forms = (
    #     db.session.query(Form.form_uid)
    #     .filter(Form.survey_uid == survey_uid, Form.form_type == "parent")
    #     .all()
    # )

    # for form in forms:
    #     try:
    #         target_mapping = TargetMapping(form.form_uid)
    #     except MappingError as e:
    #         return (
    #             jsonify(
    #                 {
    #                     "success": False,
    #                     "errors": {
    #                         "mapping_errors": e.mapping_errors,
    #                     },
    #                 }
    #             ),
    #             422,
    #         )
    #     # Mapping is only affected if the user is a bottom level supervisor in the survey
    #     if target_mapping.bottom_level_role_uid != user_role:
    #         continue

    #     # Mapping is only affected if the location is a mapping criteria
    #     if "Location" not in target_mapping.mapping_criteria:
    #         continue

    #     mappings = target_mapping.generate_mappings()
    #     if mappings:
    #         target_mapping.save_mappings(mappings)

    try:
        db.session.commit()
        return jsonify(message="User locations deleted successfully"), 200
    except Exception as e:
        db.session.rollback()
        return jsonify(message=str(e)), 500
