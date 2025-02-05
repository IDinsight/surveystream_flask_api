from app.blueprints.enumerators.models import Enumerator, SurveyorLocation
from app.blueprints.forms.models import Form
from app.blueprints.locations.models import Location
from app.blueprints.mapping.models import UserMappingConfig
from app.blueprints.media_files.models import MediaFilesConfig
from app.blueprints.module_questionnaire.models import ModuleQuestionnaire
from app.blueprints.module_selection.models import ModuleStatus
from app.blueprints.surveys.models import Survey
from app.blueprints.targets.models import Target, TargetConfig

from .models import SurveyNotification


def check_module_notification_exists(survey_uid, module_id, severity):
    """
    Check if a notification exists for a module

    Args:
        survey_uid: UID of survey
        module_id: ID of module
        severity: Severity of notification
    """
    return (
        SurveyNotification.query.filter_by(
            survey_uid=survey_uid,
            module_id=module_id,
            severity=severity,
            resolution_status="in progress",
        ).first()
        is not None
    )


def set_module_status_error(survey_uid, module_id):
    ModuleStatus.query.filter(
        ModuleStatus.module_id == module_id,
        ModuleStatus.survey_uid == survey_uid,
    ).update({"config_status": "Error"}, synchronize_session="fetch")


def check_notification_condition(survey_uid, form_uid, input_conditions):
    """
    Match notification conditions according to survey configuration and dependency conditions

    Args:
        survey_uid: UID of surveys
        form_uid: UID of form
        input_conditions: List of Notification conditions
    """
    if input_conditions is None or len(input_conditions) == 0:
        return True

    if form_uid is None:
        # TODO: Refactor this for multiple main forms
        form = Form.query.filter_by(survey_uid=survey_uid, form_type="parent").first()
        if form is not None:
            form_uid = form.form_uid

    condition_checks = {
        "location_exists": lambda: check_location_exists(survey_uid),
        "location_not_exists": lambda: not check_location_exists(survey_uid),
        "enumerator_exists": lambda: check_enumerator_exists(form_uid),
        "target_exists": lambda: check_target_exists(form_uid),
        "target_source_scto": lambda: check_target_source(form_uid, "scto"),
        "target_source_csv": lambda: check_target_source(form_uid, "csv"),
        "prime_geo_level_exists": lambda: check_prime_geo_level_exists(),
        "surveyor_location_mapping": lambda: check_surveyor_location_mapping(
            survey_uid
        ),
        "target_location_mapping": lambda: check_target_location_mapping(survey_uid),
        "form_exists": lambda: check_form_exists(form_uid),
        "target_language_not_exists": lambda: target_language_not_exists(form_uid),
        "target_gender_not_exists": lambda: target_gender_not_exists(form_uid),
        "target_location_not_exists": lambda: target_location_not_exists(form_uid),
        "enumerator_language_not_exists": lambda: enumerator_language_not_exists(
            form_uid
        ),
        "enumerator_gender_not_exists": lambda: enumerator_gender_not_exists(form_uid),
        "enumerator_location_not_exists": lambda: enumerator_location_not_exists(
            form_uid
        ),
        "mapping_exists": lambda: mapping_exists(form_uid),
        "media_config_exists": lambda: media_config_exists(form_uid),
    }

    survey_conditions = {
        condition: condition_checks[condition]()
        for condition in input_conditions
        if condition in condition_checks
    }

    return all(survey_conditions.values())


# Helper functions to check conditions


def check_location_exists(survey_uid):
    return Location.query.filter_by(survey_uid=survey_uid).first() is not None


def check_enumerator_exists(form_uid):
    return Enumerator.query.filter_by(form_uid=form_uid).first() is not None


def check_target_exists(form_uid):
    return Target.query.filter_by(form_uid=form_uid).first() is not None


def check_target_source(form_uid, source):
    return (
        TargetConfig.query.filter_by(form_uid=form_uid, target_source=source).first()
        is not None
    )


def check_prime_geo_level_exists():
    return Survey.query.filter_by().first().prime_geo_level_uid is not None


def check_surveyor_location_mapping(survey_uid):
    return (
        ModuleQuestionnaire.query.filter(
            ModuleQuestionnaire.survey_uid == survey_uid,
            ModuleQuestionnaire.surveyor_mapping_criteria.any("Location"),
        ).first()
        is not None
    )


def check_target_location_mapping(survey_uid):
    return (
        ModuleQuestionnaire.query.filter(
            ModuleQuestionnaire.survey_uid == survey_uid,
            ModuleQuestionnaire.target_mapping_criteria.any("Location"),
        ).first()
        is not None
    )


def check_form_exists(form_uid):
    return Form.query.filter_by(form_uid=form_uid).first() is not None


def target_language_not_exists(form_uid):
    return Target.query.filter_by(form_uid=form_uid, language=None).first() is not None


def target_gender_not_exists(form_uid):
    return Target.query.filter_by(form_uid=form_uid, gennder=None).first() is not None


def target_location_not_exists(form_uid):
    return (
        Target.query.filter_by(form_uid=form_uid, location_uid=None).first() is not None
    )


def enumerator_language_not_exists(form_uid):
    return (
        Enumerator.query.filter_by(form_uid=form_uid, language=None).first() is not None
    )


def enumerator_gender_not_exists(form_uid):
    return (
        Enumerator.query.filter_by(form_uid=form_uid, gender=None).first() is not None
    )


def enumerator_location_not_exists(form_uid):
    return (
        Enumerator.query.join(
            SurveyorLocation,
            Enumerator.enumerator_uid == SurveyorLocation.enumerator_uid,
            isouter=True,
        )
        .filter(Enumerator.form_uid == form_uid, SurveyorLocation.location_uid == None)
        .first()
        is not None
    )


def mapping_exists(form_uid):
    return UserMappingConfig.query.filter_by(form_uid=form_uid).first() is not None


def media_config_exists(form_uid):
    return MediaFilesConfig.query.filter_by(form_uid=form_uid).first() is not None
