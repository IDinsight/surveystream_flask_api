from datetime import datetime

from flask import jsonify

from app import db
from app.utils.google_sheet_utils import (
    google_sheet_helpers,
    load_google_service_account_credentials,
)
from app.utils.utils import (
    custom_permissions_required,
    logged_in_active_user_required,
    validate_payload,
    validate_query_params,
)

from . import emails_bp
from .models import (
    EmailConfig,
    EmailSchedule,
    EmailTemplate,
    EmailTemplateVariable,
    ManualEmailTrigger,
)
from .validators import (
    EmailConfigQueryParamValidator,
    EmailConfigValidator,
    EmailGsheetSourceParamValidator,
    EmailGsheetSourcePatchParamValidator,
    EmailScheduleQueryParamValidator,
    EmailScheduleValidator,
    EmailTemplateQueryParamValidator,
    EmailTemplateValidator,
    ManualEmailTriggerPatchValidator,
    ManualEmailTriggerQueryParamValidator,
    ManualEmailTriggerValidator,
)


@emails_bp.route("/config", methods=["POST"])
@logged_in_active_user_required
@validate_payload(EmailConfigValidator)
@custom_permissions_required("WRITE Emails", "body", "form_uid")
def create_email_config(validated_payload):
    """
    Function to create a new email config
    """
    config_values = {
        "config_type": validated_payload.config_type.data,
        "form_uid": validated_payload.form_uid.data,
        "report_users": validated_payload.report_users.data,
        "email_source": validated_payload.email_source.data,
        "email_source_gsheet_link": validated_payload.email_source_gsheet_link.data,
        "email_source_gsheet_tab": validated_payload.email_source_gsheet_tab.data,
        "email_source_gsheet_header_row": validated_payload.email_source_gsheet_header_row.data,
        "email_source_tablename": validated_payload.email_source_tablename.data,
        "email_source_columns": validated_payload.email_source_columns.data,
    }

    # Check if the email config already exists
    check_config_exists = EmailConfig.query.filter_by(
        form_uid=validated_payload.form_uid.data,
        config_type=validated_payload.config_type.data,
    ).first()

    if check_config_exists is not None:
        return (
            jsonify(
                {"error": "Email Config already exists, Use PUT methood for update"}
            ),
            400,
        )

    email_config = EmailConfig(
        **config_values,
    )

    try:
        db.session.add(email_config)
        db.session.commit()
    except Exception as e:
        db.session.rollback()
        return jsonify({"error": str(e)}), 500

    return (
        jsonify(
            {
                "success": True,
                "message": "Email Config created successfully",
                "data": email_config.to_dict(),
            }
        ),
        201,
    )


@emails_bp.route("", methods=["GET"])  # /emails
@logged_in_active_user_required
@validate_query_params(EmailConfigQueryParamValidator)
@custom_permissions_required("READ Emails", "query", "form_uid")
def get_email_details(validated_query_params):
    """Function to get email configs per form including schedules and template details"""
    form_uid = validated_query_params.form_uid.data
    # Query to get email configs including related schedules and templates
    email_configs = (
        EmailConfig.query.outerjoin(
            EmailSchedule,
            EmailConfig.email_config_uid == EmailSchedule.email_config_uid,
        )
        .outerjoin(
            EmailTemplate,
            EmailConfig.email_config_uid == EmailTemplate.email_config_uid,
        )
        .outerjoin(
            ManualEmailTrigger,
            EmailConfig.email_config_uid == ManualEmailTrigger.email_config_uid,
        )
        .filter(EmailConfig.form_uid == form_uid)
        .all()
    )

    # Return 404 if no email configs found
    if not email_configs:
        return (
            jsonify(
                {
                    "success": False,
                    "data": None,
                    "message": "Email configs not found",
                }
            ),
            404,
        )

    # Process and structure the config data
    config_data = []
    for email_config in email_configs:
        config_data.append(
            {
                **email_config.to_dict(),
                "schedules": [
                    schedule.to_dict() for schedule in email_config.schedules
                ],
                "templates": [
                    template.to_dict() for template in email_config.templates
                ],
                "manual_triggers": [
                    trigger.to_dict() for trigger in email_config.manual_triggers
                ],
            }
        )

    # Return the response
    response = jsonify(
        {
            "success": True,
            "data": config_data,
        }
    )

    return response, 200


