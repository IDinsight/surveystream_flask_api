from . import table_config_bp
from app.utils.utils import logged_in_active_user_required
from flask import jsonify, request
from flask_login import current_user
from .models import TableConfig
from .validators import UpdateTableConfigValidator
from .default_config import DefaultTableConfig
from .utils import validate_table_config
from .errors import InvalidTableConfigError
from app.blueprints.locations.models import GeoLevel
from app.blueprints.locations.utils import GeoLevelHierarchy
from app.blueprints.locations.errors import InvalidGeoLevelHierarchyError
from app.blueprints.forms.models import ParentForm
from app.blueprints.surveys.models import Survey
from app.blueprints.enumerators.models import EnumeratorColumnConfig
from app.blueprints.targets.models import TargetColumnConfig
from app import db


@table_config_bp.route("", methods=["GET"])
@logged_in_active_user_required
def get_table_config():
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
                row.column_key.split(".")[0] == "supervisors"
                and int(row.column_key.split(".")[1].split("_")[1]) <= user_level
            ):
                is_excluded_supervisor = True

        except:
            pass

        return is_excluded_supervisor

    user_uid = current_user.user_uid
    form_uid = request.args.get("form_uid")

    # Get the survey UID from the form UID
    form = ParentForm.query.filter_by(form_uid=form_uid).first()

    if form is None:
        return (
            jsonify(message=f"The form 'form_uid={form_uid}' could not be found."),
            404,
        )

    survey_uid = form.survey_uid

    # survey_query = build_survey_query(form_uid)
    # user_level = build_user_level_query(user_uid, survey_query).first().level # TODO: Add this back in once we have the supervisor hierarchy in place

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
                )
            table_config[key] = getattr(default_table_config, key)

        else:
            for row in table_result:
                # TODO: Add this back in once we have the supervisor hierarchy in place
                # if is_excluded_supervisor(row, user_level):
                #     pass
                # else:

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
def update_table_config():
    """
    Updates the table definition for the specified assignments module table
    """

    form = UpdateTableConfigValidator.from_json(request.get_json())

    if not form.validate():
        return jsonify(message=form.errors), 422

    user_uid = current_user.user_uid
    form_uid = form.form_uid.data
    table_name = form.table_name.data
    table_config = form.table_config.data

    # Get the survey UID from the form UID
    form = ParentForm.query.filter_by(form_uid=form_uid).first()

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

    # Validate the table config
    try:
        validate_table_config(
            table_config,
            table_name,
            geo_level_hierarchy,
            prime_geo_level_uid,
            enumerator_location_configured,
            target_location_configured,
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
