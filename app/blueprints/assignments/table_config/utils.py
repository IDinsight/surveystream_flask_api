import re
from app import db
from app.blueprints.targets.models import TargetColumnConfig
from app.blueprints.enumerators.models import EnumeratorColumnConfig
from app.blueprints.assignments.table_config.errors import InvalidTableConfigError
from app.blueprints.forms.models import ParentForm


def validate_table_config(
    table_config,
    table_name,
    geo_level_hierarchy,
    prime_geo_level_uid,
    enumerator_location_configured,
    target_location_configured,
    survey_uid,
):
    """
    Validates the table config
    """

    allowed_columns = {
        "assignments_main": [
            "target_uid",
            "target_id",
            "language",
            "gender",
            "custom_fields",
            "assigned_enumerator_uid",
            "assigned_enumerator_id",
            "assigned_enumerator_name",
            "assigned_enumerator_home_address",
            "assigned_enumerator_language",
            "assigned_enumerator_gender",
            "assigned_enumerator_email",
            "assigned_enumerator_mobile_primary",
            "assigned_enumerator_custom_fields",
            "completed_flag",
            "refusal_flag",
            "num_attempts",
            "last_attempt_survey_status",
            "last_attempt_survey_status_label",
            "target_assignable",
            "revisit_sections",
            "target_locations",
        ],
        "assignments_surveyors": [
            "enumerator_uid",
            "enumerator_id",
            "name",
            "email",
            "mobile_primary",
            "language",
            "home_address",
            "gender",
            "custom_fields",
            "surveyor_status",
            "surveyor_locations",
            "form_productivity",
        ],
        "assignments_review": [
            "assigned_enumerator_name",
            "prev_assigned_to",
            "target_id",
            "target_status",
        ],
        "surveyors": [
            "enumerator_uid",
            "enumerator_id",
            "name",
            "email",
            "mobile_primary",
            "language",
            "gender",
            "home_address",
            "custom_fields",
            "surveyor_status",
            "surveyor_locations",
        ],
        "targets": [
            "target_uid",
            "target_id",
            "language",
            "gender",
            "custom_fields",
            "completed_flag",
            "refusal_flag",
            "num_attempts",
            "last_attempt_survey_status",
            "last_attempt_survey_status_label",
            "target_assignable",
            "revisit_sections",
            "target_locations",
        ],
    }

    location_keys = ["target_locations", "surveyor_locations"]

    for column in table_config:
        invalid_column_errors = []

        location_key = None
        for item in location_keys:
            if column["column_key"].startswith(item):
                location_key = item

        if location_key is not None:
            if (
                location_key == "target_locations"
                and target_location_configured is False
            ):
                invalid_column_errors.append(
                    f'The column_key {column["column_key"]} is invalid. Location is not defined in the {location_key.split("_")[0]}_column_config table for this form.'
                )

            elif (
                location_key == "surveyor_locations"
                and enumerator_location_configured is False
            ):
                invalid_column_errors.append(
                    f'The column_key {column["column_key"]} is invalid. Location is not defined in the {location_key.split("_")[0]}_column_config table for this form.'
                )

            if len(invalid_column_errors) > 0:
                raise InvalidTableConfigError(invalid_column_errors)

            if location_key not in allowed_columns[table_name]:
                invalid_column_errors.append(
                    f"{location_key} is not an allowed key for the {table_name} table configuration"
                )

            if len(invalid_column_errors) > 0:
                raise InvalidTableConfigError(invalid_column_errors)

            # Check that the string is in the correct format
            if not re.match(
                rf"^{location_key}\[(\d+)\]\.(location_id|location_name)$",
                column["column_key"],
            ):
                invalid_column_errors.append(
                    f'{column["column_key"]} is not in the correct format. It should follow the pattern {location_key}[<index:int>].location_id or {location_key}[<index>].location_name>'
                )

            # Check that the location index is valid
            max_location_index = None

            if location_key == "target_locations":
                max_location_index = len(geo_level_hierarchy.ordered_geo_levels) - 1

            elif location_key == "surveyor_locations":
                for i, geo_level in enumerate(geo_level_hierarchy.ordered_geo_levels):
                    if geo_level.geo_level_uid == prime_geo_level_uid:
                        max_location_index = i

            elif (
                int(column["column_key"].split("[")[1].split("]")[0])
                > max_location_index
            ):
                if location_key == "target_locations":
                    invalid_column_errors.append(
                        f'The location index of {column["column_key"].split("[")[1].split("]")[0]} is invalid. It cannot be greater than {max_location_index} because there are {max_location_index + 1} geo levels defined for the survey.'
                    )
                elif location_key == "surveyor_locations":
                    invalid_column_errors.append(
                        f'The location index of {column["column_key"].split("[")[1].split("]")[0]} is invalid. It cannot be greater than {max_location_index} which is the index of the prime geo level defined for the survey.'
                    )

        elif column["column_key"].startswith("custom_fields"):
            if "custom_fields" not in allowed_columns[table_name]:
                invalid_column_errors.append(
                    f"custom_fields not an allowed key for the {table_name} table configuration"
                )

                raise InvalidTableConfigError(invalid_column_errors)

            # Custom fields must follow the format custom_fields['<custom_field_name>']
            if not re.match(r"^custom_fields\[\'.+\'\]$", column["column_key"]):
                invalid_column_errors.append(
                    f'{column["column_key"]} is not in the correct format. It should follow the pattern custom_fields[\'<custom_field_name>\']'
                )

                raise InvalidTableConfigError(invalid_column_errors)

            # Check that the custom field is defined in the target or enumerator column config table

            custom_field_name = column["column_key"].split("custom_fields['")[1][0:-2]

            if table_name == "assignments_main" or table_name == "targets":
                custom_field_config = (
                    TargetColumnConfig.query.filter_by(
                        custom_field_name=custom_field_name
                    )
                    .filter_by(form_id=column["form_id"])
                    .first()
                )

                if custom_field_config is None:
                    invalid_column_errors.append(
                        f"The custom field {custom_field_name} is not defined in the target_column_config table for this form."
                    )

            if table_name == "assignments_surveyors" or table_name == "surveyors":
                custom_field_config = (
                    EnumeratorColumnConfig.query.filter_by(
                        custom_field_name=custom_field_name
                    )
                    .filter_by(form_id=column["form_id"])
                    .first()
                )

                if custom_field_config is None:
                    invalid_column_errors.append(
                        f"The custom field {custom_field_name} is not defined in the enumerator_column_config table for this form."
                    )

        elif table_name == "assignments_main" and column["column_key"].startswith(
            "enumerator_custom_fields"
        ):
            if "enumerator_custom_fields" not in allowed_columns[table_name]:
                invalid_column_errors.append(
                    f"enumerator_custom_fields not an allowed key for the {table_name} table configuration"
                )

                raise InvalidTableConfigError(invalid_column_errors)

            # Custom fields must follow the format enumerator_custom_fields['<custom_field_name>']
            if not re.match(
                r"^enumerator_custom_fields\[\'.+\'\]$", column["column_key"]
            ):
                invalid_column_errors.append(
                    f'{column["column_key"]} is not in the correct format. It should follow the pattern enumerator_custom_fields[\'<custom_field_name>\']'
                )

                raise InvalidTableConfigError(invalid_column_errors)

            # Check that the custom field is defined in the target or enumerator column config table

            custom_field_name = column["column_key"].split(
                "enumerator_custom_fields['"
            )[1][0:-2]

            custom_field_config = (
                EnumeratorColumnConfig.query.filter_by(
                    custom_field_name=custom_field_name
                )
                .filter_by(form_id=column["form_id"])
                .first()
            )

            if custom_field_config is None:
                invalid_column_errors.append(
                    f"The enumerator custom field {custom_field_name} is not defined in the enumerator_column_config table for this form."
                )

        elif column["column_key"].startswith("form_productivity"):
            # Check that the string is in the correct format
            if not re.match(
                r"^form_productivity.[a-zA-z0-9_-]+.(total_assigned_target|total_completed_targets|total_pending_targets)$",
                column["column_key"],
            ):
                invalid_column_errors.append(
                    f'{column["column_key"]} is not in the correct format. It should follow the pattern form_productivity.<surveycto_form_id>.<total_assigned_target|total_completed_targets|total_pending_targets>'
                )

            # Check that the surveycto_form_id is valid
            surveycto_form_id = column["column_key"].split(".")[1].split(".")[0]
            if (
                ParentForm.query.filter(
                    ParentForm.scto_form_id == surveycto_form_id,
                    ParentForm.survey_uid == survey_uid,
                ).first()
                is None
            ):
                invalid_column_errors.append(
                    f"The surveycto_form_id {surveycto_form_id} is not found in the forms defined for this survey."
                )

        elif column["column_key"] not in allowed_columns[table_name]:
            invalid_column_errors.append(
                f"{column['column_key']} is not an allowed key for the {table_name} table configuration"
            )

    if len(invalid_column_errors) > 0:
        raise InvalidTableConfigError(invalid_column_errors)