@emails_bp.route("/config", methods=["GET"])
@logged_in_active_user_required
@validate_query_params(EmailConfigQueryParamValidator)
@custom_permissions_required("READ Emails", "query", "form_uid")
def get_email_configs(validated_query_params):
    """Function to get email schedules  per form"""
    form_uid = validated_query_params.form_uid.data

    email_configs = EmailConfig.query.filter_by(form_uid=form_uid).all()

    if email_configs is None:
        return (
            jsonify(
                {
                    "success": False,
                    "data": None,
                    "message": "Email configs not found",
                }
            ),
            404,
        )

    config_data = []
    for email_config in email_configs:
        config_data.append(email_config.to_dict())

    response = jsonify(
        {
            "success": True,
            "data": config_data,
        }
    )

    return response, 200


@emails_bp.route("/config/<int:email_config_uid>", methods=["GET"])
@logged_in_active_user_required
@custom_permissions_required("READ Emails", "path", "email_config_uid")
def get_email_config(email_config_uid):
    """Function to get a particular email config given the email config uid"""
    email_config = EmailConfig.query.filter_by(
        email_config_uid=email_config_uid
    ).first()

    if email_config is None:
        return (
            jsonify(
                {
                    "success": False,
                    "data": None,
                    "message": "Email config not found",
                }
            ),
            404,
        )

    response = jsonify(
        {
            "success": True,
            "data": email_config.to_dict(),
        }
    )

    return response, 200


@emails_bp.route("/config/<int:email_config_uid>", methods=["PUT"])
@logged_in_active_user_required
@validate_payload(EmailConfigValidator)
@custom_permissions_required("WRITE Emails", "path", "email_config_uid")
def update_email_config(email_config_uid, validated_payload):
    """
    Function to update an email config
    """
    email_config = EmailConfig.query.get_or_404(email_config_uid)

    email_config.form_uid = validated_payload.form_uid.data
    email_config.config_type = validated_payload.config_type.data
    email_config.report_users = validated_payload.report_users.data
    email_config.email_source = validated_payload.email_source.data
    email_config.email_source_gsheet_link = (
        validated_payload.email_source_gsheet_link.data
    )
    email_config.email_source_tablename = validated_payload.email_source_tablename.data
    email_config.email_source_columns = validated_payload.email_source_columns.data
    email_config.email_source_gsheet_tab = (
        validated_payload.email_source_gsheet_tab.data
    )
    email_config.email_source_gsheet_header_row = (
        validated_payload.email_source_gsheet_header_row.data
    )

    try:
        db.session.commit()
    except Exception as e:
        db.session.rollback()
        return jsonify({"error": str(e)}), 500

    response = jsonify(
        {
            "success": True,
            "message": "Email config updated successfully",
            "data": email_config.to_dict(),
        }
    )
    return response, 200


@emails_bp.route("/config/<int:email_config_uid>", methods=["DELETE"])
@logged_in_active_user_required
@custom_permissions_required("WRITE Emails", "path", "email_config_uid")
def delete_email_config(email_config_uid):
    """
    Function to delete an email config
    """

    email_config = EmailConfig.query.get_or_404(email_config_uid)

    try:
        db.session.delete(email_config)
        db.session.commit()
    except Exception as e:
        db.session.rollback()
        return jsonify({"error": str(e)}), 500

    return jsonify(success=True, message="Email config deleted successfully")


