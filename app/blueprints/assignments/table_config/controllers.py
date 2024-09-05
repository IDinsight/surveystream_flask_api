from flask import jsonify
from flask_login import current_user

from app import db
from app.blueprints.enumerators.models import EnumeratorColumnConfig
from app.blueprints.forms.models import Form
from app.blueprints.locations.errors import InvalidGeoLevelHierarchyError
from app.blueprints.locations.models import GeoLevel
from app.blueprints.locations.utils import GeoLevelHierarchy
from app.blueprints.roles.errors import InvalidRoleHierarchyError
from app.blueprints.roles.models import Role
from app.blueprints.roles.utils import (
    RoleHierarchy,
    check_if_survey_admin,
    get_user_role,
)
from app.blueprints.surveys.models import Survey
from app.blueprints.targets.models import TargetColumnConfig
from app.utils.utils import (
    custom_permissions_required,
    logged_in_active_user_required,
    validate_payload,
    validate_query_params,
)

from . import table_config_bp
from .available_columns import AvailableColumns
from .default_config import DefaultTableConfig
from .errors import InvalidTableConfigError
from .models import TableConfig
from .utils import validate_table_config
from .validators import TableConfigQueryParamValidator, UpdateTableConfigValidator


@table_config_bp.route("", methods=["GET"])
@logged_in_active_user_required
@validate_query_params(TableConfigQueryParamValidator)
@custom_permissions_required("READ Assignments", "query", "form_uid")
def get_table_config(validated_query_params):
    """
    Returns the table definitions for the assignments module tables
    """

    def is_excluded_supervisor(row, user_level):
        """
        Check if the table config row should be excluded because the supervisor is not at a child supervisor level for the logged in user
        """
        is_excluded_supervisor = False
        try:
            if (
                row.column_key.split("[")[0] == "supervisors"
                and int(row.column_key.split("[")[1].split("]")[0]) <= user_level
            ):
                is_excluded_supervisor = True

        except:
            pass

        return is_excluded_supervisor

    user_uid = current_user.user_uid
    form_uid = validated_query_params.form_uid.data
    filter_supervisors = validated_query_params.filter_supervisors.data

    # Get the survey UID from the form UID
    form = Form.query.filter_by(form_uid=form_uid).first()

    if form is None:
        return (
            jsonify(message=f"The form 'form_uid={form_uid}' could not be found."),
            404,
        )

    survey_uid = form.survey_uid

    # Figure out if we need to handle location columns
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

    role_hierarchy = None
    roles = [
        role.to_dict() for role in Role.query.filter_by(survey_uid=survey_uid).all()
    ]
    if len(roles) > 0:
        try:
            role_hierarchy = RoleHierarchy(roles)
        except InvalidRoleHierarchyError as e:
            return (
                jsonify(
                    {
                        "success": False,
                        "errors": {
                            "role_hierarchy": e.role_hierarchy_errors,
                        },
                    }
                ),
                422,
            )

    user_level = None
    # If filter_supervisors flag is True, fetch logged in user's role to
    # filter out supervisors columns to only return the child supervisors
    if filter_supervisors:
        is_survey_admin = check_if_survey_admin(user_uid, survey_uid)
        if is_survey_admin:
            user_level = None
        else:
            user_role = get_user_role(user_uid, survey_uid)
            for i, role in enumerate(role_hierarchy.ordered_roles):
                if role["role_uid"] == user_role:
                    user_level = i
                    break

    table_config = {
        "surveyors": [],
        "targets": [],
        "assignments_main": [],
        "assignments_surveyors": [],
        "assignments_review": [],
    }

    default_table_config = None

    for key in table_config.keys():
        table_result = (
            TableConfig.query.filter(
                TableConfig.table_name == key, TableConfig.form_uid == form_uid
            )
            .order_by(TableConfig.column_order)
            .all()
        )
        if table_result is None or len(table_result) == 0:
            if default_table_config is None:
                default_table_config = DefaultTableConfig(
                    form_uid,
                    survey_uid,
                    geo_level_hierarchy,
                    prime_geo_level_uid,
                    enumerator_location_configured,
                    target_location_configured,
                    role_hierarchy,
                    filter_supervisors,
                    user_level,
                )
            table_config[key] = getattr(default_table_config, key)
        else:
            for row in table_result:
                # If filter_supervisors flag is True, skip the excluded supervisors columns
                if filter_supervisors and (user_level is not None):
                    if is_excluded_supervisor(row, user_level):
                        continue

                if row.group_label is None:
                    table_config[row.table_name].append(
                        {
                            "group_label": None,
                            "columns": [
                                {
                                    "column_key": row.column_key,
                                    "column_label": row.column_label,
                                }
                            ],
                        }
                    )

                else:
                    # Find the index of the given group in our results
                    group_index = next(
                        (
                            i
                            for i, item in enumerate(table_config[row.table_name])
                            if item["group_label"] == row.group_label
                        ),
                        None,
                    )

                    if group_index is None:
                        table_config[row.table_name].append(
                            {"group_label": row.group_label, "columns": []}
                        )
                        group_index = -1

                    table_config[row.table_name][group_index]["columns"].append(
                        {
                            "column_key": row.column_key,
                            "column_label": row.column_label,
                        }
                    )

    return jsonify(table_config)


