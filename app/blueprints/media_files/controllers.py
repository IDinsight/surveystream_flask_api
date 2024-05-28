from flask import jsonify, request
from app.utils.utils import (
    custom_permissions_required,
    logged_in_active_user_required,
    validate_query_params,
    validate_payload,
)
from .models import db, MediaFilesConfig
from .routes import media_files_bp
from .validators import (
    MediaFilesConfigQueryParamValidator,
    CreateMediaFilesConfigValidator,
    MediaFilesConfigValidator,
)


@media_files_bp.route("", methods=["GET"])
@logged_in_active_user_required
@validate_query_params(MediaFilesConfigQueryParamValidator)
@custom_permissions_required("READ Media Files Config", "query", "form_uid")
def get_media_files_configs(validated_query_params):
    """
    Method to get all the media files config linked to a form

    """

    form_uid = validated_query_params.form_uid.data
    media_files_config = MediaFilesConfig.query.filter_by(form_uid=form_uid).all()

    data = [
        {
            "media_files_config_uid": config.media_files_config_uid,
            "file_type": config.file_type,
            "source": config.source,
            "scto_fields": config.scto_fields,
        }
        for config in media_files_config
    ]

    response = jsonify(
        {
            "success": True,
            "data": data,
        }
    )

    return response, 200


@media_files_bp.route("/<int:media_files_config_uid>", methods=["GET"])
@logged_in_active_user_required
@custom_permissions_required(
    "READ Media Files Config", "path", "media_files_config_uid"
)
def get_media_files_config(media_files_config_uid):
    """
    Function to get a particular media files config

    """
    media_files_config = MediaFilesConfig.query.get_or_404(media_files_config_uid)

    response = jsonify(
        {
            "success": True,
            "data": media_files_config.to_dict(),
        }
    )

    return response, 200


@media_files_bp.route("", methods=["POST"])
@logged_in_active_user_required
@validate_payload(CreateMediaFilesConfigValidator)
@custom_permissions_required("WRITE Media Files Config", "body", "form_uid")
def create_media_files_config(validated_payload):
    """
    Function to create a new media files config
    """
    form_uid = validated_payload.form_uid.data

    new_config = MediaFilesConfig(
        form_uid=form_uid,
        file_type=validated_payload.file_type.data,
        source=validated_payload.source.data,
        scto_fields=validated_payload.scto_fields.data,
    )

    try:
        db.session.add(new_config)
        db.session.commit()
    except Exception as e:
        db.session.rollback()
        return jsonify({"error": str(e)}), 500

    return (
        jsonify(
            {
                "success": True,
                "data": {
                    "message": "Media files config added successfully",
                    "config": new_config.to_dict(),
                },
            }
        ),
        201,
    )


@media_files_bp.route("/<int:media_files_config_uid>", methods=["PUT"])
@logged_in_active_user_required
@validate_payload(MediaFilesConfigValidator)
@custom_permissions_required(
    "WRITE Media Files Config", "path", "media_files_config_uid"
)
def update_media_files_config(media_files_config_uid, validated_payload):
    """
    Method to save media files config for a form
    """
    media_files_config = MediaFilesConfig.query.get_or_404(media_files_config_uid)

    media_files_config.file_type = validated_payload.file_type.data
    media_files_config.source = validated_payload.source.data
    media_files_config.scto_fields = validated_payload.scto_fields.data

    try:
        db.session.commit()
    except Exception as e:
        db.session.rollback()
        return jsonify({"error": str(e)}), 500

    response = jsonify(
        {
            "success": True,
            "data": {
                "message": "Media files config updated successfully",
                "config": media_files_config.to_dict(),
            },
        }
    )
    return response, 200


@media_files_bp.route("<int:media_files_config_uid>", methods=["DELETE"])
@logged_in_active_user_required
@custom_permissions_required(
    "WRITE Media Files Config", "path", "media_files_config_uid"
)
def delete_media_files_config(media_files_config_uid):
    """
    Function to delete a media file config
    """
    media_files_config = MediaFilesConfig.query.get_or_404(media_files_config_uid)

    try:
        db.session.delete(media_files_config)
        db.session.commit()
    except Exception as e:
        db.session.rollback()
        return jsonify({"error": str(e)}), 500

    return (
        jsonify(
            {
                "success": True,
                "data": {
                    "message": "Media files config deleted successfully",
                },
            }
        ),
        200,
    )