@emails_bp.route("/schedule", methods=["POST"])
@logged_in_active_user_required
@validate_payload(EmailScheduleValidator)
@custom_permissions_required("WRITE Emails", "body", "email_config_uid")
def create_email_schedule(validated_payload):
    """
    Function to create a new email schedule validated by email_config_uid
    """

    time_str = validated_payload.time.data
    time_obj = datetime.strptime(time_str, "%H:%M").time()

    schedule_values = {
        "email_config_uid": validated_payload.email_config_uid.data,
        "email_schedule_name": validated_payload.email_schedule_name.data,
        "dates": validated_payload.dates.data,
        "time": time_obj,
    }

    # Check if the email schedule already exists
    check_schedule_exists = EmailSchedule.query.filter_by(
        email_config_uid=validated_payload.email_config_uid.data,
        email_schedule_name=validated_payload.email_schedule_name.data,
    ).first()
    if check_schedule_exists is not None:
        return (
            jsonify(
                {"error": "Email Schedule already exists, Use PUT methood for update"}
            ),
            400,
        )

    new_schedule = EmailSchedule(
        **schedule_values,
    )

    try:
        db.session.add(new_schedule)
        db.session.commit()
    except Exception as e:
        db.session.rollback()
        return jsonify({"error": str(e)}), 500

    return (
        jsonify(
            {
                "success": True,
                "message": "Email schedule created successfully",
                "data": new_schedule.to_dict(),
            }
        ),
        201,
    )


@emails_bp.route("/schedule", methods=["GET"])
@logged_in_active_user_required
@validate_query_params(EmailScheduleQueryParamValidator)
@custom_permissions_required("READ Emails", "query", "email_config_uid")
def get_email_schedules(validated_query_params):
    """Function to get email schedules  per email config"""
    email_config_uid = validated_query_params.email_config_uid.data

    email_schedules = EmailSchedule.query.filter_by(
        email_config_uid=email_config_uid
    ).all()

    if email_schedules is None:
        return (
            jsonify(
                {
                    "success": False,
                    "data": None,
                    "message": "Email schedules not found",
                }
            ),
            404,
        )

    schedule_data = []
    for email_schedule in email_schedules:
        schedule_data.append(email_schedule.to_dict())

    response = jsonify(
        {
            "success": True,
            "data": schedule_data,
        }
    )

    return response, 200


@emails_bp.route("/schedule/<int:email_schedule_uid>", methods=["GET"])
@logged_in_active_user_required
@validate_query_params(EmailScheduleQueryParamValidator)
@custom_permissions_required("READ Emails", "query", "email_config_uid")
def get_email_schedule(email_schedule_uid, validated_query_params):
    """Function to get a particular email schedule given the email schedule uid"""
    email_schedule = EmailSchedule.query.filter_by(
        email_schedule_uid=email_schedule_uid
    ).first()

    if email_schedule is None:
        return (
            jsonify(
                {
                    "success": False,
                    "data": None,
                    "message": "Email schedule not found",
                }
            ),
            404,
        )

    response = jsonify(
        {
            "success": True,
            "data": email_schedule.to_dict(),
        }
    )

    return response, 200


@emails_bp.route("/schedule/<int:schedule_id>", methods=["PUT"])
@logged_in_active_user_required
@validate_payload(EmailScheduleValidator)
@custom_permissions_required("WRITE Emails", "body", "email_config_uid")
def update_email_schedule(schedule_id, validated_payload):
    """
    Function to update an email schedule; permissions validated by email_config_uid
    """
    time_str = validated_payload.time.data
    time_obj = datetime.strptime(time_str, "%H:%M").time()

    email_schedule = EmailSchedule.query.get_or_404(schedule_id)

    email_schedule.email_config_uid = validated_payload.email_config_uid.data
    email_schedule.dates = validated_payload.dates.data
    email_schedule.time = time_obj
    email_schedule.email_schedule_name = validated_payload.email_schedule_name.data

    try:
        db.session.commit()
    except Exception as e:
        db.session.rollback()
        return jsonify({"error": str(e)}), 500

    response = jsonify(
        {
            "success": True,
            "message": "Email schedule updated successfully",
            "data": email_schedule.to_dict(),
        }
    )
    return response, 200


