from flask import jsonify

from app.blueprints.enumerators.models import EnumeratorColumnConfig
from app.blueprints.forms.models import Form
from app.blueprints.locations.errors import InvalidGeoLevelHierarchyError
from app.blueprints.locations.models import GeoLevel
from app.blueprints.locations.utils import GeoLevelHierarchy
from app.blueprints.surveys.models import Survey
from app.blueprints.targets.models import TargetColumnConfig


def get_default_email_assignments_column(survey_uid):
    """
    Create a list of columns for the default Assignments email table.

    Args:
        survey_uid: Survey UID

    Returns:
        list: List of columns
    """

    default_column_list = []

    form = Form.query.filter_by(survey_uid=survey_uid, form_type="parent").first()
    form_uid = form.form_uid

    enumerator_location_configured = False
    target_location_configured = False

    result = TargetColumnConfig.query.filter(
        TargetColumnConfig.form_uid == form_uid,
        TargetColumnConfig.column_type == "location",
    ).first()

    if result is not None:
        target_location_configured = True

    result = EnumeratorColumnConfig.query.filter(
        EnumeratorColumnConfig.form_uid == form_uid,
        EnumeratorColumnConfig.column_type == "location",
    ).first()

    if result is not None:
        enumerator_location_configured = True

    geo_level_hierarchy = None
    prime_geo_level_uid = None

    if enumerator_location_configured or target_location_configured:
        # Get the geo levels for the survey
        geo_levels = GeoLevel.query.filter_by(survey_uid=survey_uid).all()

        try:
            geo_level_hierarchy = GeoLevelHierarchy(geo_levels)
        except InvalidGeoLevelHierarchyError as e:
            return (
                jsonify(
                    {
                        "success": False,
                        "errors": {
                            "geo_level_hierarchy": e.geo_level_hierarchy_errors,
                        },
                    }
                ),
                422,
            )

    if enumerator_location_configured:
        prime_geo_level_uid = (
            Survey.query.filter_by(survey_uid=survey_uid).first().prime_geo_level_uid
        )

        if prime_geo_level_uid is None:
            return (
                jsonify(
                    {
                        "success": False,
                        "errors": "The prime_geo_level_uid is not configured for this survey but is found as a column in the enumerator_column_config table.",
                    }
                ),
                422,
            )

        if prime_geo_level_uid not in [
            geo_level.geo_level_uid
            for geo_level in geo_level_hierarchy.ordered_geo_levels
        ]:
            return (
                jsonify(
                    {
                        "success": False,
                        "errors": f"The prime_geo_level_uid '{prime_geo_level_uid}' is not in the location type hierarchy for this survey.",
                    }
                ),
                422,
            )
    location_column_list = []
    if target_location_configured:
        for i, geo_level in enumerate(geo_level_hierarchy.ordered_geo_levels):
            location_column_list.append(
                {
                    "column_description": f"Locations : {geo_level.geo_level_name}_id",
                    "column_name": f"{geo_level.geo_level_name} ID",
                }
            )
            location_column_list.append(
                {
                    "column_description": f"Locations : {geo_level.geo_level_name}_name",
                    "column_name": f"{geo_level.geo_level_name} Name",
                }
            )

    result = TargetColumnConfig.query.filter(
        TargetColumnConfig.form_uid == form_uid,
        TargetColumnConfig.column_type == "custom_fields",
    ).all()

    target_custom_fields = []
    for row in result:
        target_custom_fields.append(
            {
                "column_description": f"Targets: custom_fields['{row.column_name}']",
                "column_name": row.column_name,
            }
        )

    result = EnumeratorColumnConfig.query.filter(
        EnumeratorColumnConfig.form_uid == form_uid,
        EnumeratorColumnConfig.column_type == "custom_fields",
    ).all()

    enumerator_custom_fields = []
    for row in result:
        enumerator_custom_fields.append(
            {
                "column_description": f"Enumerators: custom_fields['{row.column_name}']",
                "column_name": row.column_name,
            }
        )
    default_column_list = (
        [
            {
                "column_description": "Enumerators : name",
                "column_name": "Surveyor Name",
            },
            {
                "column_description": "Enumerators : enumerator_id",
                "column_name": "Surveyor ID",
            },
            {
                "column_description": "Enumerators : home_address",
                "column_name": "Surveyor Address",
            },
            {
                "column_description": "Enumerators : gender",
                "column_name": "Surveyor Gender",
            },
            {
                "column_description": "Enumerators : language",
                "column_name": "Surveyor Language",
            },
            {
                "column_description": "Enumerators : email",
                "column_name": "Surveyor Email",
            },
            {
                "column_description": "Enumerators : mobile_primary",
                "column_name": "Surveyor Mobile",
            },
            {
                "column_description": "Targets: target_id",
                "column_name": "Target ID",
            },
            {
                "column_description": "Targets: gender",
                "column_name": "Gender",
            },
            {
                "column_description": "Targets: language",
                "column_name": "Language",
            },
            {
                "column_description": "Target_Status: final_survey_status_label",
                "column_name": "Final Survey Status",
            },
            {
                "column_description": "Target_Status: final_survey_status",
                "column_name": "Final Survey Status Code",
            },
            {
                "column_description": "Target_Status: revisit_sections",
                "column_name": "Revisit Sections",
            },
            {
                "column_description": "Target_Status: num_attempts",
                "column_name": "Total Attempts",
            },
            {
                "column_description": "Target_Status: refusal_flag",
                "column_name": "Refused",
            },
            {
                "column_description": "Target_Status: completed_flag",
                "column_name": "Completed",
            },
        ]
        + location_column_list
        + target_custom_fields
        + enumerator_custom_fields
    )

    return default_column_list


