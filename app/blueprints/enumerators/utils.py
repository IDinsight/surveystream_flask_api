import io
import json
import pandas as pd
import numpy as np
from app import db
from flask_login import current_user
from csv import DictReader
from app.blueprints.locations.models import Location
from .models import (
    Enumerator,
    SurveyorForm,
    MonitorForm,
    SurveyorLocation,
    MonitorLocation,
)
from .errors import (
    HeaderRowEmptyError,
    InvalidEnumeratorRecordsError,
    InvalidColumnMappingError,
    InvalidFileStructureError,
)
from email_validator import validate_email, EmailNotValidError



class EnumeratorColumnMapping:
    """
    Class to represent the enumerator column mapping and run validations on it
    """

    def __init__(
        self, column_mapping, prime_geo_level_uid=None, optional_hardcoded_fields=[]
    ):
        try:
            self.__validate_column_mapping(column_mapping, prime_geo_level_uid)
            self.enumerator_id = column_mapping["enumerator_id"]
            self.name = column_mapping["name"]
            self.email = column_mapping["email"]
            self.mobile_primary = column_mapping["mobile_primary"]
            self.enumerator_type = column_mapping["enumerator_type"]

            if column_mapping.get("location_id_column"):
                self.location_id_column = column_mapping["location_id_column"]

            if column_mapping.get("gender"):
                self.gender = column_mapping["gender"]

            if column_mapping.get("home_address"):
                self.home_address = column_mapping["home_address"]

            if column_mapping.get("language"):
                self.language = column_mapping["language"]

            if column_mapping.get("custom_fields"):
                self.custom_fields = column_mapping["custom_fields"]

            for field in optional_hardcoded_fields:
                if column_mapping.get(field):
                    setattr(self, field, column_mapping[field])

        except:
            raise

    def to_dict(self, optional_hardcoded_fields=[]):
        result = {}

        if hasattr(self, 'enumerator_id') and self.enumerator_id:
            result["enumerator_id"] = self.enumerator_id
        if hasattr(self, 'name') and self.name:
            result["name"] = self.name
        if hasattr(self, 'email') and self.email:
            result["email"] = self.email
        if hasattr(self, 'mobile_primary') and self.mobile_primary:
            result["mobile_primary"] = self.mobile_primary
        if hasattr(self, 'enumerator_type') and self.enumerator_type:
            result["enumerator_type"] = self.enumerator_type
        if hasattr(self, 'gender') and self.gender:
            result["gender"] = self.gender
        if hasattr(self, 'language') and self.language:
            result["language"] = self.language
        if hasattr(self, 'home_address') and self.home_address:
            result["home_address"] = self.home_address
        if hasattr(self, 'enumerator_type') and self.enumerator_type:
            result["enumerator_type"] = self.enumerator_type
        if hasattr(self, 'location_id_column') and self.location_id_column:
            result["location_id_column"] = self.location_id_column
        if hasattr(self, 'custom_fields') and self.custom_fields:
            result["custom_fields"] = self.custom_fields
        for field in optional_hardcoded_fields:
            if hasattr(self, field) and getattr(self, field):
                result[field] = getattr(self, field)
        return result

    def __validate_column_mapping(self, column_mapping, prime_geo_level_uid):
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

        # If location_id_column is mapped, there should be a prime geo level defined for the survey
        if column_mapping.get("location_id_column") and not prime_geo_level_uid:
            mapping_errors.append(
                "A prime geo level must be defined for the survey if the location_id_column is mapped."
            )

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