@emails_bp.route("/schedule/<int:schedule_id>", methods=["DELETE"])
@logged_in_active_user_required
@validate_query_params(EmailScheduleQueryParamValidator)
@custom_permissions_required("WRITE Emails", "query", "email_config_uid")
def delete_email_schedule(schedule_id, validated_query_params):
    """
    Function to delete an email schedule
    """

    email_schedule = EmailSchedule.query.get_or_404(schedule_id)

    try:
        db.session.delete(email_schedule)
        db.session.commit()
    except Exception as e:
        db.session.rollback()
        return jsonify({"error": str(e)}), 500

    return jsonify(success=True, message="Email schedule deleted successfully")


@emails_bp.route("/manual-trigger", methods=["POST"])
@logged_in_active_user_required
@validate_payload(ManualEmailTriggerValidator)
@custom_permissions_required("WRITE Emails", "body", "email_config_uid")
def create_manual_email_trigger(validated_payload):
    """
    Function to create a manual email trigger
    """
    time_str = validated_payload.time.data
    time_obj = datetime.strptime(time_str, "%H:%M").time()

    trigger_values = {
        "email_config_uid": validated_payload.email_config_uid.data,
        "date": validated_payload.date.data,
        "time": time_obj,
        "recipients": validated_payload.recipients.data,
        "status": validated_payload.status.data,
    }

    new_trigger = ManualEmailTrigger(**trigger_values)

    try:
        db.session.add(new_trigger)
        db.session.commit()
    except Exception as e:
        db.session.rollback()
        return jsonify({"error": str(e)}), 500

    return (
        jsonify(
            {
                "success": True,
                "message": "Manual email trigger created successfully",
                "data": new_trigger.to_dict(),
            }
        ),
        201,
    )


@emails_bp.route("/manual-trigger", methods=["GET"])
@logged_in_active_user_required
@validate_query_params(ManualEmailTriggerQueryParamValidator)
@custom_permissions_required("READ Emails", "query", "email_config_uid")
def get_manual_email_triggers(validated_query_params):
    """
    Function to get manual triggers per form
    """
    email_config_uid = validated_query_params.email_config_uid.data
    manual_email_triggers = ManualEmailTrigger.query.filter_by(
        email_config_uid=email_config_uid
    ).all()

    if manual_email_triggers is None:
        return (
            jsonify(
                {
                    "success": False,
                    "data": None,
                    "message": "Manual email triggers not found",
                }
            ),
            404,
        )

    trigger_data = []
    for manual_trigger in manual_email_triggers:
        trigger_data.append(manual_trigger.to_dict())

    response = jsonify(
        {
            "success": True,
            "data": trigger_data,
        }
    )

    return response, 200


@emails_bp.route("/manual-trigger/<int:manual_email_trigger_uid>", methods=["GET"])
@logged_in_active_user_required
@validate_query_params(ManualEmailTriggerQueryParamValidator)
@custom_permissions_required("READ Emails", "query", "email_config_uid")
def get_manual_email_trigger(manual_email_trigger_uid, validated_query_params):
    """
    Function to get a specific manual trigger
    """
    manual_email_trigger = ManualEmailTrigger.query.filter_by(
        manual_email_trigger_uid=manual_email_trigger_uid
    ).first()

    if manual_email_trigger is None:
        return (
            jsonify(
                {
                    "success": False,
                    "data": None,
                    "message": "Manual email trigger not found",
                }
            ),
            404,
        )

    response = jsonify(
        {
            "success": True,
            "data": manual_email_trigger.to_dict(),
        }
    )

    return response, 200


