from flask import jsonify, request
from sqlalchemy.exc import IntegrityError

from app.blueprints.forms.models import Form
from app.utils.utils import (
    custom_permissions_required,
    logged_in_active_user_required,
    update_module_status,
    update_module_status_after_request,
    validate_payload,
    validate_query_params,
)

from .models import MediaFilesConfig, db
from .routes import media_files_bp
from .validators import (
    CreateMediaFilesConfigValidator,
    MediaFilesConfigQueryParamValidator,
    MediaFilesConfigValidator,
)


@media_files_bp.route("", methods=["GET"])
@logged_in_active_user_required
@validate_query_params(MediaFilesConfigQueryParamValidator)
@custom_permissions_required("READ Media Files Config", "query", "survey_uid")
def get_media_files_configs(validated_query_params):
    """
    Method to get all the media files config linked to a survey

    """

    survey_uid = validated_query_params.survey_uid.data

    result = (
        db.session.query(MediaFilesConfig, Form)
        .join(
            Form,
            MediaFilesConfig.form_uid == Form.form_uid,
        )
        .filter(Form.survey_uid == survey_uid)
        .all()
    )

    data = [
        {
            "media_files_config_uid": media_files_config.media_files_config_uid,
            "form_uid": form.form_uid,
            "scto_form_id": form.scto_form_id,
            "file_type": media_files_config.file_type,
            "source": media_files_config.source,
            "format": media_files_config.format,
            "scto_fields": media_files_config.scto_fields,
            "media_fields": media_files_config.media_fields,
            "mapping_criteria": media_files_config.mapping_criteria,
            "google_sheet_key": media_files_config.google_sheet_key,
            "mapping_google_sheet_key": media_files_config.mapping_google_sheet_key,
        }
        for media_files_config, form in result
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
@update_module_status_after_request(12, "form_uid")
def create_media_files_config(validated_payload):
    """
    Function to create a new media files config
    """
    form_uid = validated_payload.form_uid.data

    new_config = MediaFilesConfig(
        form_uid=form_uid,
        file_type=validated_payload.file_type.data,
        source=validated_payload.source.data,
        format=validated_payload.format.data,
        scto_fields=validated_payload.scto_fields.data,
        media_fields=validated_payload.media_fields.data,
        mapping_criteria=validated_payload.mapping_criteria.data,
    )

    try:
        db.session.add(new_config)
        db.session.commit()
    except IntegrityError as e:
        db.session.rollback()
        return (
            jsonify(
                {
                    "success": False,
                    "error": {
                        "message": "A config already exists for this survey with the same scto_form_id, type and source"
                    },
                }
            ),
            400,
        )
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
    media_files_config.format = validated_payload.format.data
    media_files_config.scto_fields = validated_payload.scto_fields.data
    media_files_config.media_fields = validated_payload.media_fields.data
    media_files_config.mapping_criteria = validated_payload.mapping_criteria.data

    try:
        db.session.commit()

    except IntegrityError as e:
        db.session.rollback()
        return (
            jsonify(
                {
                    "success": False,
                    "error": {
                        "message": "A config already exists for this survey with the same scto_form_id, type and source"
                    },
                }
            ),
            400,
        )
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
    form_uid = media_files_config.form_uid

    try:
        db.session.delete(media_files_config)

        # Update the status of the module
        update_module_status(12, form_uid=form_uid)

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
