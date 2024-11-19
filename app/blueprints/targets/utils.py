import io
from csv import DictReader

import numpy as np
import pandas as pd
from sqlalchemy import insert

from app import db
from app.blueprints.locations.models import Location
from app.blueprints.mapping.models import UserTargetMapping

from .errors import (
    HeaderRowEmptyError,
    InvalidColumnMappingError,
    InvalidFileStructureError,
    InvalidTargetRecordsError,
)
from .models import Target, TargetStatus


class TargetColumnMapping:
    """
    Class to represent the target column mapping and run validations on it
    """

    def __init__(self, column_mapping, form_uid, write_mode, mapping_criteria):
        try:
            self.__validate_column_mapping(column_mapping, mapping_criteria)
            self.target_id = column_mapping["target_id"]

            if column_mapping.get("language"):
                self.language = column_mapping["language"]

            if column_mapping.get("gender"):
                self.gender = column_mapping["gender"]

            if column_mapping.get("location_id_column"):
                self.location_id_column = column_mapping["location_id_column"]

            if column_mapping.get("custom_fields"):
                self.custom_fields = column_mapping["custom_fields"]
        except:
            raise

    def to_dict(self):
        result = {}

        if hasattr(self, "target_id") and self.target_id:
            result["target_id"] = self.target_id
        if hasattr(self, "language") and self.language:
            result["language"] = self.language
        if hasattr(self, "location_id_column") and self.location_id_column:
            result["location_id_column"] = self.location_id_column
        if hasattr(self, "gender") and self.gender:
            result["gender"] = self.gender
        if hasattr(self, "custom_fields") and self.custom_fields:
            result["custom_fields"] = self.custom_fields

        return result

    def __validate_column_mapping(self, column_mapping, mapping_criteria):
        """
        Method to run validations on the column mapping and raise an exception containing a list of errors

        :param column_mapping: List of column mappings from the request payload
        :param mapping_criteria: List of mapping criteria for targets to supervisor mapping
        """

        mapping_errors = []

        # Each mandatory column should appear in the mapping exactly once
        # The validator will catch the case where a mandatory column is missing
        # It's a dictionary so we cannot have duplicate keys

        # Columns based on the mapping criteria should be present in the column mapping
        if "Gender" in mapping_criteria and column_mapping.get("gender") is None:
            mapping_errors.append(
                f"Field name 'gender' is missing from the column mapping but is required based on the mapping criteria."
            )
        if (
            "Location" in mapping_criteria
            and column_mapping.get("location_id_column") is None
        ):
            mapping_errors.append(
                f"Field name 'location_id_column' is missing from the column mapping but is required based on the mapping criteria."
            )
        if "Language" in mapping_criteria and column_mapping.get("language") is None:
            mapping_errors.append(
                f"Field name 'language' is missing from the column mapping but is required based on the mapping criteria."
            )

        # Field names should be unique
        field_names = []
        for field_name, mapped_column in column_mapping.items():
            if field_name == "custom_fields":
                for custom_field in column_mapping["custom_fields"]:
                    if custom_field["field_label"] in field_names:
                        mapping_errors.append(
                            f"Field name '{custom_field['field_label']}' appears multiple times in the column mapping. Field names should be unique."
                        )
                    field_names.append(custom_field["field_label"])
            else:
                if field_name in field_names:
                    mapping_errors.append(
                        f"Field name '{field_name}' appears multiple times in the column mapping. Field names should be unique."
                    )
                field_names.append(field_name)

        # Mapped column names should be unique
        rev_multidict = {}
        for field_name, mapped_column in column_mapping.items():
            if field_name == "custom_fields":
                for custom_field in column_mapping["custom_fields"]:
                    rev_multidict.setdefault(custom_field["column_name"], set()).add(
                        custom_field["field_label"]
                    )
            else:
                rev_multidict.setdefault(mapped_column, set()).add(field_name)
        duplicates = [
            key
            for key, values in rev_multidict.items()
            if len(values) > 1 and key not in ("", "None", None)
        ]
        for mapped_column in duplicates:
            mapping_errors.append(
                f"Column name '{mapped_column}' is mapped to multiple fields: ({', '.join(rev_multidict[mapped_column])}). Column names should only be mapped once."
            )

        if len(mapping_errors) > 0:
            raise InvalidColumnMappingError(mapping_errors)

        return


