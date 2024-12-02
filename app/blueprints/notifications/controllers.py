from flask import jsonify

from app.blueprints.module_selection.models import Module
from app.blueprints.roles.models import Permission, Role, RolePermission, SurveyAdmin
from app.blueprints.surveys.models import Survey
from app.blueprints.user_management.models import User
from app.utils.utils import (
    logged_in_active_user_required,
    validate_payload,
    validate_query_params,
)

from .models import SurveyNotification, UserNotification, db
from .routes import notifications_bp
from .validators import (
    GetNotificationsQueryValidator,
    PostNotificationsPayloadValidator,
    PutNotificationsPayloadValidator,
)


@notifications_bp.route("", methods=["GET"])
@logged_in_active_user_required
@validate_query_params(GetNotificationsQueryValidator)
def get_notifications(validated_query_params):
    user_uid = validated_query_params.user_uid.data
    user = User.query.get_or_404(user_uid)

    user_notifications = []
    user_notifications = UserNotification.query.filter(
        UserNotification.user_uid == user_uid
    ).all()

    survey_notifications_dict = []
    # If the user is a super admin, return all survey notifications
    if user.is_super_admin:
        survey_notifications = (
            db.session.query(
                SurveyNotification,
                Survey.survey_id,
                Module.name.label("module_name"),
            )
            .join(Survey, Survey.survey_uid == SurveyNotification.survey_uid)
            .join(Module, Module.module_id == SurveyNotification.module_id)
            .all()
        )
        survey_notifications_dict = [
            {
                "survey_id": notification.survey_id,
                "module_name": notification.module_name,
                **notification.SurveyNotification.to_dict(),
            }
            for notification in survey_notifications
        ]
    else:
        # Check if user is survey admin for any survey
        survey_admin = SurveyAdmin.query.filter(SurveyAdmin.user_uid == user_uid).all()
        admin_access_survey_uids = [
            survey.survey_uid for survey in survey_admin if survey_admin is not None
        ]

        # IF Survey Admin for any survey pull all notifications for that survey
        if len(admin_access_survey_uids) > 0:
            survey_notifications = SurveyNotification.query.filter(
                SurveyNotification.survey_uid.in_(admin_access_survey_uids)
            ).all()
            survey_notifications = (
                db.session.query(
                    SurveyNotification,
                    Survey.survey_id,
                    Module.name.label("module_name"),
                )
                .join(Survey, Survey.survey_uid == SurveyNotification.survey_uid)
                .join(Module, Module.module_id == SurveyNotification.module_id)
                .filter(SurveyNotification.survey_uid.in_(admin_access_survey_uids))
                .all()
            )
            survey_notifications_dict += [
                {
                    "survey_id": notification.survey_id,
                    "module_name": notification.module_name,
                    **notification.SurveyNotification.to_dict(),
                }
                for notification in survey_notifications
            ]

        survey_notifications = (
            db.session.query(
                SurveyNotification,
                Survey.survey_id,
                Module.name.label("module_name"),
            )
            .select_from(SurveyNotification)
            .join(Survey, Survey.survey_uid == SurveyNotification.survey_uid)
            .join(Module, Module.module_id == SurveyNotification.module_id)
            .join(Role, Role.survey_uid == SurveyNotification.survey_uid)
            .join(User, User.roles.any(Role.role_uid))
            .join(Permission, Module.module_id == Permission.module_id)
            .join(
                RolePermission,
                (Role.role_uid == RolePermission.role_uid)
                & (RolePermission.permission_uid == Permission.permission_uid),
            )
            .filter(
                User.user_uid == user_uid,
                Permission.active,
                SurveyNotification.survey_uid.notin_(admin_access_survey_uids),
            )
            .all()
        )
        survey_notifications_dict += [
            {
                "survey_id": notification.survey_id,
                "module_name": notification.module_name,
                **notification.SurveyNotification.to_dict(),
            }
            for notification in survey_notifications
        ]
    return jsonify(
        {
            "success": True,
            "user_notifications": [
                notification.to_dict() for notification in user_notifications
            ],
            "survey_notifications": survey_notifications_dict,
        }
    )


@notifications_bp.route("", methods=["POST"])
@logged_in_active_user_required
@validate_payload(PostNotificationsPayloadValidator)
def post_notifications(validated_payload):

    user_uid = validated_payload.user_uid.data

    if user_uid:
        user = User.query.get_or_404(user_uid)

        user_notification = UserNotification(
            user_uid=user_uid,
            notification_status=validated_payload.notification_status.data,
            notification_message=validated_payload.notification_message.data,
            notification_type=validated_payload.notification_type.data,
        )

        db.session.add(user_notification)

        notification = user_notification

    else:
        survey_uid = validated_payload.survey_uid.data
        survey = Survey.query.get_or_404(survey_uid)

        module_id = validated_payload.module_id.data
        module = Module.query.get_or_404(module_id)

        survey_notification = SurveyNotification(
            survey_uid=survey_uid,
            module_id=module_id,
            notification_status=validated_payload.notification_status.data,
            notification_message=validated_payload.notification_message.data,
            notification_type=validated_payload.notification_type.data,
        )

        db.session.add(survey_notification)

        notification = survey_notification

    try:
        db.session.commit()
    except Exception as e:
        db.session.rollback()
        return (
            jsonify(
                {
                    "error": str(e),
                    "success": False,
                }
            ),
            500,
        )

    response = jsonify(
        {
            "success": True,
            "message": "Notification created successfully",
            "data": notification.to_dict(),
        }
    )
    return response, 200


@notifications_bp.route("", methods=["PUT"])
@logged_in_active_user_required
@validate_payload(PutNotificationsPayloadValidator)
def put_notifications(validated_payload):
    user_notification_uid = validated_payload.user_notification_uid.data
    survey_notification_uid = validated_payload.survey_notification_uid.data

    if user_notification_uid:
        user_notification = UserNotification.query.get_or_404(user_notification_uid)
        user_notification.notification_status = (
            validated_payload.notification_status.data
        )
        user_notification.notification_type = validated_payload.notification_type.data
        user_notification.notification_message = (
            validated_payload.notification_message.data
        )
        notification = user_notification

    elif survey_notification_uid:
        survey_notification = SurveyNotification.query.get_or_404(
            survey_notification_uid
        )
        survey_notification.notification_status = (
            validated_payload.notification_status.data
        )
        survey_notification.notification_type = validated_payload.notification_type.data
        survey_notification.notification_message = (
            validated_payload.notification_message.data
        )
        notification = survey_notification

    else:
        return (
            jsonify(
                {
                    "error": "Invalid request, Either survey_notification_uid or user_notificiation_uid should be provided",
                    "success": False,
                }
            ),
            400,
        )

    try:
        db.session.commit()
    except Exception as e:
        db.session.rollback()
        return (
            jsonify(
                {
                    "error": str(e),
                    "success": False,
                }
            ),
            500,
        )

    response = jsonify(
        {
            "success": True,
            "message": "Notification updated successfully",
            "data": notification.to_dict(),
        }
    )
    return response, 200
