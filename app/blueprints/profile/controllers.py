from . import profile_bp
import os
from app.utils.utils import logged_in_active_user_required
from werkzeug.utils import secure_filename
from flask import jsonify, request, current_app
from flask_login import current_user
from app import db
from .validators import (
    UpdateUserProfileValidator,
    UploadUserAvatarValidator,
    RemoveUserAvatarValidator,
)
import boto3


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
    }

    return jsonify(final_result)


@profile_bp.route("", methods=["PATCH"])
@logged_in_active_user_required
def update_profile():
    """
    Updates the profile of the logged in user
    """
    form = UpdateUserProfileValidator.from_json(request.get_json())

    if form.validate():
        current_user.email = form.new_email.data
        db.session.commit()

        return jsonify(message="Profile updated"), 200

    else:
        return jsonify(message=form.errors), 422


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
    form = UploadUserAvatarValidator()

    if form.validate_on_submit():
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

    else:
        return jsonify(message=form.errors), 422


@profile_bp.route("/avatar/remove", methods=["POST"])
@logged_in_active_user_required
def remove_profile_avatar():
    """
    Removes the profile avatar image of the logged in user
    """
    form = RemoveUserAvatarValidator()

    if form.validate():
        boto3.client("s3", current_app.config["AWS_REGION"]).delete_object(
            Bucket=current_app.config["S3_BUCKET_NAME"],
            Key=current_user.avatar_s3_filekey,
        )

        current_user.avatar_s3_filekey = None
        db.session.commit()

        return jsonify(message="Success"), 200

    else:
        return jsonify(message=form.errors), 422
