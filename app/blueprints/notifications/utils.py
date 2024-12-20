from app.blueprints.enumerators.models import Enumerator
from app.blueprints.locations.models import Location
from app.blueprints.module_questionnaire.models import ModuleQuestionnaire
from app.blueprints.targets.models import Target, TargetConfig


def check_notification_conditions(
    action_module_id, notification_module_id, survey_uid, form_uid
):
    """
    Check if the notification conditions are met.

    Args:
        action_module_id (int): Module ID which created the action.
        notification_module_id (int): Module ID for which we need to create a notification.
        survey_uid (str): Unique identifier for the survey.
        form_uid (str): Unique identifier for the form.

    Returns:
        bool: True if conditions are met, False otherwise.
    """

    # Base condition
    # Default condition to check for a module before raising any notification for it
    base_condition = True

    # Additional condition
    # Additional condition to check for inter-module dependencies before raising any notification
    additional_condition = True

    # Locations Module
    if notification_module_id == 5:
        # Check if the survey has locations data
        base_condition = (
            Location.query.filter_by(survey_uid=survey_uid).first() is not None
        )

    # Enumerator Module
    elif notification_module_id == 7:
        # Check if the survey has enumerator data
        base_condition = (
            Enumerator.query.filter_by(form_uid=form_uid).first() is not None
        )

    # Target Module
    elif notification_module_id == 8:
        # Check if the survey has target data
        # Check if the target source is set as csv for the survey
        base_condition = (
            Target.query.filter_by(form_uid=form_uid).first() is not None
            and TargetConfig.query.filter_by(
                form_uid=form_uid, target_source="csv"
            ).first()
            is not None
        )

    # Additional conditions for Locations Module
    if action_module_id == 5:
        # Enumerator Module
        if notification_module_id == 7:
            # Check if surveyor mapping criteria includes location for the survey
            additional_condition = (
                ModuleQuestionnaire.query.filter(
                    ModuleQuestionnaire.survey_uid == survey_uid,
                    ModuleQuestionnaire.surveyor_mapping_criteria.any("Location"),
                ).first()
                is not None
            )

        # Target Module
        elif notification_module_id == 8:
            # Check if target mapping criteria includes location for the survey
            additional_condition = (
                ModuleQuestionnaire.query.filter(
                    ModuleQuestionnaire.survey_uid == survey_uid,
                    ModuleQuestionnaire.target_mapping_criteria.any("Location"),
                ).first()
                is not None
            )

    return base_condition and additional_condition