# Create a PUT route to update the table config
@table_config_bp.route("", methods=["PUT"])
@logged_in_active_user_required
@validate_payload(UpdateTableConfigValidator)
@custom_permissions_required("WRITE Assignments", "body", "form_uid")
def update_table_config(validated_payload):
    """
    Updates the table definition for the specified assignments module table
    """

    user_uid = current_user.user_uid
    form_uid = validated_payload.form_uid.data
    table_name = validated_payload.table_name.data
    table_config = validated_payload.table_config.data

    # Get the survey UID from the form UID
    form = Form.query.filter_by(form_uid=form_uid).first()

    if form is None:
        return (
            jsonify(message=f"The form 'form_uid={form_uid}' could not be found."),
            404,
        )

    survey_uid = form.survey_uid

    # Figure out if we need to handle location columns

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
                        "errors": f"The prime_geo_level_uid '{prime_geo_level_uid}' is not in the geo level hierarchy for this survey.",
                    }
                ),
                422,
            )

    role_hierarchy = None
    roles = [
        role.to_dict() for role in Role.query.filter_by(survey_uid=survey_uid).all()
    ]
    if len(roles) > 0:
        try:
            role_hierarchy = RoleHierarchy(roles)
        except InvalidRoleHierarchyError as e:
            return (
                jsonify(
                    {
                        "success": False,
                        "errors": {
                            "role_hierarchy": e.role_hierarchy_errors,
                        },
                    }
                ),
                422,
            )

    # Validate the table config
    try:
        validate_table_config(
            table_config,
            table_name,
            geo_level_hierarchy,
            prime_geo_level_uid,
            enumerator_location_configured,
            target_location_configured,
            role_hierarchy,
            survey_uid,
            form_uid,
        )
    except InvalidTableConfigError as e:
        return (
            jsonify(success=False, errors=e.invalid_column_errors),
            422,
        )

    # Delete the existing table config for the given form and table name
    TableConfig.query.filter(
        TableConfig.form_uid == form_uid, TableConfig.table_name == table_name
    ).delete()

    # Add the new table config
    for i, column in enumerate(table_config):
        table_config_row = TableConfig(
            form_uid=form_uid,
            table_name=table_name,
            group_label=column["group_label"],
            column_key=column["column_key"],
            column_label=column["column_label"],
            column_order=i + 1,
        )
        db.session.add(table_config_row)

    try:
        db.session.commit()
    except Exception as e:
        db.session.rollback()
        return jsonify({"success": False, "errors": str(e)}), 500

    return (
        jsonify(
            {
                "success": True,
                "message": f"Successfully updated the table config for the {table_name} table.",
            }
        ),
        200,
    )


@table_config_bp.route("/available-columns", methods=["GET"])
@logged_in_active_user_required
@validate_query_params(TableConfigQueryParamValidator)
@custom_permissions_required("READ Assignments", "query", "form_uid")
def get_available_columns(validated_query_params):
    """
    Returns the full set of available columns for the assignments module tables
    """

    form_uid = validated_query_params.form_uid.data

    # Get the survey UID from the form UID
    form = Form.query.filter_by(form_uid=form_uid).first()

    if form is None:
        return (
            jsonify(message=f"The form 'form_uid={form_uid}' could not be found."),
            404,
        )

    survey_uid = form.survey_uid

    # Figure out if we need to handle location columns
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

    roles = [
        role.to_dict() for role in Role.query.filter_by(survey_uid=survey_uid).all()
    ]
    if len(roles) > 0:
        try:
            role_hierarchy = RoleHierarchy(roles)
        except InvalidRoleHierarchyError as e:
            return (
                jsonify(
                    {
                        "success": False,
                        "errors": {
                            "role_hierarchy": e.role_hierarchy_errors,
                        },
                    }
                ),
                422,
            )

    available_columns = AvailableColumns(
        form_uid,
        survey_uid,
        geo_level_hierarchy,
        prime_geo_level_uid,
        enumerator_location_configured,
        target_location_configured,
        role_hierarchy,
    )

    return jsonify(available_columns.to_dict())