class TargetsUpload:
    """
    Class to represent the targets data and run validations on it
    """

    def __init__(self, csv_string, column_mapping, survey_uid, form_uid):
        try:
            self.col_names = self.__get_col_names(csv_string)
        except Exception as e:
            raise e

        self.survey_uid = survey_uid
        self.form_uid = form_uid
        self.expected_columns = self.__build_expected_columns(column_mapping)
        self.targets_df = self.__build_targets_df(csv_string)

    def __get_col_names(self, csv_string):
        col_names = DictReader(io.StringIO(csv_string)).fieldnames
        if len(col_names) == 0:
            raise HeaderRowEmptyError(
                "Column names were not found in the file. Make sure the first row of the file contains column names."
            )

        return col_names

    def __build_expected_columns(self, column_mapping):
        """
        Get the expected columns from the mapped column names
        These are the columns that should be in the csv file
        """

        expected_columns = [
            column_mapping.target_id,
        ]

        if hasattr(column_mapping, "language"):
            expected_columns.append(column_mapping.language)

        if hasattr(column_mapping, "gender"):
            expected_columns.append(column_mapping.gender)

        if hasattr(column_mapping, "location_id_column"):
            expected_columns.append(column_mapping.location_id_column)

        if hasattr(column_mapping, "custom_fields"):
            for custom_field in column_mapping.custom_fields:
                expected_columns.append(custom_field["column_name"])

        return expected_columns

    def __build_targets_df(self, csv_string):
        """
        Method to create and format the targets dataframe from the decoded csv file string
        """

        # Read the csv content into a dataframe
        targets_df = pd.read_csv(
            io.StringIO(csv_string),
            dtype=str,
            keep_default_na=False,
        )

        # Override the column names in case there are duplicate column names
        # This is needed because pandas will append a .1 to the duplicate column name
        # Get column names from csv file using DictReader

        targets_df.columns = self.col_names

        # Strip white space from all columns
        for index in range(targets_df.shape[1]):
            targets_df.iloc[:, index] = targets_df.iloc[:, index].str.strip()

        # Replace empty strings with NaN
        targets_df = targets_df.replace("", np.nan)

        # Shift the index by 2 so that the row numbers start at 2 (to match the row numbers in the csv file)
        targets_df.index += 2

        # Rename the index column to row_number
        targets_df.index.name = "row_number"

        return targets_df

    def validate_records(self, column_mapping, bottom_level_geo_level_uid, write_mode):
        """
        Method to run validations on the targets data
        """

        file_structure_errors = []

        record_errors = {
            "summary": {
                "total_rows": len(self.targets_df),
                "total_correct_rows": None,
                "total_rows_with_errors": None,
            },
            "summary_by_error_type": [],
            "invalid_records": {
                "ordered_columns": ["row_number"] + self.expected_columns + ["errors"],
                "records": None,
            },
        }

        # Check for a valid file structure before running any other validations on the records

        # Each mapped column should appear in the csv file exactly once
        file_columns = self.targets_df.columns.to_list()
        for column_name in self.expected_columns:
            if file_columns.count(column_name) != 1:
                file_structure_errors.append(
                    f"Column name '{column_name}' from the column mapping appears {file_columns.count(column_name)} time(s) in the uploaded file. It should appear exactly once."
                )

        if len(file_structure_errors) > 0:
            raise InvalidFileStructureError(file_structure_errors)

        # Run validations on the records

        # Create an empty copy of the targets dataframe to store the error messages for the invalid records
        invalid_records_df = self.targets_df.copy()
        invalid_records_df["errors"] = ""

        # Non-nullable columns should contain no blank fields
        non_null_columns = [
            column_mapping.target_id,
        ]

        if hasattr(column_mapping, "location_id_column"):
            non_null_columns.append(column_mapping.location_id_column)

        non_null_columns_df = self.targets_df.copy()[
            self.targets_df[non_null_columns].isnull().any(axis=1)
        ]

        if len(non_null_columns_df) > 0:
            record_errors["summary_by_error_type"].append(
                {
                    "error_type": "Blank field",
                    "error_message": f"Blank values are not allowed in the following columns: {', '.join(non_null_columns)}. Blank values in these columns were found for the following row(s): {', '.join(str(row_number) for row_number in non_null_columns_df.index.to_list())}",
                    "error_count": 0,
                    "row_numbers_with_errors": non_null_columns_df.index.to_list(),
                }
            )

            # Add the error message to the non_null_columns_df dataframe
            # The error message should contain the column name(s) with the blank field(s)
            # Iterate over the dataframe
            for index, row in non_null_columns_df.iterrows():
                blank_columns = []
                for column_name in non_null_columns:
                    if pd.isnull(row[column_name]):
                        blank_columns.append(column_name)
                        record_errors["summary_by_error_type"][-1]["error_count"] += 1

                non_null_columns_df.at[index, "errors"] = (
                    f"Blank field(s) found in the following column(s): {', '.join(blank_columns)}. The column(s) cannot contain blank fields."
                )

            invalid_records_df = invalid_records_df.merge(
                non_null_columns_df[["errors"]],
                how="left",
                left_index=True,
                right_index=True,
            )
            # Replace NaN with empty string
            invalid_records_df["errors_y"] = invalid_records_df["errors_y"].fillna("")

            invalid_records_df["errors"] = invalid_records_df[
                ["errors_x", "errors_y"]
            ].apply("; ".join, axis=1)
            invalid_records_df = invalid_records_df.drop(
                columns=["errors_x", "errors_y"]
            )
            invalid_records_df["errors"] = invalid_records_df["errors"].str.strip("; ")

        # The file should have no duplicate rows
        duplicates_df = self.targets_df.copy()[self.targets_df.duplicated(keep=False)]
        if len(duplicates_df) > 0:
            record_errors["summary_by_error_type"].append(
                {
                    "error_type": "Duplicate rows",
                    "error_message": f"The file has {len(duplicates_df)} duplicate row(s). Duplicate rows are not allowed. The following row numbers are duplicates: {', '.join(str(row_number) for row_number in duplicates_df.index.to_list())}",
                    "error_count": len(duplicates_df),
                    "row_numbers_with_errors": duplicates_df.index.to_list(),
                }
            )

            duplicates_df["errors"] = "Duplicate row"

            invalid_records_df = invalid_records_df.merge(
                duplicates_df[["errors"]], how="left", left_index=True, right_index=True
            )
            # Replace NaN with empty string
            invalid_records_df["errors_y"] = invalid_records_df["errors_y"].fillna("")

            invalid_records_df["errors"] = invalid_records_df[
                ["errors_x", "errors_y"]
            ].apply("; ".join, axis=1)
            invalid_records_df = invalid_records_df.drop(
                columns=["errors_x", "errors_y"]
            )
            invalid_records_df["errors"] = invalid_records_df["errors"].str.strip("; ")

        # The file should have no duplicate target IDs
        duplicates_df = self.targets_df[
            self.targets_df.duplicated(subset=column_mapping.target_id, keep=False)
        ]
        if len(duplicates_df) > 0:
            record_errors["summary_by_error_type"].append(
                {
                    "error_type": "Duplicate target_id's in file",
                    "error_message": f"The file has {len(duplicates_df)} duplicate target_id(s). The following row numbers contain target_id duplicates: {', '.join(str(row_number) for row_number in duplicates_df.index.to_list())}",
                    "error_count": len(duplicates_df),
                    "row_numbers_with_errors": duplicates_df.index.to_list(),
                }
            )

            duplicates_df["errors"] = "Duplicate target_id"
            invalid_records_df = invalid_records_df.merge(
                duplicates_df["errors"], how="left", left_index=True, right_index=True
            )
            # Replace NaN with empty string
            invalid_records_df["errors_y"] = invalid_records_df["errors_y"].fillna("")
            invalid_records_df["errors"] = invalid_records_df[
                ["errors_x", "errors_y"]
            ].apply("; ".join, axis=1)
            invalid_records_df = invalid_records_df.drop(
                columns=["errors_x", "errors_y"]
            )
            invalid_records_df["errors"] = invalid_records_df["errors"].str.strip("; ")

        # If the location_id_column is mapped, the file should contain no location_id's that are not in the database
        if hasattr(column_mapping, "location_id_column"):
            location_id_query = (
                Location.query.filter(
                    Location.survey_uid == self.survey_uid,
                    Location.geo_level_uid == bottom_level_geo_level_uid,
                )
                .with_entities(Location.location_id)
                .distinct()
            )
            invalid_location_id_df = self.targets_df[
                ~self.targets_df[column_mapping.location_id_column].isin(
                    [row[0] for row in location_id_query.all()]
                )
            ]
            if len(invalid_location_id_df) > 0:
                record_errors["summary_by_error_type"].append(
                    {
                        "error_type": "Invalid location_id's",
                        "error_message": f"The file contains {len(invalid_location_id_df)} location_id(s) that were not found in the uploaded locations data. The following row numbers contain invalid location_id's: {', '.join(str(row_number) for row_number in invalid_location_id_df.index.to_list())}",
                        "error_count": len(invalid_location_id_df),
                        "row_numbers_with_errors": invalid_location_id_df.index.to_list(),
                    }
                )

                invalid_location_id_df["errors"] = (
                    "Location id not found in uploaded locations data for the survey's bottom level geo level"
                )
                invalid_records_df = invalid_records_df.merge(
                    invalid_location_id_df["errors"],
                    how="left",
                    left_index=True,
                    right_index=True,
                )
                # Replace NaN with empty string
                invalid_records_df["errors_y"] = invalid_records_df["errors_y"].fillna(
                    ""
                )
                invalid_records_df["errors"] = invalid_records_df[
                    ["errors_x", "errors_y"]
                ].apply("; ".join, axis=1)
                invalid_records_df = invalid_records_df.drop(
                    columns=["errors_x", "errors_y"]
                )
                invalid_records_df["errors"] = invalid_records_df["errors"].str.strip(
                    "; "
                )

        if len(record_errors["summary_by_error_type"]) > 0:
            record_errors["summary"]["total_correct_rows"] = len(
                invalid_records_df[invalid_records_df["errors"] == ""]
            )
            record_errors["summary"]["total_rows_with_errors"] = len(
                invalid_records_df[invalid_records_df["errors"] != ""]
            )
            record_errors["summary"]["error_count"] = sum(
                [
                    error["error_count"]
                    for error in record_errors["summary_by_error_type"]
                ]
            )

            invalid_records_df["row_number"] = invalid_records_df.index

            record_errors["invalid_records"]["records"] = (
                invalid_records_df[invalid_records_df["errors"] != ""]
                .fillna("")
                .to_dict(orient="records")
            )
            raise InvalidTargetRecordsError(record_errors)

        return

    def filter_successful_records(self, record_errors):
        """
        Method to filter the records that have no errors

        """
        row_numbers_with_errors = [
            error["row_numbers_with_errors"]
            for error in record_errors["summary_by_error_type"]
        ]
        error_record_indices = [
            item for sublist in row_numbers_with_errors for item in sublist
        ]

        # deduplicate the list of error record indices
        error_record_indices = list(set(error_record_indices))

        self.targets_df = self.targets_df[
            ~self.targets_df.index.isin(error_record_indices)
        ]

        return

    def save_records(self, column_mapping, write_mode):
        """
        Method to save the targets data to the database
        """

        ####################################################################
        # Prepare a list of the target records to insert into the database
        ####################################################################

        location_uid_lookup = self.__build_location_uid_lookup(column_mapping)

        self.targets_df = self.targets_df[self.expected_columns]

        ####################################################################
        # Use the list of target records to write to the database
        ####################################################################

        records_to_write = []

        for row in self.targets_df.drop_duplicates().itertuples():
            target_dict = self.__build_target_dict(
                row, column_mapping, location_uid_lookup
            )

            # Ensure 'custom_fields' exists and add 'column_mapping'
            custom_fields = target_dict.setdefault("custom_fields", {})
            custom_fields.setdefault("column_mapping", column_mapping.to_dict())

            records_to_write.append(target_dict)

        if write_mode == "overwrite":
            # For the overwrite mode, delete existing records for the form and insert the records in chunks of 1000 using the fast bulk insert method

            # Remove rows from target status table first
            subquery = db.session.query(Target.target_uid).filter(
                Target.form_uid == self.form_uid
            )
            db.session.query(TargetStatus).filter(
                TargetStatus.target_uid.in_(subquery)
            ).delete(synchronize_session=False)

            # Remove rows from UserTargetMapping table
            db.session.query(UserTargetMapping).filter(
                UserTargetMapping.target_uid.in_(subquery)
            ).delete(synchronize_session=False)

            Target.query.filter_by(form_uid=self.form_uid).delete()
            db.session.commit()

            chunk_size = 1000
            for pos in range(0, len(records_to_write), chunk_size):
                db.session.execute(
                    insert(Target).values(records_to_write[pos : pos + chunk_size])
                )
                db.session.flush()

        elif write_mode == "merge":
            # This mode will include new records added and update the existing records with the new data;
            # target_id columns should not be updated
            target_ids = [item["target_id"] for item in records_to_write]

            # Collect records to update separately from the records to insert, so we can perform bulk updates reducing db overhead
            records_to_insert = []
            records_to_update = []

            existing_targets = (
                db.session.query(Target.target_id)
                .filter(
                    Target.form_uid == self.form_uid, Target.target_id.in_(target_ids)
                )
                .all()
            )

            existing_target_ids = [result[0] for result in existing_targets]

            for row in records_to_write:
                target_dict = row
                if target_dict["target_id"] in existing_target_ids:
                    records_to_update.append(target_dict)
                else:
                    records_to_insert.append(target_dict)

            for record in records_to_update:
                update_values = {
                    key: record[key]
                    for key in record
                    if key not in ["target_id", "form_uid", "custom_fields"]
                }

                if update_values:
                    Target.query.filter(
                        Target.target_id == record["target_id"],
                        Target.form_uid == self.form_uid,
                    ).update(update_values, synchronize_session=False)

                if "custom_fields" in record:
                    target_record = Target.query.filter_by(
                        target_id=record["target_id"], form_uid=record["form_uid"]
                    ).first()

                    for field_name, field_value in record["custom_fields"].items():
                        target_record.custom_fields[field_name] = field_value

            if records_to_insert:
                # Insert records in chunks to the database
                chunk_size = 1000
                for pos in range(0, len(records_to_insert), chunk_size):
                    db.session.execute(
                        insert(Target).values(records_to_insert[pos : pos + chunk_size])
                    )
                    db.session.flush()

        db.session.commit()
        return

    def __build_location_uid_lookup(self, column_mapping):
        """
        Create a location UID lookup if the location ID column is present
        """

        if hasattr(column_mapping, "location_id_column"):
            # Get the location UID from the location ID
            locations = Location.query.filter(
                Location.location_id.in_(
                    self.targets_df[column_mapping.location_id_column]
                    .drop_duplicates()
                    .tolist()
                ),
                Location.survey_uid == self.survey_uid,
            ).with_entities(Location.location_uid, Location.location_id)

            # Create a dictionary of location ID to location UID
            location_uid_lookup = {
                location.location_id: location.location_uid
                for location in locations.all()
            }

            return location_uid_lookup

        else:
            return None

    def __build_target_dict(self, row, column_mapping, location_uid_lookup):
        """
        Method to build the target dictionary from the targets dataframe row
        """

        target_dict = {
            "form_uid": self.form_uid,
            "target_id": row[1],
        }

        # Add the language if it exists
        if hasattr(column_mapping, "language"):
            col_index = (
                self.targets_df.columns.get_loc(column_mapping.language) + 1
            )  # Add 1 to the index to account for the df index
            target_dict["language"] = row[col_index]

        # Add the gender if it exists
        if hasattr(column_mapping, "gender"):
            col_index = (
                self.targets_df.columns.get_loc(column_mapping.gender) + 1
            )  # Add 1 to the index to account for the df index
            target_dict["gender"] = row[col_index]

        if hasattr(column_mapping, "location_id_column"):
            col_index = (
                self.targets_df.columns.get_loc(column_mapping.location_id_column) + 1
            )
            target_dict["location_uid"] = location_uid_lookup[row[col_index]]

        # Add the custom fields if they exist
        if hasattr(column_mapping, "custom_fields"):
            custom_fields = {}
            for custom_field in column_mapping.custom_fields:
                col_index = (
                    self.targets_df.columns.get_loc(custom_field["column_name"]) + 1
                )  # Add 1 to the index to account for the df index
                custom_fields[custom_field["field_label"]] = row[col_index]
            target_dict["custom_fields"] = custom_fields

        return target_dict