@emails_bp.route("/manual-trigger/<int:manual_email_trigger_uid>", methods=["PUT"])
@logged_in_active_user_required
@validate_payload(ManualEmailTriggerValidator)
@custom_permissions_required("WRITE Emails", "body", "email_config_uid")
def update_manual_email_trigger(manual_email_trigger_uid, validated_payload):
    """
    Function to update a manual trigger
    """
    time_str = validated_payload.time.data
    time_obj = datetime.strptime(time_str, "%H:%M").time()

    manual_email_trigger = ManualEmailTrigger.query.get_or_404(manual_email_trigger_uid)
    manual_email_trigger.email_config_uid = validated_payload.email_config_uid.data
    manual_email_trigger.date = validated_payload.date.data
    manual_email_trigger.time = time_obj
    manual_email_trigger.recipients = validated_payload.recipients.data
    manual_email_trigger.status = validated_payload.status.data

    try:
        db.session.commit()
    except Exception as e:
        db.session.rollback()
        return jsonify({"error": str(e)}), 500

    return (
        jsonify(
            success=True,
            message="Manual email trigger updated successfully",
            data=manual_email_trigger.to_dict(),
        ),
        200,
    )


@emails_bp.route("/manual-trigger/<int:manual_email_trigger_uid>", methods=["PATCH"])
@logged_in_active_user_required
@validate_payload(ManualEmailTriggerPatchValidator)
@custom_permissions_required("WRITE Emails", "body", "email_config_uid")
def update_manual_email_trigger_status(manual_email_trigger_uid, validated_payload):
    """
    Function to update a manual trigger status
    Requires the email_config_uid for permission reasons
    """

    manual_email_trigger = ManualEmailTrigger.query.get_or_404(manual_email_trigger_uid)
    manual_email_trigger.status = validated_payload.status.data

    try:
        db.session.commit()
    except Exception as e:
        db.session.rollback()
        return jsonify({"error": str(e)}), 500

    return (
        jsonify(
            success=True,
            message="Manual email trigger status updated successfully",
            data=manual_email_trigger.to_dict(),
        ),
        200,
    )


@emails_bp.route("/manual-trigger/<int:manual_email_trigger_uid>", methods=["DELETE"])
@logged_in_active_user_required
@validate_query_params(ManualEmailTriggerQueryParamValidator)
@custom_permissions_required("WRITE Emails", "query", "email_config_uid")
def delete_manual_email_trigger(manual_email_trigger_uid, validated_query_params):
    """
    Function to delete a manual trigger
    """
    manual_email_trigger = ManualEmailTrigger.query.get_or_404(manual_email_trigger_uid)

    try:
        db.session.delete(manual_email_trigger)
        db.session.commit()
    except Exception as e:
        db.session.rollback()
        return jsonify({"error": str(e)}), 500

    return jsonify(success=True, message="Manual email trigger deleted successfully")


@emails_bp.route("/template", methods=["POST"])
@logged_in_active_user_required
@validate_payload(EmailTemplateValidator)
@custom_permissions_required("WRITE Emails", "body", "email_config_uid")
def create_email_template(validated_payload):
    """
    Function to create an email template
    """
    template_values = {
        "email_config_uid": validated_payload.email_config_uid.data,
        "subject": validated_payload.subject.data,
        "language": validated_payload.language.data,
        "content": validated_payload.content.data,
    }

    # Check if the email template already exists
    check_email_template_exists = EmailTemplate.query.filter_by(
        email_config_uid=validated_payload.email_config_uid.data,
        language=validated_payload.language.data,
    ).first()
    if check_email_template_exists is not None:
        return (
            jsonify(
                {"error": "Email Template already exists, Use PUT methood for update"}
            ),
            400,
        )

    new_template = EmailTemplate(**template_values)

    try:
        db.session.add(new_template)
        db.session.commit()
    except Exception as e:
        db.session.rollback()
        return jsonify({"error": str(e)}), 500

    # Upload Template Variables & tables
    try:
        for variable in validated_payload.variable_list.data:
            variable_obj = EmailTemplateVariable(
                variable_type=variable.get("variable_type"),
                variable_name=variable.get("variable_name"),
                variable_expression=variable.get("variable_expression"),
                source_table=variable.get("source_table"),
                table_column_mapping=variable.get("table_column_mapping"),
                email_template_uid=new_template.email_template_uid,
            )
            db.session.add(variable_obj)
        db.session.commit()
    except Exception as e:
        db.session.rollback()
        return jsonify({"error": str(e)}), 500

    return (
        jsonify(
            {
                "success": True,
                "message": "Email template created successfully",
                "data": new_template.to_dict(),
            }
        ),
        201,
    )


