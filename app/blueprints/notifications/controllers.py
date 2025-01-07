from flask import jsonify
from flask_login import current_user

from app.blueprints.module_selection.models import Module, ModuleStatus
from app.blueprints.roles.models import Permission, Role, RolePermission, SurveyAdmin
from app.blueprints.surveys.models import Survey
from app.blueprints.user_management.models import User
from app.utils.utils import (
    custom_permissions_required,
    logged_in_active_user_required,
    validate_payload,
)

from .models import (
    NotificationAction,
    NotificationTemplate,
    SurveyNotification,
    UserNotification,
    db,
)
from .routes import notifications_bp
from .utils import check_notification_conditions
from .validators import (
    PostActionPayloadValidator,
    PostNotificationsPayloadValidator,
    PutNotificationsPayloadValidator,
    ResolveNotificationPayloadValidator,
)


@notifications_bp.route("", methods=["GET"])
@logged_in_active_user_required
def get_notifications():
    """
    Get all notification for a user.
    Collects all notificacations based on role of user.

    """
    user = current_user
    user_uid = user.user_uid

    if not user:
        return (
            jsonify(
                {
                    "error": "User not found",
                    "success": False,
                }
            ),
            404,
        )

    user_notifications = []
    user_notifications = (
        UserNotification.query.filter(UserNotification.user_uid == user_uid)
        .order_by(UserNotification.created_at.desc())
        .all()
    )

    user_notification_dict = [
        {
            "type": "user",
            **notification.to_dict(),
        }
        for notification in user_notifications
    ]

    survey_notifications_dict = []
    # If the user is a super admin, return all survey notifications
    if user.is_super_admin:
        survey_notifications = (
            db.session.query(
                SurveyNotification,
                Survey.survey_id,
                Module.module_id,
                Module.name.label("module_name"),
            )
            .join(Survey, Survey.survey_uid == SurveyNotification.survey_uid)
            .join(Module, Module.module_id == SurveyNotification.module_id)
            .order_by(SurveyNotification.created_at.desc())
            .all()
        )
        survey_notifications_dict = [
            {
                "survey_id": notification.survey_id,
                "survey_uid": notification.SurveyNotification.survey_uid,
                "module_name": notification.module_name,
                "module_id": notification.module_id,
                "type": "survey",
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
                    Module.module_id,
                    Module.name.label("module_name"),
                )
                .join(Survey, Survey.survey_uid == SurveyNotification.survey_uid)
                .join(Module, Module.module_id == SurveyNotification.module_id)
                .filter(SurveyNotification.survey_uid.in_(admin_access_survey_uids))
                .order_by(SurveyNotification.created_at.desc())
                .all()
            )
            survey_notifications_dict += [
                {
                    "survey_id": notification.survey_id,
                    "survey_uid": notification.SurveyNotification.survey_uid,
                    "module_name": notification.module_name,
                    "module_id": notification.module_id,
                    "type": "survey",
                    **notification.SurveyNotification.to_dict(),
                }
                for notification in survey_notifications
            ]

        survey_notifications = (
            db.session.query(
                SurveyNotification,
                Survey.survey_id,
                Module.module_id,
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
            .order_by(SurveyNotification.created_at.desc())
            .all()
        )
        survey_notifications_dict += [
            {
                "survey_id": notification.survey_id,
                "survey_uid": notification.SurveyNotification.survey_uid,
                "module_name": notification.module_name,
                "module_id": notification.module_id,
                "type": "survey",
                **notification.SurveyNotification.to_dict(),
            }
            for notification in survey_notifications
        ]

    # Sort notifications by created_at
    notifications = sorted(
        survey_notifications_dict + user_notification_dict,
        key=lambda x: x["created_at"],
        reverse=True,
    )
    return jsonify(
        {
            "success": True,
            "data": notifications,
        }
    )


@notifications_bp.route("", methods=["POST"])
@logged_in_active_user_required
@validate_payload(PostNotificationsPayloadValidator)
def post_notifications(validated_payload):
    """
    Create a Notification based on type

    """

    type = validated_payload.type.data
    if type == "survey":
        survey_uid = validated_payload.survey_uid.data
        survey = Survey.query.filter(Survey.survey_uid == survey_uid).first()

        if not survey:
            return (
                jsonify(
                    {
                        "error": "Survey not found",
                        "success": False,
                    }
                ),
                404,
            )

        module_id = validated_payload.module_id.data
        module = Module.query.filter(Module.module_id == module_id).first()

        if not module:
            return (
                jsonify(
                    {
                        "error": "Module not found",
                        "success": False,
                    }
                ),
                404,
            )

        notification = SurveyNotification(
            survey_uid=survey_uid,
            module_id=module_id,
            resolution_status=validated_payload.resolution_status.data,
            message=validated_payload.message.data,
            severity=validated_payload.severity.data,
        )

        db.session.add(notification)

        if (
            validated_payload.severity.data == "error"
            and validated_payload.resolution_status.data != "done"
        ):
            ModuleStatus.query.filter(
                ModuleStatus.module_id == module_id,
                ModuleStatus.survey_uid == survey_uid,
            ).update({"config_status": "Error"})

    else:
        user_uid = validated_payload.user_uid.data
        user = User.query.filter(User.user_uid == user_uid).first()

        if not user:
            return (
                jsonify(
                    {
                        "error": "User not found",
                        "success": False,
                    }
                ),
                404,
            )

        notification = UserNotification(
            user_uid=user_uid,
            resolution_status=validated_payload.resolution_status.data,
            message=validated_payload.message.data,
            severity=validated_payload.severity.data,
        )

        db.session.add(notification)

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
    """
    Update a notification based on type
    """

    type = validated_payload.type.data
    notification_uid = validated_payload.notification_uid.data

    if type == "survey":
        survey_notification = SurveyNotification.query.filter(
            SurveyNotification.notification_uid == notification_uid
        ).first()

        if not survey_notification:
            return (
                jsonify(
                    {
                        "error": "Notification not found",
                        "success": False,
                    }
                ),
                404,
            )

        survey_notification.resolution_status = validated_payload.resolution_status.data
        survey_notification.severity = validated_payload.severity.data
        survey_notification.message = validated_payload.message.data
        notification = survey_notification

        if validated_payload.severity.data == "error":
            config_status = (
                "Error"
                if validated_payload.resolution_status.data != "done"
                else "Done"
            )
            ModuleStatus.query.filter(
                ModuleStatus.module_id == notification.module_id,
                ModuleStatus.survey_uid == notification.survey_uid,
            ).update({"config_status": config_status})

    else:
        user_notification = UserNotification.query.filter(
            UserNotification.notification_uid == notification_uid
        ).first()

        if not user_notification:
            return (
                jsonify(
                    {
                        "error": "Notification not found",
                        "success": False,
                    }
                ),
                404,
            )

        user_notification.resolution_status = validated_payload.resolution_status.data
        user_notification.severity = validated_payload.severity.data
        user_notification.message = validated_payload.message.data
        notification = user_notification

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


@notifications_bp.route("", methods=["PATCH"])
@logged_in_active_user_required
@validate_payload(ResolveNotificationPayloadValidator)
def resolve_notification(validated_payload):
    """
    Resolve a notification based on type
    """

    type = validated_payload.type.data
    notification_uid = validated_payload.notification_uid.data
    survey_uid = validated_payload.survey_uid.data
    module_id = validated_payload.module_id.data
    resolution_status = validated_payload.resolution_status.data

    if not (type and notification_uid) and not (survey_uid and module_id):
        return (
            jsonify(
                {
                    "error": "Either notification_uid or both survey_uid and module_id must be present.",
                    "success": False,
                }
            ),
            404,
        )

    if notification_uid:
        if type == "survey":
            notification = SurveyNotification.query.filter(
                SurveyNotification.notification_uid == notification_uid
            ).first()

            if not notification:
                return (
                    jsonify(
                        {
                            "error": "Notification not found",
                            "success": False,
                        }
                    ),
                    404,
                )
            if resolution_status == "done":

                ModuleStatus.query.filter(
                    ModuleStatus.module_id == notification.module_id,
                    ModuleStatus.survey_uid == notification.survey_uid,
                    ModuleStatus.config_status == "Error",
                ).update({"config_status": "Done"})

        elif type == "user":
            notification = UserNotification.query.filter(
                UserNotification.notification_uid == notification_uid
            ).first()

            if not notification:
                return (
                    jsonify(
                        {
                            "error": "Notification not found",
                            "success": False,
                        }
                    ),
                    404,
                )

        notification.resolution_status = resolution_status

    else:
        survey_notifications = SurveyNotification.query.filter(
            SurveyNotification.survey_uid == survey_uid,
            SurveyNotification.module_id == module_id,
        ).all()

        for survey_notification in survey_notifications:
            survey_notification.resolution_status = resolution_status

        if resolution_status == "done":

            ModuleStatus.query.filter(
                ModuleStatus.module_id == module_id,
                ModuleStatus.survey_uid == survey_uid,
                ModuleStatus.config_status == "Error",
            ).update({"config_status": "Done"})

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
            "message": "Notification resolved successfully",
        }
    )

    return response, 200


