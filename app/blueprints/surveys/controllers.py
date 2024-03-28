from flask import jsonify, request
from sqlalchemy.exc import IntegrityError
from flask_login import current_user
from app import db
from .models import Survey
from app.blueprints.roles.models import Role, SurveyAdmin
from app.blueprints.locations.models import GeoLevel
from app.blueprints.module_selection.models import ModuleStatus, Module
from .routes import surveys_bp
from .validators import (
    CreateSurveyValidator,
    UpdateSurveyValidator,
)
from app.utils.utils import (
    custom_permissions_required,
    logged_in_active_user_required,
    validate_payload,
)


@surveys_bp.route("", methods=["GET"])
@logged_in_active_user_required
def get_all_surveys():
    if current_user.get_is_super_admin():
        # Return all surveys for the super admin users
        surveys = Survey.query.all()
    else:
        survey_admin_check = SurveyAdmin.query.filter_by(
            user_uid=current_user.user_uid
        ).all()
        user_roles = current_user.get_roles()

        if survey_admin_check and user_roles:
            # Get surveys where the user is a survey admin or associated with user's roles
            survey_uids_admin = {entry.survey_uid for entry in survey_admin_check}
            surveys_with_roles = (
                Survey.query.join(Role, Survey.survey_uid == Role.survey_uid)
                .filter(
                    (Role.role_uid.in_(user_roles))
                    | (Survey.survey_uid.in_(survey_uids_admin))
                )
                .distinct()
                .all()
            )
            surveys = surveys_with_roles
        elif survey_admin_check:
            # Get surveys where the user is a survey admin
            survey_uids_admin = {entry.survey_uid for entry in survey_admin_check}
            surveys = Survey.query.filter(
                Survey.survey_uid.in_(survey_uids_admin)
            ).all()
        elif user_roles:
            # Get surveys associated with the user's roles
            surveys_with_roles = (
                Survey.query.join(Role, Survey.survey_uid == Role.survey_uid)
                .filter(Role.role_uid.in_(user_roles))
                .distinct()
                .all()
            )
            surveys = surveys_with_roles
        else:
            # No surveys for the user
            surveys = []

    data = [survey.to_dict() for survey in surveys]
    response = {"success": True, "data": data}

    return jsonify(response), 200


@surveys_bp.route("", methods=["POST"])
@logged_in_active_user_required
@validate_payload(CreateSurveyValidator)
@custom_permissions_required("CREATE SURVEY")
def create_survey(validated_payload):
    survey = Survey(
        survey_id=validated_payload.survey_id.data,
        survey_name=validated_payload.survey_name.data,
        project_name=validated_payload.project_name.data,
        survey_description=validated_payload.survey_description.data,
        surveying_method=validated_payload.surveying_method.data,
        planned_start_date=validated_payload.planned_start_date.data,
        planned_end_date=validated_payload.planned_end_date.data,
        irb_approval=validated_payload.irb_approval.data,
        config_status=validated_payload.config_status.data,
        state=validated_payload.state.data,
        prime_geo_level_uid=validated_payload.prime_geo_level_uid.data,
        created_by_user_uid=current_user.user_uid,
    )
    try:
        db.session.add(survey)
        db.session.commit()

        # Add the current user as a survey admin for the newly created survey
        survey_admin_entry = SurveyAdmin(
            survey_uid=survey.survey_uid, user_uid=current_user.user_uid
        )
        db.session.add(survey_admin_entry)
        db.session.commit()
        # Also populate Module Status table with default values
        module_list = Module.query.filter_by(optional=False).all()
        for module in module_list:
            default_config_status = ModuleStatus(
                survey_uid=survey.survey_uid,
                module_id=module.module_id,
                config_status=(
                    "In Progress"
                    if module.name == "Basic information"
                    else "Not Started"
                ),
            )
            db.session.add(default_config_status)

        db.session.commit()
    except IntegrityError:
        db.session.rollback()
        return jsonify({"error": "survey_id already exists"}), 400
    return (
        jsonify(
            {
                "success": True,
                "data": {"message": "success", "survey": survey.to_dict()},
            }
        ),
        201,
    )