@emails_bp.route("/template", methods=["GET"])
@logged_in_active_user_required
@validate_query_params(EmailTemplateQueryParamValidator)
@custom_permissions_required("READ Emails", "query", "email_config_uid")
def get_all_email_templates(validated_query_params):
    """
    Function to get email templates
    """
    templates = EmailTemplate.query.filter_by(
        email_config_uid=validated_query_params.email_config_uid.data
    ).all()

    template_data = []
    for template in templates:
        template_data.append(template.to_dict())

    response = jsonify(
        {
            "success": True,
            "data": template_data,
        }
    )
    return response, 200


@emails_bp.route("/template/<int:email_template_uid>", methods=["GET"])
@logged_in_active_user_required
@validate_query_params(EmailTemplateQueryParamValidator)
@custom_permissions_required("READ Emails", "query", "email_config_uid")
def get_email_template(email_template_uid, validated_query_params):
    """
    Function to get a specific email template using the template_uid
    """
    template = EmailTemplate.query.get_or_404(email_template_uid)
    response = jsonify(
        {
            "success": True,
            "data": template.to_dict(),
        }
    )
    return response, 200


@emails_bp.route("/template/<int:email_template_uid>", methods=["PUT"])
@logged_in_active_user_required
@validate_payload(EmailTemplateValidator)
@custom_permissions_required("WRITE Emails", "body", "email_config_uid")
def update_email_template(email_template_uid, validated_payload):
    """
    Function to update an email template
    """
    template = EmailTemplate.query.get_or_404(email_template_uid)
    template.email_config_uid = validated_payload.email_config_uid.data
    template.subject = validated_payload.subject.data
    template.language = validated_payload.language.data
    template.content = validated_payload.content.data

    try:
        db.session.commit()
    except Exception as e:
        db.session.rollback()
        return jsonify({"error": str(e)}), 500

    # Upload Template Variables & tables
    try:
        for variable in validated_payload.variable_list.data:
            variable_obj = EmailTemplateVariable(
                variable_type=variable.get("variable_type"),
                variable_name=variable.get("variable_name"),
                variable_expression=variable.get("variable_expression"),
                source_table=variable.get("source_table"),
                table_column_mapping=variable.get("table_column_mapping"),
                email_template_uid=template.email_template_uid,
            )
            db.session.add(variable_obj)
        db.session.commit()
    except Exception as e:
        db.session.rollback()
        return jsonify({"error": str(e)}), 500

    response = jsonify(
        {
            "success": True,
            "message": "Email template updated successfully",
            "data": template.to_dict(),
        }
    )
    return response, 200


@emails_bp.route("/template/<int:email_template_uid>", methods=["DELETE"])
@logged_in_active_user_required
@validate_query_params(EmailTemplateQueryParamValidator)
@custom_permissions_required("WRITE Emails", "query", "email_config_uid")
def delete_email_template(email_template_uid, validated_query_params):
    """
    Function to delete an email template
    """
    template = EmailTemplate.query.get_or_404(email_template_uid)
    try:
        db.session.delete(template)
        db.session.commit()
    except Exception as e:
        db.session.rollback()
        return jsonify({"error": str(e)}), 500

    return (
        jsonify({"success": True, "message": "Email template deleted successfully"}),
        200,
    )


