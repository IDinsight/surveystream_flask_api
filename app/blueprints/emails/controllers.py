from . import emails_bp
from app.utils.utils import (
    custom_permissions_required,
    logged_in_active_user_required,
    validate_payload,
)
from flask import jsonify
from app import db
from .validators import (
    EmailScheduleValidator,
    ManualEmailTriggerValidator,
    EmailTemplateValidator,
)
from .models import EmailSchedule, ManualEmailTrigger, EmailTemplate


@emails_bp.route("/schedule", methods=["POST"])
@logged_in_active_user_required
@validate_payload(EmailScheduleValidator)
@custom_permissions_required("WRITE Email", "body", "form_uid")
def create_email_schedule(validated_payload):
    data = validated_payload
    new_schedule = EmailSchedule(
        form_uid=data["form_uid"],
        date=data["date"],
        time=data["time"],
        template_uid=data["template_uid"],
    )
    db.session.add(new_schedule)
    db.session.commit()
    return jsonify({"message": "Email schedule created successfully"}), 201


@emails_bp.route("/schedule/<int:form_uid>", methods=["GET"])
@logged_in_active_user_required
@custom_permissions_required("READ Email", "path", "form_uid")
def get_email_schedules(form_uid):
    email_schedules = EmailSchedule.query.get_or_404(form_uid)
    return jsonify(email_schedule=email_schedules.serialize())


@emails_bp.route("/schedule/<int:schedule_id>", methods=["PUT"])
@logged_in_active_user_required
@validate_payload(EmailScheduleValidator)
@custom_permissions_required("WRITE Email", "body", "form_uid")
def update_email_schedule(schedule_id, validated_payload):
    data = validated_payload
    email_schedule = EmailSchedule.query.get_or_404(schedule_id)
    for key, value in data.items():
        setattr(email_schedule, key, value)
    db.session.commit()
    return jsonify(message="Email schedule updated successfully")


@emails_bp.route("/schedule/<int:schedule_id>", methods=["DELETE"])
@logged_in_active_user_required
@custom_permissions_required("WRITE Email", "body", "schedule_id")
def delete_email_schedule(schedule_id):
    email_schedule = EmailSchedule.query.get_or_404(schedule_id)
    db.session.delete(email_schedule)
    db.session.commit()
    return jsonify(message="Email schedule deleted successfully")


@emails_bp.route("/manual-trigger", methods=["POST"])
@logged_in_active_user_required
@validate_payload(ManualEmailTriggerValidator)
@custom_permissions_required("WRITE Email", "body", "form_uid")
def create_manual_email_trigger(validated_payload):
    data = validated_payload
    new_trigger = ManualEmailTrigger(
        form_uid=data["form_uid"],
        date=data["date"],
        time=data["time"],
        recipients=data["recipients"],
        template_uid=data["template_uid"],
        status=data["status"],
    )
    db.session.add(new_trigger)
    db.session.commit()
    return jsonify({"message": "Manual email trigger created successfully"}), 201


@emails_bp.route("/manual-triggers/<int:form_uid>", methods=["GET"])
@logged_in_active_user_required
@custom_permissions_required("READ Email", "body", "form_uid")
def get_manual_email_trigger(form_uid):
    manual_email_trigger = ManualEmailTrigger.query.get_or_404(form_uid)
    return jsonify(manual_email_trigger=manual_email_trigger.serialize())


@emails_bp.route("/manual-trigger/<int:trigger_id>", methods=["PUT"])
@logged_in_active_user_required
@validate_payload(ManualEmailTriggerValidator)
@custom_permissions_required("WRITE Email", "body", "schedule_id")
def update_manual_email_trigger(trigger_id, validated_payload):
    data = validated_payload
    manual_email_trigger = ManualEmailTrigger.query.get_or_404(trigger_id)
    for key, value in data.items():
        setattr(manual_email_trigger, key, value)
    db.session.commit()
    return jsonify(message="Manual email trigger updated successfully")


@emails_bp.route("/manual-trigger/<int:trigger_id>", methods=["DELETE"])
@logged_in_active_user_required
@custom_permissions_required("WRITE Email", "body", "trigger_id")
def delete_manual_email_trigger(trigger_id):
    manual_email_trigger = ManualEmailTrigger.query.get_or_404(trigger_id)
    db.session.delete(manual_email_trigger)
    db.session.commit()
    return jsonify(message="Manual email trigger deleted successfully")


# TODO: implement template endpoints here
@emails_bp.route("/template", methods=["POST"])
@logged_in_active_user_required
@validate_payload(EmailTemplateValidator)
@custom_permissions_required("ADMIN")
def create_email_template(validated_payload):
    data = validated_payload
    new_template = EmailTemplate(
        template_name=data["template_name"],
        subject=data["subject"],
        sender_email=data["sender_email"],
        content=data["content"],
    )
    db.session.add(new_template)
    db.session.commit()
    return jsonify({"message": "Email template created successfully"}), 201