class EnumeratorsUpload:
    """
    Class to represent the enumerators data and run validations on it
    """

    def __init__(
        self,
        csv_string,
        column_mapping,
        survey_uid,
        form_uid,
        optional_hardcoded_fields=[],
    ):
        try:
            self.col_names = self.__get_col_names(csv_string)
        except:
            raise
        self.survey_uid = survey_uid
        self.form_uid = form_uid
        self.optional_hardcoded_fields = optional_hardcoded_fields
        self.expected_columns = self.__build_expected_columns(column_mapping)
        self.enumerators_df = self.__build_enumerators_df(csv_string)

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

        # Get the expected columns from the mapped column names

        expected_columns = [
            column_mapping.enumerator_id,
            column_mapping.name,
            column_mapping.email,
            column_mapping.mobile_primary,
            column_mapping.enumerator_type,
        ]

        for optional_field in self.optional_hardcoded_fields:
            if hasattr(column_mapping, optional_field):
                expected_columns.append(getattr(column_mapping, optional_field))

        if hasattr(column_mapping, "location_id_column"):
            expected_columns.append(column_mapping.location_id_column)

        if hasattr(column_mapping, "custom_fields"):
            for custom_field in column_mapping.custom_fields:
                expected_columns.append(custom_field["column_name"])

        return expected_columns

    def __build_enumerators_df(self, csv_string):
        """
        Method to create and format the enumerators dataframe from the decoded csv file string
        """

        # Read the csv content into a dataframe
        enumerators_df = pd.read_csv(
            io.StringIO(csv_string),
            dtype=str,
            keep_default_na=False,
        )

        # Override the column names in case there are duplicate column names
        # This is needed because pandas will append a .1 to the duplicate column name
        # Get column names from csv file using DictReader

        enumerators_df.columns = self.col_names

        # Strip white space from all columns
        for index in range(enumerators_df.shape[1]):
            enumerators_df.iloc[:, index] = enumerators_df.iloc[:, index].str.strip()

        # Replace empty strings with NaN
        enumerators_df = enumerators_df.replace("", np.nan)

        # Shift the index by 2 so that the row numbers start at 2 (to match the row numbers in the csv file)
        enumerators_df.index += 2

        # Rename the index column to row_number
        enumerators_df.index.name = "row_number"

        return enumerators_df

    def validate_records(self, column_mapping, prime_geo_level_uid, write_mode):
        """
        Method to run validations on the enumerators data

        :param expected_columns: List of expected column names from the column mapping
        """

        file_structure_errors = []

        record_errors = {
            "summary": {
                "total_rows": len(self.enumerators_df),
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
        file_columns = self.enumerators_df.columns.to_list()
        for column_name in self.expected_columns:
            if file_columns.count(column_name) != 1:
                file_structure_errors.append(
                    f"Column name '{column_name}' from the column mapping appears {file_columns.count(column_name)} time(s) in the uploaded file. It should appear exactly once."
                )

        if len(file_structure_errors) > 0:
            raise InvalidFileStructureError(file_structure_errors)

        # Run validations on the records

        # Create an empty copy of the enumerators dataframe to store the error messages for the invalid records
        invalid_records_df = self.enumerators_df.copy()
        invalid_records_df["errors"] = ""

        # Mandatory columns should contain no blank fields
        non_null_columns = [
            column_mapping.enumerator_id,
            column_mapping.name,
            column_mapping.email,
            column_mapping.enumerator_type,
        ]

        non_null_columns_df = self.enumerators_df.copy()[
            self.enumerators_df[non_null_columns].isnull().any(axis=1)
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
        duplicates_df = self.enumerators_df.copy()[
            self.enumerators_df.duplicated(keep=False)
        ]
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

        # The file should have no duplicate enumerator IDs
        duplicates_df = self.enumerators_df[
            self.enumerators_df.duplicated(
                subset=column_mapping.enumerator_id, keep=False
            )
        ]
        if len(duplicates_df) > 0:
            record_errors["summary_by_error_type"].append(
                {
                    "error_type": "Duplicate enumerator_id's in file",
                    "error_message": f"The file has {len(duplicates_df)} duplicate enumerator_id(s). The following row numbers contain enumerator_id duplicates: {', '.join(str(row_number) for row_number in duplicates_df.index.to_list())}",
                    "error_count": len(duplicates_df),
                    "row_numbers_with_errors": duplicates_df.index.to_list(),
                }
            )

            duplicates_df["errors"] = "Duplicate enumerator_id"
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

        # If the write_mode is `merge`, the file can have enumerator_id's that are already in the database

        # Validate the email ID's
        self.enumerators_df["errors"] = ""
        for index, row in self.enumerators_df.iterrows():
            try:
                validate_email(row[column_mapping.email])
            except Exception as e:
                self.enumerators_df.loc[index, "errors"] = str(e)

        invalid_email_id_df = self.enumerators_df[self.enumerators_df["errors"] != ""]
        if len(invalid_email_id_df) > 0:
            record_errors["summary_by_error_type"].append(
                {
                    "error_type": "Invalid email ID",
                    "error_message": f"The file contains {len(invalid_email_id_df)} invalid email ID(s). The following row numbers have invalid email ID's: {', '.join(str(row_number) for row_number in invalid_email_id_df.index.to_list())}",
                    "error_count": len(invalid_email_id_df),
                    "row_numbers_with_errors": invalid_email_id_df.index.to_list(),
                }
            )

            invalid_records_df = invalid_records_df.merge(
                invalid_email_id_df["errors"],
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

        self.enumerators_df.drop(columns=["errors"], inplace=True)

        # Validate the phone numbers
        invalid_mobile_primary_df = self.enumerators_df[
            ~self.enumerators_df[column_mapping.mobile_primary].str.contains(
                r"^[0-9\.\s\-\(\)\+]{10,20}$"
            )
        ]
        if len(invalid_mobile_primary_df) > 0:
            record_errors["summary_by_error_type"].append(
                {
                    "error_type": "Invalid mobile number",
                    "error_message": f"The file contains {len(invalid_mobile_primary_df)} invalid mobile number(s) in the mobile_primary field. Mobile numbers must be between 10 and 20 characters in length and can only contain digits or the special characters '-', '.', '+', '(', or ')'. The following row numbers have invalid mobile numbers: {', '.join(str(row_number) for row_number in invalid_mobile_primary_df.index.to_list())}",
                    "error_count": len(invalid_mobile_primary_df),
                    "row_numbers_with_errors": invalid_mobile_primary_df.index.to_list(),
                }
            )

            invalid_mobile_primary_df[
                "errors"
            ] = "Invalid mobile number - numbers must be between 10 and 20 characters in length and can only contain digits or the special characters '-', '.', '+', '(', or ')'"

            invalid_records_df = invalid_records_df.merge(
                invalid_mobile_primary_df["errors"],
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

        def validate_enumerator_type(enumerator_type):
            is_valid = True
            type_list = enumerator_type.strip().lower().split(";")
            for type in type_list:
                if type.strip() not in ["surveyor", "monitor"]:
                    is_valid = False

            return is_valid

        # Validate the enumerator types
        invalid_enumerator_type_df = self.enumerators_df[
            ~self.enumerators_df[column_mapping.enumerator_type].apply(
                validate_enumerator_type
            )
        ]
        if len(invalid_enumerator_type_df) > 0:
            record_errors["summary_by_error_type"].append(
                {
                    "error_type": "Invalid enumerator type",
                    "error_message": f"The file contains {len(invalid_enumerator_type_df)} invalid enumerator type(s) in the enumerator_type field. Valid enumerator types are 'surveyor' and 'monitor' and can be separated by a semicolon if the enumerator has multiple types. The following row numbers have invalid enumerator types: {', '.join(str(row_number) for row_number in invalid_enumerator_type_df.index.to_list())}",
                    "error_count": len(invalid_enumerator_type_df),
                    "row_numbers_with_errors": invalid_enumerator_type_df.index.to_list(),
                }
            )

            invalid_enumerator_type_df[
                "errors"
            ] = "Invalid enumerator type - valid enumerator types are 'surveyor' and 'monitor' and can be separated by a semicolon if the enumerator has multiple types"

            invalid_records_df = invalid_records_df.merge(
                invalid_enumerator_type_df["errors"],
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

        # If the location_id_column is mapped, the file should contain no location_id's that are not in the database
        if hasattr(column_mapping, "location_id_column"):
            location_id_query = (
                Location.query.filter(
                    Location.survey_uid == self.survey_uid,
                    Location.geo_level_uid == prime_geo_level_uid,
                )
                .with_entities(Location.location_id)
                .distinct()
            )
            invalid_location_id_df = self.enumerators_df[
                ~self.enumerators_df[column_mapping.location_id_column].isin(
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
                ] = "Location id not found in uploaded locations data for the survey's prime geo level"
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
            raise InvalidEnumeratorRecordsError(record_errors)

        return

    def save_records(self, column_mapping, write_mode):
        """
        Method to save the enumerators data to the database
        """

        ####################################################################
        # Prepare a list of the enumerator records to insert into the database
        ####################################################################

        location_uid_lookup = self.__build_location_uid_lookup(column_mapping)

        # Order the columns in the dataframe so we can easily access them by index
        self.enumerators_df = self.enumerators_df[self.expected_columns]

        ####################################################################
        # Use the list of enumerator records to write to the database
        ####################################################################

        records_to_write = [
            row for row in self.enumerators_df.drop_duplicates().itertuples()]

        records_to_insert = []
        records_to_update = []

        if write_mode == "overwrite":
            SurveyorForm.query.filter_by(form_uid=self.form_uid).delete()
            SurveyorLocation.query.filter_by(form_uid=self.form_uid).delete()
            MonitorForm.query.filter_by(form_uid=self.form_uid).delete()
            MonitorLocation.query.filter_by(form_uid=self.form_uid).delete()
            Enumerator.query.filter_by(form_uid=self.form_uid).delete()
            db.session.commit()
            records_to_insert = records_to_write

        if write_mode == "merge":
            enumerator_ids = [item[1]
                              for item in records_to_write]

            
            existing_enumerator = db.session.query(Enumerator.enumerator_id).filter(
                form_uid == self.form_uid,
                Enumerator.enumerator_id.in_(enumerator_ids)
            ).all()

            existing_enumerator_ids = [result[0]
                                       for result in existing_enumerator]

            for row in records_to_write:
                enumerator_dict = row
                if enumerator_dict[1] in existing_enumerator_ids:
                    records_to_update.append(enumerator_dict)
                else:
                    records_to_insert.append(enumerator_dict)

        if records_to_insert:
            # Insert the enumerators into the database
            for i, row in enumerate(records_to_insert):
                enumerator = Enumerator(
                    form_uid=self.form_uid,
                    enumerator_id=row[1],
                    name=row[2],
                    email=row[3],
                    mobile_primary=row[4],
                )

                for optional_field in self.optional_hardcoded_fields:
                    # Add the optional fields
                    if hasattr(column_mapping, optional_field):
                        col_index = (
                            self.enumerators_df.columns.get_loc(
                                getattr(column_mapping, optional_field)
                            )
                            + 1
                        )  # Add 1 to the index to account for the df index
                        setattr(enumerator, optional_field, row[col_index])

                # Add the custom fields with column_mapping if they don't exist
                custom_fields = {}

                if hasattr(column_mapping, "custom_fields"):
                    for custom_field in column_mapping.custom_fields:
                        col_index = (
                            self.enumerators_df.columns.get_loc(
                                custom_field["column_name"])
                            + 1
                        )  # Add 1 to the index to account for the df index
                        custom_fields[custom_field["field_label"]
                                      ] = row[col_index]

                # Add column_mapping to custom fields
                custom_fields['column_mapping'] = column_mapping.to_dict()
                enumerator.custom_fields = custom_fields

                db.session.add(enumerator)
                db.session.flush()

                enumerator_types = [item.lower().strip() for item in row[5].split(";")]

                for enumerator_type in enumerator_types:
                    if enumerator_type == "surveyor":
                        surveyor_form = SurveyorForm(
                            enumerator_uid=enumerator.enumerator_uid,
                            form_uid=self.form_uid,
                            user_uid=current_user.user_uid,
                        )

                        db.session.add(surveyor_form)

                        if hasattr(column_mapping, "location_id_column"):
                            # Get the position of the location column in the dataframe
                            col_index = (
                                self.enumerators_df.columns.get_loc(
                                    getattr(column_mapping, "location_id_column")
                                )
                                + 1
                            )  # Add 1 to the index to account for the df index
                            surveyor_location = SurveyorLocation(
                                enumerator_uid=enumerator.enumerator_uid,
                                form_uid=self.form_uid,
                                location_uid=location_uid_lookup[row[col_index]],
                            )

                            db.session.add(surveyor_location)

                    if enumerator_type == "monitor":
                        monitor_form = MonitorForm(
                            enumerator_uid=enumerator.enumerator_uid,
                            form_uid=self.form_uid,
                            user_uid=current_user.user_uid,
                        )

                        db.session.add(monitor_form)

                        if hasattr(column_mapping, "location_id_column"):
                            # Get the position of the location column in the dataframe
                            col_index = (
                                self.enumerators_df.columns.get_loc(
                                    getattr(column_mapping, "location_id_column")
                                )
                                + 1
                            )
                            monitor_location = MonitorLocation(
                                enumerator_uid=enumerator.enumerator_uid,
                                form_uid=self.form_uid,
                                location_uid=location_uid_lookup[row[col_index]],
                            )

                            db.session.add(monitor_location)

        if records_to_update:
            for record in records_to_update:
                excluded_columns = ["enumerator_id", "form_uid", "custom_fields", "enumerator_type", "location_id_column"]

                column_to_key_mapping = {}

                for key, value in column_mapping.to_dict().items():
                    if key != "custom_fields" and key != 'location_id_column' and key != 'enumerator_type':
                        column_to_key_mapping[value] = key


                enumerator_id = record[1]

                update_data = {
                    column_to_key_mapping[col]: getattr(record, col)
                    for col in record._fields
                    if col not in excluded_columns
                       and col in column_to_key_mapping
                }

                # Update the records in the database
                Enumerator.query.filter(
                    Enumerator.enumerator_id == enumerator_id,
                    Enumerator.form_uid == self.form_uid,
                ).update(update_data, synchronize_session=False)

                # Add column_mapping to custom fields
                # Add the custom fields with column_mapping if they don't exist
                custom_fields = {}

                if hasattr(column_mapping, "custom_fields"):
                    for custom_field in column_mapping.custom_fields:
                        col_index = (
                                self.enumerators_df.columns.get_loc(
                                    custom_field["column_name"])
                                + 1
                        )  # Add 1 to the index to account for the df index
                        custom_fields[custom_field["field_label"]
                        ] = record[col_index]
                # Add column_mapping to custom fields
                custom_fields['column_mapping'] = column_mapping.to_dict()

                if custom_fields:
                    for field_name, field_value in custom_fields.items():
                        jsonb_set_expression = func.jsonb_set(
                            Enumerator.custom_fields,
                            '{%s}' % field_name,
                            json.dumps(field_value),
                            True  # add true to overwrite existing keys
                        )

                        db.session.execute(
                            update(Enumerator)
                            .values(custom_fields=cast(jsonb_set_expression, JSONB))
                            .where(
                                (Enumerator.enumerator_id == record[1]) &
                                (Enumerator.form_uid == self.form_uid)
                            )
                        )            
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
                    self.enumerators_df[column_mapping.location_id_column]
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