@emails_bp.route("/gsheet", methods=["GET"])
@logged_in_active_user_required
@validate_payload(EmailGsheetSourceParamValidator)
@custom_permissions_required("READ Emails", "body", "form_uid")
def fetch_google_sheet_headers(validated_payload):
    """
    Function to fetch headers from a Google Sheet
    """

    email_source_gsheet_link = validated_payload.email_source_gsheet_link.data
    email_source_gsheet_tab = validated_payload.email_source_gsheet_tab.data
    email_source_gsheet_header_row = (
        validated_payload.email_source_gsheet_header_row.data
    )
    google_service_account_credentials = load_google_service_account_credentials()

    # Initialize the GoogleSheetUtils class to read the headers
    try:
        headers = google_sheet_helpers(
            google_service_account_credentials=google_service_account_credentials,
            google_sheet_url=email_source_gsheet_link,
            google_sheet_tab=email_source_gsheet_tab,
            header_index=email_source_gsheet_header_row,
        ).read_sheet_headers()
    except Exception as e:
        if len(e.args) > 0 and type(e.args[0]) == dict and "code" in e.args[0]:
            if e.args[0]["code"] == 404:
                return (
                    jsonify(
                        {
                            "error": "Google Sheet not found, kindly check sheet link and tab name"
                        }
                    ),
                    404,
                )
            elif e.args[0]["code"] == 403:
                return (
                    jsonify(
                        {
                            "error": "Google Sheet access forbidden, kindly check sheet permissions"
                        }
                    ),
                    403,
                )
            else:
                return jsonify({"error": str(e)}), e.args[0]["code"]
        else:
            return jsonify({"error": str(e)}), 500

    response = jsonify(
        {
            "success": True,
            "message": "Google Sheet column Headers retrieved successfully",
            "data": headers,
        }
    )
    return response, 200


@emails_bp.route("/gsheet", methods=["PATCH"])
@logged_in_active_user_required
@validate_payload(EmailGsheetSourcePatchParamValidator)
@custom_permissions_required("WRITE Emails", "body", "email_config_uid")
def update_google_sheet_headers(validated_payload):
    """
    Function to update headers from a Google Sheet for a config
    """

    email_config = EmailConfig.query.filter_by(
        email_config_uid=validated_payload.email_config_uid.data
    ).first()
    google_service_account_credentials = load_google_service_account_credentials()

    # Initialize the GoogleSheetUtils class to read the headers
    try:
        headers = google_sheet_helpers(
            google_service_account_credentials=google_service_account_credentials,
            google_sheet_url=email_config.email_source_gsheet_link,
            google_sheet_tab=email_config.email_source_gsheet_tab,
            header_index=email_config.email_source_gsheet_header_row,
        ).read_sheet_headers()
    except Exception as e:
        if len(e.args) > 0 and type(e.args[0]) == dict and "code" in e.args[0]:
            if e.args[0]["code"] == 404:
                return (
                    jsonify(
                        {
                            "error": "Google Sheet not found, kindly check sheet link and tab name"
                        }
                    ),
                    404,
                )
            elif e.args[0]["code"] == 403:
                return (
                    jsonify(
                        {
                            "error": "Google Sheet access forbidden, kindly check sheet permissions"
                        }
                    ),
                    403,
                )
            else:
                return jsonify({"error": str(e)}), e.args[0]["code"]
        else:
            return jsonify({"error": str(e)}), 500

    # Update the email source columns in db
    email_config.email_source_columns = headers
    try:
        db.session.commit()
    except Exception as e:
        db.session.rollback()
        return jsonify({"error": str(e)}), 500

    response = jsonify(
        {
            "success": True,
            "message": "Email Source Columns updated successfully",
            "data": headers,
        }
    )
    return response, 200
