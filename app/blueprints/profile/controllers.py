from . import profile_bp
import os
from app.utils.utils import logged_in_active_user_required, validate_payload
from werkzeug.utils import secure_filename
from flask import jsonify, current_app
from flask_login import current_user
from app import db
from .validators import (
    UpdateUserProfileValidator,
    UploadUserAvatarValidator,
)
import boto3
from sqlalchemy import cast, ARRAY, func

from app.blueprints.roles.models import Role, Permission, RolePermission, SurveyAdmin


@profile_bp.route("", methods=["GET"])
@logged_in_active_user_required
def get_profile():
    """
    Returns the profile of the logged in user
    """

    final_result = {
        "user_uid": current_user.user_uid,
        "first_name": current_user.first_name,
        "middle_name": current_user.middle_name,
        "last_name": current_user.last_name,
        "email": current_user.email,
        "phone_primary": current_user.phone_primary,
        "home_state_name": current_user.home_state,
        "home_district_name": current_user.home_district,
        "is_super_admin": current_user.is_super_admin,
        "can_create_survey": current_user.can_create_survey,
        "roles": [],
    }

    user_permissions = (
        db.session.query(Role, Permission.name, Permission.permission_uid)
        .filter(Role.role_uid == func.any(current_user.roles))
        .join(RolePermission, Role.role_uid == RolePermission.role_uid)
        .join(Permission, Permission.permission_uid == RolePermission.permission_uid)
        .group_by(Role.role_uid, Permission.name, Permission.permission_uid)
        .all()
    )

    admin_surveys_query = (
        db.session.query(SurveyAdmin.survey_uid)
        .filter(SurveyAdmin.user_uid == current_user.user_uid)
        .all()
    )

    admin_surveys = [survey_id for (survey_id,) in admin_surveys_query]

    final_result["admin_surveys"] = admin_surveys
    # Process roles data if available
    if user_permissions:
        role_data = {}
        for role, permission_name, permission_uid in user_permissions:
            if role.role_uid not in role_data:

                role_data[role.role_uid] = {
                    "survey_uid": role.survey_uid,
                    "role_uid": role.survey_uid,
                    "role_name": role.role_name,
                    "permission_names": [],
                    "permission_uids": [],
                }
            role_data[role.role_uid]["permission_names"].append(permission_name)
            role_data[role.role_uid]["permission_uids"].append(permission_uid)

        # Convert dictionary to list of role_data
        final_result["roles"] = list(role_data.values())

    return jsonify(final_result)


@profile_bp.route("", methods=["PATCH"])
@logged_in_active_user_required
@validate_payload(UpdateUserProfileValidator)
def update_profile(validated_payload):
    """
    Updates the profile of the logged in user
    """
    current_user.email = validated_payload.new_email.data
    db.session.commit()

    return jsonify(message="Profile updated"), 200


@profile_bp.route("/avatar", methods=["GET"])
@logged_in_active_user_required
def get_profile_avatar():
    """
    Returns a presigned url for the profile avatar image of the logged in user
    """

    if current_user.avatar_s3_filekey:
        url = boto3.client(
            "s3", current_app.config["AWS_REGION"]
        ).generate_presigned_url(
            "get_object",
            Params={
                "Bucket": current_app.config["S3_BUCKET_NAME"],
                "Key": current_user.avatar_s3_filekey,
            },
            ExpiresIn=60,
        )
    else:
        url = None

    final_result = {"image_url": url}

    return jsonify(final_result)


@profile_bp.route("/avatar", methods=["PUT"])
@logged_in_active_user_required
def update_profile_avatar():
    """
    Updates the profile avatar image of the logged in user
    """

    # This method uses an HTML form to upload the image so we don't use the validate_payload decorator here (which is for JSON payloads)
    form = UploadUserAvatarValidator()

    if not form.validate_on_submit():
        return jsonify(errors=form.errors), 422
    f = form.image.data
    user_provided_filename = secure_filename(f.filename)
    extension = os.path.splitext(user_provided_filename)[1]
    s3_filekey = "images/avatars/" + str(current_user.user_uid) + extension

    boto3.client("s3", current_app.config["AWS_REGION"]).upload_fileobj(
        f, current_app.config["S3_BUCKET_NAME"], s3_filekey
    )

    current_user.avatar_s3_filekey = s3_filekey
    db.session.commit()

    return jsonify(message="Success"), 200


@profile_bp.route("/avatar/remove", methods=["POST"])
@logged_in_active_user_required
def remove_profile_avatar():
    """
    Removes the profile avatar image of the logged in user
    """

    boto3.client("s3", current_app.config["AWS_REGION"]).delete_object(
        Bucket=current_app.config["S3_BUCKET_NAME"],
        Key=current_user.avatar_s3_filekey,
    )

    current_user.avatar_s3_filekey = None
    db.session.commit()

    return jsonify(message="Success"), 200
