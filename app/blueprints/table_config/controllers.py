from . import table_config_bp
from app.utils import logged_in_active_user_required
from flask import jsonify, request
from flask_login import current_user
from app import db
from app.queries.helper_queries import (
    build_survey_query,
    build_user_level_query,
)
from app.models.data_models import TableConfig


@table_config_bp.route("", methods=["GET"])
@logged_in_active_user_required
def get_table_config():
    """
    Returns the table definitions for the web app tables
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

    result = (
        db.session.query(TableConfig)
        .filter(TableConfig.form_uid == form_uid)
        .order_by(TableConfig.webapp_table_name, TableConfig.column_order)
        .all()
    )

    survey_query = build_survey_query(form_uid)
    user_level = build_user_level_query(user_uid, survey_query).first().level

    table_config = {
        "surveyors": [],
        "targets": [],
        "assignments_main": [],
        "assignments_surveyors": [],
        "assignments_review": [],
    }

    for row in result:
        if is_excluded_supervisor(row, user_level):
            pass

        else:
            if row.group_label is None:
                table_config[row.webapp_table_name].append(
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
                        for i, item in enumerate(table_config[row.webapp_table_name])
                        if item["group_label"] == row.group_label
                    ),
                    None,
                )

                if group_index is None:
                    table_config[row.webapp_table_name].append(
                        {"group_label": row.group_label, "columns": []}
                    )
                    group_index = -1

                table_config[row.webapp_table_name][group_index]["columns"].append(
                    {"column_key": row.column_key, "column_label": row.column_label}
                )

    return jsonify(table_config)