@notifications_bp.route("/action", methods=["POST"])
@logged_in_active_user_required
@validate_payload(PostActionPayloadValidator)
@custom_permissions_required("ADMIN")
def create_notification_via_action(validated_payload):
    """
    Create a Notification based on action
    """

    survey_uid = validated_payload.survey_uid.data
    action = validated_payload.action.data
    form_uid = validated_payload.form_uid.data

    survey = Survey.query.filter(Survey.survey_uid == survey_uid).first()

    if not survey:
        return (
            jsonify(
                {
                    "error": "Survey not found",
                    "success": False,
                }
            ),
            404,
        )

    notification_action = NotificationAction.query.filter(
        NotificationAction.name == action
    ).first()

    if not notification_action:
        return (
            jsonify(
                {
                    "error": "Action not found",
                    "success": False,
                }
            ),
            404,
        )

    notification_template = NotificationTemplate.query.filter(
        NotificationTemplate.notification_template_uid.in_(
            notification_action.notification_template_list
        )
    ).all()

    notification_created_flag = False
    for template in notification_template:
        if check_notification_conditions(
            notification_action.module_id,
            template.module_id,
            survey_uid,
            form_uid,
        ):
            message = notification_action.message + " " + template.message
            notification = SurveyNotification(
                survey_uid=survey_uid,
                module_id=template.module_id,
                resolution_status="in progress",
                message=message,
                severity=template.severity,
            )

            db.session.add(notification)
            notification_created_flag = True

            if template.severity == "error":
                ModuleStatus.query.filter(
                    ModuleStatus.module_id == template.module_id,
                    ModuleStatus.survey_uid == survey_uid,
                ).update({"config_status": "Error"})

    if not notification_created_flag:
        return (
            jsonify(
                {
                    "error": "No notification created for the action, conditions not met",
                    "success": False,
                }
            ),
            422,
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
            "message": "Notification created successfully",
        }
    )

    return response, 200
