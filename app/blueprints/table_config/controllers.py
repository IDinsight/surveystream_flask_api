from . import table_config_bp
from app.utils.utils import logged_in_active_user_required
from flask import jsonify, request
from flask_login import current_user
from .models import TableConfig
from .default_config import DefaultTableConfig
from app.blueprints.locations.models import GeoLevel
from app.blueprints.locations.utils import GeoLevelHierarchy
from app.blueprints.locations.errors import InvalidGeoLevelHierarchyError
from app.blueprints.forms.models import ParentForm
from app.blueprints.surveys.models import Survey


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
                    form_uid, geo_level_hierarchy, prime_geo_level_uid
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