def get_default_email_variable_names(form_uid):
    """
    Get the default email variable names for the given form_uid.

    Args:
        form_uid: form_uid of the SCTO Form

    Returns:
        List of columns
    """

    default_column_list = [
        "Surveyor Name",
        "Surveyor ID",
        "Surveyor Language",
        "Surveyor Gender",
        "Assignment Date",
        "Surveyor Email",
    ]

    location_column_list = []
    enumerator_custom_fields = []

    form = Form.query.filter_by(form_uid=form_uid).first()
    survey_uid = form.survey_uid

    result = EnumeratorColumnConfig.query.filter(
        EnumeratorColumnConfig.form_uid == form_uid,
        EnumeratorColumnConfig.column_type == "custom_fields",
    ).all()
    for row in result:
        enumerator_custom_fields.append(f"Surveyor: {row.column_name}")

    # For locations we will generate all location hierarchies above or equal to prime geo level
    # Check if geo level configured for the form
    result = EnumeratorColumnConfig.query.filter(
        EnumeratorColumnConfig.form_uid == form_uid,
        EnumeratorColumnConfig.column_type == "location",
    ).first()

    if result is not None:
        geo_level_hierarchy = None
        prime_geo_level_uid = None
        # Get the geo levels for the survey
        geo_levels = GeoLevel.query.filter_by(survey_uid=survey_uid).all()

        try:
            geo_level_hierarchy = GeoLevelHierarchy(geo_levels)
        except InvalidGeoLevelHierarchyError as e:
            return (
                jsonify(
                    {
                        "success": False,
                        "errors": {
                            "geo_level_hierarchy": e.geo_level_hierarchy_errors,
                        },
                    }
                ),
                422,
            )

        prime_geo_level_uid = (
            Survey.query.filter_by(survey_uid=survey_uid).first().prime_geo_level_uid
        )

        if prime_geo_level_uid is None:
            return (
                jsonify(
                    {
                        "success": False,
                        "errors": "The prime_geo_level_uid is not configured for this survey but is found as a column in the enumerator_column_config table.",
                    }
                ),
                422,
            )

        if prime_geo_level_uid not in [
            geo_level.geo_level_uid
            for geo_level in geo_level_hierarchy.ordered_geo_levels
        ]:
            return (
                jsonify(
                    {
                        "success": False,
                        "errors": f"The prime_geo_level_uid '{prime_geo_level_uid}' is not in the location type hierarchy for this survey.",
                    }
                ),
                422,
            )
        for i, geo_level in enumerate(geo_level_hierarchy.ordered_geo_levels):
            location_column_list.append(f"Locations : {geo_level.geo_level_name}_id")
            location_column_list.append(f"Locations : {geo_level.geo_level_name}_name")
            if geo_level.geo_level_uid == prime_geo_level_uid:
                break

    return default_column_list + location_column_list + enumerator_custom_fields