@surveys_bp.route("/<int:survey_uid>/config-status", methods=["GET"])
@logged_in_active_user_required
def get_survey_config_status(survey_uid):
    """
    Get the configuration status for each module for a given survey
    """
    # Check if survey exists and throw error if not
    survey = Survey.query.filter_by(survey_uid=survey_uid).first()
    if survey is None:
        return jsonify({"error": "Survey not found"}), 404

    config_status = (
        db.session.query(
            Module.module_id,
            Module.name,
            ModuleStatus.config_status,
            Module.optional,
            Survey.config_status.label("overall_status"),
        )
        .join(
            Module,
            ModuleStatus.module_id == Module.module_id,
        )
        .join(
            Survey,
            ModuleStatus.survey_uid == Survey.survey_uid,
        )
        .filter(ModuleStatus.survey_uid == survey_uid)
        .all()
    )

    data = {}
    optional_module_flag = False
    for status in config_status:
        data["overall_status"] = status["overall_status"]
        if status.optional is False:
            if status.name in ["Basic information", "Module selection"]:
                data[status.name] = {"status": status.config_status}
            else:
                if "Survey information" not in list(data.keys()):
                    data["Survey information"] = []
                data["Survey information"].append(
                    {"name": status.name, "status": status.config_status}
                )
        else:
            optional_module_flag = True
            if "Module configuration" not in list(data.keys()):
                data["Module configuration"] = []
            data["Module configuration"].append(
                {
                    "module_id": status.module_id,
                    "name": status.name,
                    "status": status.config_status,
                }
            )

    # Temp: Update module status based on whether data is present in the corresponding backend
    # table because we aren't updating the module status table from each module currently
    from app.blueprints.forms.models import ParentForm
    from app.blueprints.enumerators.models import Enumerator
    from app.blueprints.targets.models import Target
    from app.blueprints.assignments.models import SurveyorAssignment

    survey = Survey.query.filter_by(survey_uid=survey_uid).first()
    scto_information = ParentForm.query.filter_by(survey_uid=survey_uid).first()
    roles = Role.query.filter_by(survey_uid=survey_uid).first()
    locations = GeoLevel.query.filter_by(survey_uid=survey_uid).first()

    enumerators = None
    targets = None
    assignments = None

    if scto_information is not None:
        enumerators = Enumerator.query.filter_by(
            form_uid=scto_information.form_uid
        ).first()
        targets = Target.query.filter_by(form_uid=scto_information.form_uid).first()

    if enumerators and targets:
        assignments = (
            db.session.query(
                SurveyorAssignment,
            )
            .join(
                Enumerator,
                Enumerator.enumerator_uid == SurveyorAssignment.enumerator_uid,
            )
            .join(Target, Target.target_uid == SurveyorAssignment.target_uid)
            .filter(Target.form_uid == scto_information.form_uid)
            .first()
        )

    if survey is not None:
        data["Basic information"]["status"] = "In Progress"
    if optional_module_flag:
        data["Module selection"]["status"] = "In Progress"

    for item in data["Survey information"]:
        if item["name"] == "SurveyCTO information":
            if scto_information is not None:
                item["status"] = "In Progress"
        elif item["name"] == "Field supervisor roles":
            if roles is not None:
                item["name"] = "User and role management"
                item["status"] = "In Progress"
        elif item["name"] == "Survey locations":
            if locations is not None:
                item["status"] = "In Progress"
        elif item["name"] == "Enumerators":
            if enumerators is not None:
                item["status"] = "In Progress"
        elif item["name"] == "Targets":
            if targets is not None:
                item["status"] = "In Progress"
    if "Module configuration" in data:
        for item in data["Module configuration"]:
            if (
                isinstance(item, dict)
                and "name" in item
                and item["name"] == "Assignments"
            ):
                if assignments is not None:
                    item["status"] = "In Progress"

    response = {"success": True, "data": data}
    return jsonify(response), 200


@surveys_bp.route("/<int:survey_uid>/basic-information", methods=["GET"])
@logged_in_active_user_required
def get_survey(survey_uid):
    survey = Survey.query.filter_by(survey_uid=survey_uid).first()
    if survey is None:
        return jsonify({"error": "Survey not found"}), 404
    return jsonify(survey.to_dict())


@surveys_bp.route("/<int:survey_uid>/basic-information", methods=["PUT"])
@logged_in_active_user_required
@validate_payload(UpdateSurveyValidator)
@custom_permissions_required("ADMIN", "path", "survey_uid")
def update_survey(survey_uid, validated_payload):
    if Survey.query.filter_by(survey_uid=survey_uid).first() is None:
        return jsonify({"error": "Survey not found"}), 404

    Survey.query.filter_by(survey_uid=survey_uid).update(
        {
            Survey.survey_uid: survey_uid,
            Survey.survey_id: validated_payload.survey_id.data,
            Survey.survey_name: validated_payload.survey_name.data,
            Survey.survey_description: validated_payload.survey_description.data,
            Survey.project_name: validated_payload.project_name.data,
            Survey.surveying_method: validated_payload.surveying_method.data,
            Survey.irb_approval: validated_payload.irb_approval.data,
            Survey.planned_start_date: validated_payload.planned_start_date.data,
            Survey.planned_end_date: validated_payload.planned_end_date.data,
            Survey.state: validated_payload.state.data,
            Survey.prime_geo_level_uid: validated_payload.prime_geo_level_uid.data,
            Survey.config_status: validated_payload.config_status.data,
        },
        synchronize_session="fetch",
    )
    db.session.commit()
    survey = Survey.query.filter_by(survey_uid=survey_uid).first()
    return jsonify(survey.to_dict()), 200


@surveys_bp.route("/<int:survey_uid>", methods=["DELETE"])
@logged_in_active_user_required
@custom_permissions_required("ADMIN", "path", "survey_uid")
def delete_survey(survey_uid):
    survey = Survey.query.filter_by(survey_uid=survey_uid).first()
    if survey is None:
        return jsonify({"error": "Survey not found"}), 404

    ModuleStatus.query.filter(ModuleStatus.survey_uid == survey_uid).delete()
    db.session.delete(survey)

    db.session.commit()
    return "", 204