def apply_target_scto_filters(csv_string, target_filters):
    """
    Create a new CSV string with the target records filtered based on the filter input

    CSV is read in chunks and filters are applied till the end of the file or a threshold is reached

    Args:
        csv_string: The CSV string containing the target records
        target_filters: The filters to apply to the target records, Array of TargetSCTOFilter objects
    """

    # Create filter strings
    final_filter_string = ""
    filter_count = 0
    for filter_group_arr in target_filters:
        group_count = 0
        filter_group = filter_group_arr["filter_group"]
        # Initialize
        filter_string = " ( "
        for filter in filter_group:
            column_name = filter["variable_name"]
            filter_value = filter["filter_value"]
            filter_operator = filter["filter_operator"]

            if group_count > 0:
                filter_string += " & "
            group_count += 1

            if filter_value:
                filter_value = "'" + filter_value + "'"

            if filter_operator == "Is":
                filter_string += (
                    "( chunk_df['" + column_name + "'] == " + filter_value + " )"
                )
            elif filter_operator == "Is not":
                filter_string += (
                    "( chunk_df['" + column_name + "'] != " + filter_value + " )"
                )
            elif filter_operator == "Contains":
                filter_string += (
                    "(  chunk_df['"
                    + column_name
                    + "'].str.contains('"
                    + str(filter_value)
                    + "')  )"
                )
            elif filter_operator == "Does not contain":
                filter_string += (
                    "(  ~chunk_df['"
                    + column_name
                    + "'].str.contains('"
                    + str(filter_value)
                    + "') )"
                )
            elif filter_operator == "Is empty":
                filter_string += "(  chunk_df['" + column_name + "'].isnull() )"
            elif filter_operator == "Is not empty":
                filter_string += "(  ~chunk_df['" + column_name + "'].isnull() )"

        filter_string += " ) "
        if filter_count > 0:
            final_filter_string = final_filter_string + " | "

        final_filter_string += filter_string
        filter_count += 1

    # Read the CSV string in chunks of 100 rows at a time
    chunk_size = 100
    filtered_data = pd.DataFrame()

    for chunk_df in pd.read_csv(
        io.StringIO(csv_string), chunksize=chunk_size, dtype=str
    ):
        chunk_df = chunk_df.replace("", np.nan)

        # Apply the filter string to the chunk
        filtered_chunk = chunk_df[eval(final_filter_string)]

        filtered_data = pd.concat([filtered_data, filtered_chunk])
        if len(filtered_data) >= 20:
            break

    # Convert the filtered data back to a CSV string
    filtered_csv_string = filtered_data.to_csv(index=False)
    return filtered_csv_string
