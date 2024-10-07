from flask import current_app, jsonify, request
from flask_login import current_user
from flask_mail import Message
from passlib.pwd import genword
from sqlalchemy import case, distinct, func, or_, null, case
from sqlalchemy.exc import IntegrityError

from app import db, mail
from app.blueprints.auth.models import ResetPasswordToken, User
from app.blueprints.forms.models import Form

from app.blueprints.roles.models import Role, SurveyAdmin, UserHierarchy
from app.blueprints.locations.models import Location
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
    GetUserLocationsParamValidator,
    GetUserLanguagesParamValidator,
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

    # If survey_uid is provided, also fetch user locations and languages to return along with user details
    if validated_payload.survey_uid.data:
        survey_admin_subquery = (
            db.session.query(
                SurveyAdmin.survey_uid,
                SurveyAdmin.user_uid,
            )
            .filter(SurveyAdmin.survey_uid == validated_payload.survey_uid.data)
            .distinct()
            .subquery()
        )

        locations_subquery = (
            db.session.query(
                UserLocation.user_uid,
                func.array_agg(UserLocation.location_uid).label("location_uids"),
                func.array_agg(Location.location_id).label("location_ids"),
                func.array_agg(Location.location_name).label("location_names"),
            )
            .join(
                Location,
                (Location.location_uid == UserLocation.location_uid)
                & (Location.survey_uid == validated_payload.survey_uid.data),
            )
            .filter(UserLocation.survey_uid == validated_payload.survey_uid.data)
            .group_by(UserLocation.user_uid)
            .distinct()
            .subquery()
        )

        languages_subquery = (
            db.session.query(
                UserLanguage.user_uid,
                func.array_agg(UserLanguage.language).label("languages"),
            )
            .filter(UserLanguage.survey_uid == validated_payload.survey_uid.data)
            .group_by(UserLanguage.user_uid)
            .distinct()
            .subquery()
        )

        user_with_email = (
            db.session.query(
                User,
                case(
                    [
                        (
                            survey_admin_subquery.c.user_uid.isnot(None),
                            True,
                        )
                    ],
                    else_=False,
                ).label("is_survey_admin"),
                locations_subquery.c.location_uids,
                locations_subquery.c.location_ids,
                locations_subquery.c.location_names,
                languages_subquery.c.languages,
            )
            .outerjoin(
                locations_subquery, (User.user_uid == locations_subquery.c.user_uid)
            )
            .outerjoin(
                languages_subquery, (User.user_uid == languages_subquery.c.user_uid)
            )
            .outerjoin(
                survey_admin_subquery,
                (User.user_uid == survey_admin_subquery.c.user_uid),
            )
            .filter(
                User.email == validated_payload.email.data,
            )
            .first()
        )
    else:
        user_with_email = (
            db.session.query(
                User,
                False,  # is_survey_admin
                null().label("location_uids"),
                null().label("location_ids"),
                null().label("location_names"),
                null().label("languages"),
            )
            .filter_by(email=validated_payload.email.data)
            .first()
        )

    if not user_with_email:
        return jsonify(message="User not found"), 404
    else:
        return (
            jsonify(
                message="User already exists",
                user={
                    **user_with_email[0].to_dict(),
                    **{
                        "is_survey_admin": user_with_email[1],
                        "location_uids": [
                            location_uid
                            for location_uid in user_with_email[2]
                            if location_uid
                        ]
                        if user_with_email[4]
                        else [],
                        "location_ids": [
                            location_id
                            for location_id in user_with_email[3]
                            if location_id
                        ]
                        if user_with_email[4]
                        else [],
                        "location_names": [
                            location_names
                            for location_names in user_with_email[4]
                            if location_names
                        ]
                        if user_with_email[4]
                        else [],
                        "languages": [
                            language for language in user_with_email[5] if language
                        ]
                        if user_with_email[5]
                        else [],
                    },
                },
            ),
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
    - location_uids
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
    if validated_payload.location_uids.data and validated_payload.survey_uid.data:
        for location_uid in validated_payload.location_uids.data:
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
    - location_uids
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

    survey_uid = validated_payload.survey_uid.data
    # Only proceed with survey level details updation if survey_uid is provided
    if survey_uid:
        # Add or remove survey admin privileges based on is_survey_admin field
        if validated_payload.is_survey_admin.data:
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
            # Remove survey admin entry
            survey_admin_entry = SurveyAdmin.query.filter_by(
                user_uid=user_uid, survey_uid=survey_uid
            ).first()
            if survey_admin_entry:
                db.session.delete(survey_admin_entry)
                db.session.commit()  # Commit the deletion

        # Update user locations if location_uids data is provided
        if validated_payload.location_uids.data:
            # Delete existing user locations
            UserLocation.query.filter_by(
                user_uid=user_uid, survey_uid=survey_uid
            ).delete()
            # Add new user locations
            for location_uid in validated_payload.location_uids.data:
                user_location = UserLocation(
                    survey_uid=survey_uid,
                    user_uid=user_uid,
                    location_uid=location_uid,
                )
                db.session.add(user_location)
        else:
            # Delete existing user locations
            UserLocation.query.filter_by(
                user_uid=user_uid, survey_uid=survey_uid
            ).delete()

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
        else:
            # Delete existing user languages
            UserLanguage.query.filter_by(
                user_uid=user_uid, survey_uid=survey_uid
            ).delete()

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
            Role.survey_uid,
            Role.role_uid,
            Role.role_name,
            Survey.survey_name,
        )
        .join(Survey, Role.survey_uid == Survey.survey_uid)
        .distinct()
        .subquery()
    )

    survey_admin_subquery = (
        db.session.query(
            SurveyAdmin.survey_uid,
            SurveyAdmin.user_uid,
            Survey.survey_name,
        )
        .join(Survey, SurveyAdmin.survey_uid == Survey.survey_uid)
        .distinct()
        .subquery()
    )

    # Apply conditions based on current_user.is_super_admin
    if current_user.is_super_admin and survey_uid is None:
        users = (
            db.session.query(
                User,
                invite_subquery.c.is_active.label("invite_is_active"),
                func.array_agg(
                    distinct(
                        case(
                            [
                                (
                                    roles_subquery.c.role_name.isnot(None),
                                    func.jsonb_build_object(
                                        "role_name",
                                        roles_subquery.c.role_name,
                                        "survey_name",
                                        roles_subquery.c.survey_name,
                                    ),
                                )
                            ]
                        )
                    )
                ).label("user_survey_role_names"),
                func.array_agg(
                    distinct(
                        case(
                            [
                                (
                                    survey_admin_subquery.c.survey_name.isnot(None),
                                    survey_admin_subquery.c.survey_name,
                                )
                            ]
                        )
                    )
                ).label("user_admin_survey_names"),
                # Initialize survey level fields as null
                null().label("supervisor_uid"),
                null().label("location_uids"),
                null().label("location_ids"),
                null().label("location_names"),
                null().label("languages"),
            )
            .outerjoin(invite_subquery, User.user_uid == invite_subquery.c.user_uid)
            .outerjoin(
                survey_admin_subquery, survey_admin_subquery.c.user_uid == User.user_uid
            )
            .outerjoin(
                roles_subquery, (roles_subquery.c.role_uid == func.any(User.roles))
            )
            .group_by(
                User.user_uid,
                invite_subquery.c.is_active,
            )
        ).all()
    else:
        locations_subquery = (
            db.session.query(
                UserLocation.user_uid,
                func.array_agg(UserLocation.location_uid).label("location_uids"),
                func.array_agg(Location.location_id).label("location_ids"),
                func.array_agg(Location.location_name).label("location_names"),
            )
            .join(
                Location,
                (Location.location_uid == UserLocation.location_uid)
                & (Location.survey_uid == survey_uid),
            )
            .filter(UserLocation.survey_uid == survey_uid)
            .group_by(UserLocation.user_uid)
            .distinct()
            .subquery()
        )

        languages_subquery = (
            db.session.query(
                UserLanguage.user_uid,
                func.array_agg(UserLanguage.language).label("languages"),
            )
            .filter(UserLanguage.survey_uid == survey_uid)
            .group_by(UserLanguage.user_uid)
            .distinct()
            .subquery()
        )

        users = (
            db.session.query(
                User,
                invite_subquery.c.is_active.label("invite_is_active"),
                func.array_agg(
                    case(
                        [
                            (
                                roles_subquery.c.role_name.isnot(None),
                                func.json_build_object(
                                    "role_name",
                                    roles_subquery.c.role_name,
                                    "survey_name",
                                    roles_subquery.c.survey_name,
                                ),
                            )
                        ]
                    )
                ).label("user_survey_role_names"),
                func.array_agg(
                    case(
                        [
                            (
                                survey_admin_subquery.c.survey_name.isnot(None),
                                survey_admin_subquery.c.survey_name,
                            )
                        ]
                    )
                ).label("user_admin_survey_names"),
                UserHierarchy.parent_user_uid.label("supervisor_uid"),
                locations_subquery.c.location_uids,
                locations_subquery.c.location_ids,
                locations_subquery.c.location_names,
                languages_subquery.c.languages,
            )
            .outerjoin(invite_subquery, User.user_uid == invite_subquery.c.user_uid)
            .outerjoin(
                survey_admin_subquery,
                (survey_admin_subquery.c.user_uid == User.user_uid)
                & (survey_admin_subquery.c.survey_uid == survey_uid),
            )
            .outerjoin(
                roles_subquery,
                (roles_subquery.c.role_uid == func.any(User.roles))
                & (roles_subquery.c.survey_uid == survey_uid),
            )
            .outerjoin(
                UserHierarchy,
                (UserHierarchy.user_uid == User.user_uid)
                & (UserHierarchy.survey_uid == survey_uid),
            )
            .outerjoin(
                locations_subquery, (locations_subquery.c.user_uid == User.user_uid)
            )
            .outerjoin(
                languages_subquery, (languages_subquery.c.user_uid == User.user_uid)
            )
            .group_by(
                User.user_uid,
                invite_subquery.c.is_active,
                UserHierarchy.parent_user_uid,
                locations_subquery.c.location_uids,
                locations_subquery.c.location_ids,
                locations_subquery.c.location_names,
                languages_subquery.c.languages,
            )
            .filter(
                or_(
                    roles_subquery.c.survey_uid == survey_uid,
                    survey_admin_subquery.c.survey_uid == survey_uid,
                )
            )
        ).all()

    user_list = []

    for (
        user,
        invite_is_active,
        user_survey_role_names,
        user_admin_survey_names,
        supervisor_uid,
        location_uids,
        location_ids,
        location_names,
        languages,
    ) in users:
        user_data = {
            "user_uid": user.user_uid,
            "email": user.email,
            "first_name": user.first_name,
            "last_name": user.last_name,
            "roles": user.roles,
            "gender": user.gender,
            "user_survey_role_names": [
                role_name for role_name in user_survey_role_names if role_name
            ],
            "user_admin_survey_names": [
                survey_name for survey_name in user_admin_survey_names if survey_name
            ],
            "supervisor_uid": supervisor_uid,
            "location_uids": [
                location_uid for location_uid in location_uids if location_uid
            ]
            if location_uids
            else [],
            "location_ids": [location_id for location_id in location_ids if location_id]
            if location_ids
            else [],
            "location_names": [
                location_name for location_name in location_names if location_name
            ]
            if location_names
            else [],
            "languages": [language for language in languages if language]
            if languages
            else [],
            "is_super_admin": user.is_super_admin,
            "can_create_survey": user.can_create_survey,
            "status": ("Active" if user.active else "Deactivated"),
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
@validate_query_params(GetUserLocationsParamValidator)
def get_user_locations(validated_query_params):
    """Function to get user locations"""

    survey_uid = validated_query_params.survey_uid.data
    user_uid = validated_query_params.user_uid.data

    user_location_query = (
        db.session.query(
            UserLocation.user_uid,
            func.concat(
                User.first_name, ' ', User.last_name
            ).label('user_name'),
            UserLocation.location_uid,
            Location.location_id,
            Location.location_name,
        )
        .join(User, User.user_uid == UserLocation.user_uid)
        .join(
            Location,
            (Location.location_uid == UserLocation.location_uid)
            & (Location.survey_uid == survey_uid),
        )
        .filter(UserLocation.survey_uid == survey_uid)
    )

    if user_uid:
        user_location_query = user_location_query.filter(
            UserLocation.user_uid == user_uid
        )

    user_locations = user_location_query.all()

    if user_locations:
        return (
            jsonify(
                {
                    "success": True,
                    "data": [
                        {
                            "user_uid": user_uid,
                            "user_name": user_name,
                            "location_uid": location_uid,
                            "location_id": location_id,
                            "location_name": location_name,
                        }
                        for user_uid, user_name, location_uid, location_id, location_name in user_locations
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
    location_uids = validated_payload.location_uids.data

    UserLocation.query.filter_by(survey_uid=survey_uid, user_uid=user_uid).delete()

    for location_uid in location_uids:
        user_location = UserLocation(
            survey_uid=survey_uid,
            user_uid=user_uid,
            location_uid=location_uid,
        )
        db.session.add(user_location)

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

    try:
        db.session.commit()
        return jsonify(message="User locations deleted successfully"), 200
    except Exception as e:
        db.session.rollback()
        return jsonify(message=str(e)), 500


# User Languages
@user_management_bp.route("/user-languages", methods=["GET"])
@logged_in_active_user_required
@validate_query_params(GetUserLanguagesParamValidator)
def get_user_languages(validated_query_params):
    """Function to get user languages"""

    survey_uid = validated_query_params.survey_uid.data
    user_uid = validated_query_params.user_uid.data

    user_language_query = (
        db.session.query(
            UserLanguage.user_uid,
            func.concat(
                User.first_name, ' ', User.last_name
            ).label('user_name'),
            UserLanguage.language,
        )
        .join(User, User.user_uid == UserLanguage.user_uid)
        .filter(UserLanguage.survey_uid == survey_uid)
    )

    if user_uid:
        user_language_query = user_language_query.filter(
            UserLanguage.user_uid == user_uid
        )

    user_languages = user_language_query.all()

    if user_languages:
        return (
            jsonify(
                {
                    "success": True,
                    "data": [
                        {
                            "user_uid": user_uid,
                            "user_name": user_name,
                            "language": language,
                        }
                        for user_uid, user_name, language in user_languages
                    ],
                }
            ),
            200,
        )
    else:
        return jsonify(message="User languages not found"), 404
