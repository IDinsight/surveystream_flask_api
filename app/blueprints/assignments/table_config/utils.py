import re
from app import db
from app.blueprints.targets.models import TargetColumnConfig
from app.blueprints.enumerators.models import EnumeratorColumnConfig
from app.blueprints.assignments.table_config.errors import InvalidTableConfigError
from app.blueprints.forms.models import Form
from .available_columns import AvailableColumns


def validate_table_config(
    table_config,
    table_name,
    geo_level_hierarchy,
    prime_geo_level_uid,
    enumerator_location_configured,
    target_location_configured,
    survey_uid,
    form_uid,
):
    """
    Validates the table config
    """

    available_columns = AvailableColumns(
        form_uid,
        survey_uid,
        geo_level_hierarchy,
        prime_geo_level_uid,
        enumerator_location_configured,
        target_location_configured,
    ).to_dict()

    allowed_columns = {}

    for key, value in available_columns.items():
        allowed_columns[key] = [column["column_key"] for column in value]

    location_keys = ["target_locations", "surveyor_locations"]

    invalid_column_errors = []
    for column in table_config:

        if column["column_key"] not in allowed_columns[table_name]:

            # We know something is wrong with the column key but we want to see if we can provide a more specific error message in addition to the general one above
            location_key = None
            for item in location_keys:
                if column["column_key"].startswith(item):
                    location_key = item

            if location_key is not None:
                # Check that the string is in the correct format
                if not re.match(
                    rf"^{location_key}\[(\d+)\]\.(location_id|location_name)$",
                    column["column_key"],
                ):
                    invalid_column_errors.append(
                        f'\'{column["column_key"]}\' is not in the correct format. It should follow the pattern {location_key}[<index:int>].location_id or {location_key}[<index>].location_name>'
                    )

                # Only proceed to the rest of the location checks if the column key is formatted correctly
                else:

                    # Check if locations are configured in the enumerator/target column config
                    if (
                        location_key == "target_locations"
                        and target_location_configured is False
                    ):
                        invalid_column_errors.append(
                            f'The column_key \'{column["column_key"]}\' is invalid. Location is not defined in the {location_key.split("_")[0]}_column_config table for this form.'
                        )
                    elif (
                        location_key == "surveyor_locations"
                        and enumerator_location_configured is False
                    ):
                        invalid_column_errors.append(
                            f'The column_key \'{column["column_key"]}\' is invalid. Location is not defined in the enumerator_column_config table for this form.'
                        )

                    # Check that the location index is valid
                    max_location_index = None

                    if (
                        location_key == "target_locations"
                        and target_location_configured is True
                    ):
                        max_location_index = (
                            len(geo_level_hierarchy.ordered_geo_levels) - 1
                        )

                        if (
                            int(column["column_key"].split("[")[1].split("]")[0])
                            > max_location_index
                        ):
                            invalid_column_errors.append(
                                f'The location index of {column["column_key"].split("[")[1].split("]")[0]} for {column["column_key"]} is invalid. It must be in the range [0:{max_location_index}] because there are {max_location_index + 1} geo levels defined for the survey.'
                            )

                    elif (
                        location_key == "surveyor_locations"
                        and enumerator_location_configured is True
                    ):
                        for i, geo_level in enumerate(
                            geo_level_hierarchy.ordered_geo_levels
                        ):
                            if geo_level.geo_level_uid == prime_geo_level_uid:
                                max_location_index = i

                        if (
                            int(column["column_key"].split("[")[1].split("]")[0])
                            > max_location_index
                        ):
                            invalid_column_errors.append(
                                f'The location index of {column["column_key"].split("[")[1].split("]")[0]} for {column["column_key"]} is invalid. It must be in the range [0:{max_location_index}] because {max_location_index} is the index of the prime geo level defined for the survey.'
                            )

            elif column["column_key"].startswith("custom_fields"):
                # Custom fields must follow the format custom_fields['<custom_field_name>']
                if not re.match(r"^custom_fields\[\'.+\'\]$", column["column_key"]):
                    invalid_column_errors.append(
                        f'{column["column_key"]} is not in the correct format. It should follow the pattern custom_fields[\'<custom_field_name>\']'
                    )

                else:
                    # We know that the custom field is in the correct format. If it's not in the available columns then it's not in the corresponding column config table.
                    custom_field_name = column["column_key"].split("custom_fields['")[
                        1
                    ][0:-2]

                    if table_name in [
                        "assignments_main",
                        "targets",
                        "assignments_review",
                    ]:

                        invalid_column_errors.append(
                            f"The custom field '{custom_field_name}' is not defined in the target_column_config table for this form."
                        )

                    if (
                        table_name == "assignments_surveyors"
                        or table_name == "surveyors"
                    ):

                        invalid_column_errors.append(
                            f"The custom field '{custom_field_name}' is not defined in the enumerator_column_config table for this form."
                        )

            elif table_name in ["assignments_main", "assignments_review"] and column[
                "column_key"
            ].startswith("assigned_enumerator_custom_fields"):
                # Custom fields must follow the format enumerator_custom_fields['<custom_field_name>']
                if not re.match(
                    r"^assigned_enumerator_custom_fields\[\'.+\'\]$",
                    column["column_key"],
                ):
                    invalid_column_errors.append(
                        f'{column["column_key"]} is not in the correct format. It should follow the pattern assigned_enumerator_custom_fields[\'<custom_field_name>\']'
                    )

                else:

                    # Check that the custom field is defined in the target or enumerator column config table

                    custom_field_name = column["column_key"].split(
                        "assigned_enumerator_custom_fields['"
                    )[1][0:-2]

                    invalid_column_errors.append(
                        f"The enumerator custom field '{custom_field_name}' is not defined in the enumerator_column_config table for this form."
                    )

            elif column["column_key"].startswith("form_productivity"):
                # Check that the string is in the correct format
                if not re.match(
                    r"^form_productivity.[a-zA-z0-9_-]+.(total_assigned_targets|total_completed_targets|total_pending_targets)$",
                    column["column_key"],
                ):
                    invalid_column_errors.append(
                        f'{column["column_key"]} is not in the correct format. It should follow the pattern form_productivity.<surveycto_form_id>.<total_assigned_target|total_completed_targets|total_pending_targets>'
                    )

                else:
                    # Check that the surveycto_form_id is valid
                    surveycto_form_id = column["column_key"].split(".")[1].split(".")[0]
                    if (
                        Form.query.filter(
                            Form.scto_form_id == surveycto_form_id,
                            Form.survey_uid == survey_uid,
                        ).first()
                        is None
                    ):
                        invalid_column_errors.append(
                            f"The surveycto_form_id '{surveycto_form_id}' is not found in the forms defined for this survey."
                        )

            elif column["column_key"].startswith("scto_fields"):

                # Check that the string is in the correct format
                if not re.match(
                    r"^scto_fields.[a-zA-z0-9_]+$",
                    column["column_key"],
                ):
                    invalid_column_errors.append(
                        f'\'{column["column_key"]}\' is not in the correct format. It should follow the pattern scto_fields.<surveycto_field_name> (allowed characters are a-z, A-Z, 0-9, _).'
                    )

                invalid_column_errors.append(
                    f'The SurveyCTO field \'{column["column_key"].split(".")[1]}\' was not found in the form definition for this form.'
                )

            else:
                invalid_column_errors.append(
                    f"'{column['column_key']}' is not an allowed key for the {table_name} table configuration"
                )

    if len(invalid_column_errors) > 0:
        raise InvalidTableConfigError(invalid_column_errors)
