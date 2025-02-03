from flask import jsonify
from flask_login import current_user
from sqlalchemy import case
from sqlalchemy.exc import IntegrityError
from sqlalchemy.sql import func

from app import db
from app.blueprints.locations.models import GeoLevel
from app.blueprints.module_questionnaire.models import ModuleQuestionnaire
from app.blueprints.module_selection.models import (
    Module,
    ModuleDependency,
    ModuleStatus,
)
from app.blueprints.roles.models import Role, SurveyAdmin
from app.utils.utils import (
    custom_permissions_required,
    logged_in_active_user_required,
    validate_payload,
)

from .models import Survey
from .routes import surveys_bp
from .utils import ModuleStatusCalculator, is_module_optional
from .validators import (
    CreateSurveyValidator,
    UpdateSurveyStateValidator,
    UpdateSurveyValidator,
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

        # Also populate Module Status table with mandatory modules
        module_list = Module.query.filter_by(optional=False).all()
        for module in module_list:
            default_config_status = ModuleStatus(
                survey_uid=survey.survey_uid,
                module_id=module.module_id,
                config_status="Not Started",
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

    # Get dependency information for each module
    module_dependencies = (
        db.session.query(
            ModuleDependency.requires_module_id,
            func.array_agg(ModuleDependency.required_if)
            .filter(ModuleDependency.required_if != None)
            .label("required_if_conditions"),
        )
        .join(
            ModuleStatus,
            ModuleDependency.module_id == ModuleStatus.module_id,
        )
        .filter(ModuleStatus.survey_uid == survey_uid)
        .group_by(ModuleDependency.requires_module_id)
        .subquery()
    )

    config_status = (
        db.session.query(
            Module.module_id,
            Module.name,
            Module.optional,
            ModuleStatus.config_status,
            module_dependencies.c.required_if_conditions,
            Survey.config_status.label("survey_overall_status"),
            Survey.state.label("survey_state"),
        )
        .join(
            Module,
            ModuleStatus.module_id == Module.module_id,
        )
        .outerjoin(
            module_dependencies,
            ModuleStatus.module_id == module_dependencies.c.requires_module_id,
        )
        .join(
            Survey,
            ModuleStatus.survey_uid == Survey.survey_uid,
        )
        .filter(ModuleStatus.survey_uid == survey_uid)
        .all()
    )

    data = {}
    num_modules = 0
    num_completed_modules = 0
    num_optional_modules = 0  # This is not used for completion percentage calculation

    module_status_calculator = ModuleStatusCalculator(survey_uid)
    for status in config_status:
        survey_state = status.survey_state
        data["overall_status"] = status["survey_overall_status"]

        calculated_status = module_status_calculator.get_status(status.module_id)

        if status.name in ["Basic information", "Module selection"]:
            data[status.name] = {
                "status": calculated_status,
                "optional": status.optional,
            }

            num_modules += 1
            if calculated_status == "Done":
                num_completed_modules += 1

        elif status.name in [
            "SurveyCTO information",
            "Survey locations",
            "User and role management",
            "Enumerators",
            "Targets",
            "Target status mapping",
            "Mapping",
        ]:
            if "Survey information" not in list(data.keys()):
                data["Survey information"] = []

            calculated_optional_flag = is_module_optional(
                survey_uid,
                status.optional,
                status.required_if_conditions,
                calculated_status,
            )

            if calculated_optional_flag == False:
                # These modules are mandatory
                data["Survey information"].append(
                    {
                        "name": status.name,
                        "status": calculated_status,
                        "optional": False,
                    }
                )

                num_modules += 1
                if calculated_status == "Done":
                    num_completed_modules += 1

            else:
                data["Survey information"].append(
                    {
                        "name": status.name,
                        "status": calculated_status,
                        "optional": calculated_optional_flag,
                    }
                )
                num_optional_modules += 1

        else:
            if survey_state == "Active" and calculated_status in [
                "In Progress",
                "Done",
            ]:
                calculated_status = "Live"

            if "Module configuration" not in list(data.keys()):
                data["Module configuration"] = []

            optional = False  # Since this list will only have selected modules and selected modules are mandatory
            if status.name == "Assignments column configuration":
                # this module is not mandatory
                optional = True
                num_optional_modules += 1
            else:
                optional = False
                num_modules += 1
                if calculated_status in ["Done", "Live", "In Progress"]:
                    num_completed_modules += 1

            data["Module configuration"].append(
                {
                    "module_id": status.module_id,
                    "name": status.name,
                    "status": calculated_status,
                    "optional": optional,
                }
            )

    data["completion_percentage"] = (
        round(num_completed_modules / num_modules * 100, 2) if num_modules > 0 else 0
    )
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
    ModuleQuestionnaire.query.filter(
        ModuleQuestionnaire.survey_uid == survey_uid
    ).delete()
    db.session.delete(survey)

    db.session.commit()
    return "", 204


@surveys_bp.route("/<int:survey_uid>/config-status", methods=["GET"])
@logged_in_active_user_required
@validate_payload(UpdateSurveyStateValidator)
@custom_permissions_required("ADMIN", "path", "survey_uid")
def update_survey_state(survey_uid, validated_payload):
    state = validated_payload.state.data

    # Check if survey exists and throw error if not
    survey = Survey.query.filter_by(survey_uid=survey_uid).first()
    if survey is None:
        return jsonify({"error": "Survey not found"}), 404

    # Checks before updating the state to Active
    if state == "Active":
        # Get dependency information for each module
        module_dependencies = (
            db.session.query(
                ModuleDependency.requires_module_id,
                func.array_agg(ModuleDependency.required_if)
                .filter(ModuleDependency.required_if != None)
                .label("required_if_conditions"),
            )
            .join(
                ModuleStatus,
                ModuleDependency.module_id == ModuleStatus.module_id,
            )
            .filter(ModuleStatus.survey_uid == survey_uid)
            .group_by(ModuleDependency.requires_module_id)
            .subquery()
        )

        config_status = (
            db.session.query(
                Module.module_id,
                Module.name,
                Module.optional,
                ModuleStatus.config_status,
                module_dependencies.c.required_if_conditions,
            )
            .join(
                Module,
                ModuleStatus.module_id == Module.module_id,
            )
            .outerjoin(
                module_dependencies,
                ModuleStatus.module_id == module_dependencies.c.requires_module_id,
            )
            .filter(ModuleStatus.survey_uid == survey_uid)
            .all()
        )

        incomplete_modules = []
        module_status_calculator = ModuleStatusCalculator(survey_uid)
        for status in config_status:
            calculated_status = module_status_calculator.get_status(status.module_id)

            # For output modules without configurations on the webapp, we skip the check
            if status.module_id in [
                10,
                13,
                16,
            ]:  # Productivity tracker, hiring and assignment column configuration modules
                continue
            elif status.module_id == [
                9,
                11,
                12,
                15,
                18,
            ]:  # These modules have configurations on the webapp
                # We expect these modules to be in progress or done states
                if calculated_status not in ["Done", "In Progress"]:
                    incomplete_modules.append(status.name)
            else:
                # For other modules, non-optional modules should be done and optional in "Not Started"/"Done" state
                calculated_optional_flag = is_module_optional(
                    survey_uid,
                    status.optional,
                    status.required_if_conditions,
                    calculated_status,
                )
                if calculated_optional_flag == False and calculated_status != "Done":
                    incomplete_modules.append(status.name)

        if len(incomplete_modules) > 0:
            return (
                jsonify(
                    {
                        "success": False,
                        "error": "Cannot activate survey. The following modules are incomplete: "
                        + ", ".join(incomplete_modules)
                        + ". Please complete these modules before activating the survey.",
                    }
                ),
                422,
            )

    overall_config_status = (
        Survey.query.with_entities(Survey.config_status)
        .filter(Survey.survey_uid == survey_uid)
        .first()
    )
    overall_config_status = overall_config_status[0]

    # Update the overall configuration status based on the state
    if state == "Active":
        overall_config_status = "Done"
    elif state == "Draft":
        overall_config_status = "In Progress - Configuration"
    elif state == "Past":
        # Keep the overall configuration status as it is
        pass

    # Update the state of the survey
    Survey.query.filter_by(survey_uid=survey_uid).update(
        {Survey.state: state, Survey.config_status: overall_config_status},
        synchronize_session="fetch",
    )
    db.session.commit()

    return (
        jsonify({"success": True, "message": "Survey state updated successfully."}),
        200,
    )
