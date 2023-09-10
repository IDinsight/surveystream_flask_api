import io
import pandas as pd
import numpy as np
from csv import DictReader
from app.blueprints.locations.models import Location
from .models import Target
from .errors import (
    HeaderRowEmptyError,
    InvalidTargetRecordsError,
    InvalidColumnMappingError,
    InvalidFileStructureError,
)


class TargetColumnMapping:
    """
    Class to represent the target column mapping and run validations on it
    """

    def __init__(self, column_mapping):
        try:
            self.__validate_column_mapping(column_mapping)
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

    def __validate_column_mapping(self, column_mapping):
        """
        Method to run validations on the column mapping and raise an exception containing a list of errors

        :param geo_levels: List of geo levels for the survey from the database
        :param column_mapping: List of column mappings from the request payload
        """

        mapping_errors = []

        # Each mandatory column should appear in the mapping exactly once
        # The validator will catch the case where a mandatory column is missing
        # It's a dictionary so we cannot have duplicate keys

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
        duplicates = [key for key, values in rev_multidict.items() if len(values) > 1]
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

    def __init__(self, csv_string):
        try:
            self.col_names = self.__get_col_names(csv_string)
        except:
            raise
        self.targets_df = self.__build_targets_df(csv_string)

    def __get_col_names(self, csv_string):
        col_names = DictReader(io.StringIO(csv_string)).fieldnames
        if len(col_names) == 0:
            raise HeaderRowEmptyError(
                "Column names were not found in the file. Make sure the first row of the file contains column names."
            )

        return col_names

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

    def validate_records(
        self, expected_columns, column_mapping, bottom_level_geo_level_uid, form, mode
    ):
        """
        Method to run validations on the targets data

        :param expected_columns: List of expected column names from the column mapping
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
                "ordered_columns": ["row_number"] + expected_columns + ["errors"],
                "records": None,
            },
        }

        # Check for a valid file structure before running any other validations on the records

        # Each mapped column should appear in the csv file exactly once
        file_columns = self.targets_df.columns.to_list()
        for column_name in expected_columns:
            if file_columns.count(column_name) != 1:
                file_structure_errors.append(
                    f"Column name '{column_name}' from the column mapping appears {file_columns.count(column_name)} time(s) in the uploaded file. It should appear exactly once."
                )

        # Each column in the csv file should be mapped exactly once
        for column_name in file_columns:
            if expected_columns.count(column_name) != 1:
                file_structure_errors.append(
                    f"Column name '{column_name}' in the csv file appears {expected_columns.count(column_name)} time(s) in the column mapping. It should appear exactly once."
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

                non_null_columns_df.at[
                    index, "errors"
                ] = f"Blank field(s) found in the following column(s): {', '.join(blank_columns)}. The column(s) cannot contain blank fields."

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

        # If the mode is `append`, the file should have no target_id's that are already in the database
        if mode == "append":
            target_id_query = (
                Target.query.filter(
                    Target.form_uid == form.form_uid,
                )
                .with_entities(Target.target_id)
                .distinct()
            )
            invalid_target_id_df = self.targets_df[
                self.targets_df["target_id"].isin(
                    [row[0] for row in target_id_query.all()]
                )
            ]
            if len(invalid_target_id_df) > 0:
                record_errors["summary_by_error_type"].append(
                    {
                        "error_type": "target_id's found in database",
                        "error_message": f"The file contains {len(invalid_target_id_df)} target_id(s) that have already been uploaded. The following row numbers contain target_id's that have already been uploaded: {', '.join(str(row_number) for row_number in invalid_target_id_df.index.to_list())}",
                        "error_count": len(invalid_target_id_df),
                        "row_numbers_with_errors": invalid_target_id_df.index.to_list(),
                    }
                )

                invalid_target_id_df[
                    "errors"
                ] = "The same target_id already exists for the form - target_id's must be unique for each form"
                invalid_records_df = invalid_records_df.merge(
                    invalid_target_id_df["errors"],
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

        # If the location_id_column is mapped, the file should contain no location_id's that are not in the database
        if hasattr(column_mapping, "location_id_column"):
            location_id_query = (
                Location.query.filter(
                    Location.survey_uid == form.survey_uid,
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

                invalid_location_id_df[
                    "errors"
                ] = "Location id not found in uploaded locations data for the survey's bottom level geo level"
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
