import io
import json
from csv import DictReader
from datetime import datetime

import numpy as np
import pandas as pd
from flask_login import current_user
from sqlalchemy import (
    Date,
    DateTime,
    Integer,
    alias,
    and_,
    cast,
    column,
    func,
    insert,
    select,
    update,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.sql import Values

from app import db
from app.blueprints.emails.models import EmailConfig, EmailSchedule
from app.blueprints.enumerators.models import Enumerator, SurveyorForm
from app.blueprints.mapping.errors import MappingError
from app.blueprints.mapping.utils import SurveyorMapping, TargetMapping
from app.blueprints.roles.utils import check_if_survey_admin
from app.blueprints.targets.models import Target, TargetStatus

from .errors import (
    HeaderRowEmptyError,
    InvalidAssignmentRecordsError,
    InvalidColumnMappingError,
    InvalidFileStructureError,
)
from .models import SurveyorAssignment
from .queries import build_child_users_with_supervisors_query


class AssignmentsColumnMapping:
    """
    Class to represent the assignments column mapping and run validations on it
    """

    def __init__(self, column_mapping):
        try:
            self.__validate_column_mapping(column_mapping)
            self.target_id = column_mapping["target_id"]
            self.enumerator_id = column_mapping["enumerator_id"]

        except:
            raise

    def to_dict(self):
        result = {}

        if hasattr(self, "target_id") and self.target_id:
            result["target_id"] = self.target_id
        if hasattr(self, "enumerator_id") and self.enumerator_id:
            result["enumerator_id"] = self.enumerator_id

        return result

    def __validate_column_mapping(self, column_mapping):
        """
        Method to run validations on the column mapping and raise an exception containing a list of errors

        """

        mapping_errors = []

        # Each mandatory column should appear in the mapping exactly once
        # The validator will catch the case where a mandatory column is missing
        # It's a dictionary so we cannot have duplicate keys

        # Field names should be unique
        field_names = []
        for field_name, mapped_column in column_mapping.items():
            if field_name in field_names:
                mapping_errors.append(
                    f"Field name '{field_name}' appears multiple times in the column mapping. Field names should be unique."
                )
            field_names.append(field_name)

        # Mapped column names should be unique
        rev_multidict = {}
        for field_name, mapped_column in column_mapping.items():
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


class AssignmentsUpload:
    """
    Class to represent the assignments data and run validations on it
    """

    def __init__(
        self,
        csv_string,
        column_mapping,
        survey_uid,
        form_uid,
        user_uid,
    ):
        try:
            self.col_names = self.__get_col_names(csv_string)
        except:
            raise
        self.survey_uid = survey_uid
        self.form_uid = form_uid
        self.user_uid = user_uid
        self.expected_columns = self.__build_expected_columns(column_mapping)
        self.assignments_df = self.__build_assignments_df(csv_string)

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
            column_mapping.target_id,
            column_mapping.enumerator_id,
        ]

        return expected_columns

    def __build_assignments_df(self, csv_string):
        """
        Method to create and format the assignments dataframe from the decoded csv file string
        """

        # Read the csv content into a dataframe
        assignments_df = pd.read_csv(
            io.StringIO(csv_string),
            dtype=str,
            keep_default_na=False,
        )

        # Override the column names in case there are duplicate column names
        # This is needed because pandas will append a .1 to the duplicate column name
        # Get column names from csv file using DictReader

        assignments_df.columns = self.col_names

        # Strip white space from all columns
        for index in range(assignments_df.shape[1]):
            assignments_df.iloc[:, index] = assignments_df.iloc[:, index].str.strip()

        # Replace empty strings with NaN
        assignments_df = assignments_df.replace("", np.nan)

        # Shift the index by 2 so that the row numbers start at 2 (to match the row numbers in the csv file)
        assignments_df.index += 2

        # Rename the index column to row_number
        assignments_df.index.name = "row_number"

        return assignments_df

    def __check_if_mapped_to_same_supervisor(
        self,
        target_id,
        surveyor_id,
        target_mappings,
        surveyor_mappings,
    ):
        """
        Function to check if the target is assigned to an enumerator mapped to the same supervisor
        """

        target_supervisor_uid = [s for t, s in target_mappings if t == target_id]
        surveyor_supervisor_uid = [s for e, s in surveyor_mappings if e == surveyor_id]

        return target_supervisor_uid == surveyor_supervisor_uid

    def validate_records(self, column_mapping, write_mode):
        """
        Method to run validations on the assignments data

        :param expected_columns: List of expected column names from the column mapping
        """

        file_structure_errors = []

        record_errors = {
            "summary": {
                "total_rows": len(self.assignments_df),
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
        file_columns = self.assignments_df.columns.to_list()
        for column_name in self.expected_columns:
            if file_columns.count(column_name) != 1:
                file_structure_errors.append(
                    f"Column name '{column_name}' from the column mapping appears {file_columns.count(column_name)} time(s) in the uploaded file. It should appear exactly once."
                )

        if len(file_structure_errors) > 0:
            raise InvalidFileStructureError(file_structure_errors)

        # Run validations on the records

        # Create an empty copy of the assignments dataframe to store the error messages for the invalid records
        invalid_records_df = self.assignments_df.copy()
        invalid_records_df["errors"] = ""

        # Mandatory columns should contain no blank fields
        non_null_columns = [
            column_mapping.enumerator_id,
            column_mapping.target_id,
        ]

        non_null_columns_df = self.assignments_df.copy()[
            self.assignments_df[non_null_columns].isnull().any(axis=1)
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
        duplicates_df = self.assignments_df.copy()[
            self.assignments_df.duplicated(keep=False)
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

        # The file should have no duplicate target IDs
        duplicates_df = self.assignments_df[
            self.assignments_df.duplicated(subset=column_mapping.target_id, keep=False)
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

        # If the write_mode is `merge`, the file can have target_id's that are already in the database

        # The file should contain no target_id's that are not in the database for that form
        target_id_query = Target.query.filter(
            Target.form_uid == self.form_uid,
        ).with_entities(
            Target.target_id,
        )
        invalid_target_id_df = self.assignments_df[
            ~self.assignments_df[column_mapping.target_id].isin(
                [row[0] for row in target_id_query.all()]
            )
        ]
        if len(invalid_target_id_df) > 0:
            record_errors["summary_by_error_type"].append(
                {
                    "error_type": "Invalid target_id's",
                    "error_message": f"The file contains {len(invalid_target_id_df)} target_id(s) that were not found in the uploaded targets data. The following row numbers contain invalid target_id's: {', '.join(str(row_number) for row_number in invalid_target_id_df.index.to_list())}",
                    "error_count": len(invalid_target_id_df),
                    "row_numbers_with_errors": invalid_target_id_df.index.to_list(),
                }
            )

            invalid_target_id_df[
                "errors"
            ] = "Target id not found in uploaded targets data for the form"
            invalid_records_df = invalid_records_df.merge(
                invalid_target_id_df["errors"],
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

        # The file should contain no target_id's that are not assignable at the moment
        not_assignable_target_id_query = (
            db.session.query(
                Target.target_id,
            )
            .join(
                TargetStatus,
                TargetStatus.target_uid == Target.target_uid,
            )
            .filter(
                Target.form_uid == self.form_uid,
                TargetStatus.target_assignable == False,
            )
        )

        not_assignable_target_id_df = self.assignments_df[
            self.assignments_df[column_mapping.target_id].isin(
                [row[0] for row in not_assignable_target_id_query.all()]
            )
        ]
        if len(not_assignable_target_id_df) > 0:
            record_errors["summary_by_error_type"].append(
                {
                    "error_type": "Not Assignable target_id's",
                    "error_message": f"The file contains {len(not_assignable_target_id_df)} target_id(s) that were not assignable for this form (most likely because they are complete). The following row numbers contain not assignable target_id's: {', '.join(str(row_number) for row_number in not_assignable_target_id_df.index.to_list())}",
                    "error_count": len(not_assignable_target_id_df),
                    "row_numbers_with_errors": not_assignable_target_id_df.index.to_list(),
                }
            )

            not_assignable_target_id_df[
                "errors"
            ] = "Target id not assignable for this form (most likely because they are complete)"
            invalid_records_df = invalid_records_df.merge(
                not_assignable_target_id_df["errors"],
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

        # The file should contain no enumerator_id's that are not in the database for that form
        enumerator_id_query = (
            db.session.query(Enumerator.enumerator_id, SurveyorForm.status)
            .join(
                SurveyorForm,
                Enumerator.enumerator_uid == SurveyorForm.enumerator_uid,
            )
            .filter(
                SurveyorForm.form_uid == self.form_uid,
            )
        )

        invalid_enumerator_id_df = self.assignments_df[
            ~self.assignments_df[column_mapping.enumerator_id].isin(
                [enumerator_id for enumerator_id, status in enumerator_id_query.all()]
            )
        ]
        if len(invalid_enumerator_id_df) > 0:
            record_errors["summary_by_error_type"].append(
                {
                    "error_type": "Invalid enumerator_id's",
                    "error_message": f"The file contains {len(invalid_enumerator_id_df)} enumerator_id(s) that were not found in the uploaded enumerators data. The following row numbers contain invalid enumerator_id's: {', '.join(str(row_number) for row_number in invalid_enumerator_id_df.index.to_list())}",
                    "error_count": len(invalid_enumerator_id_df),
                    "row_numbers_with_errors": invalid_enumerator_id_df.index.to_list(),
                }
            )

            invalid_enumerator_id_df[
                "errors"
            ] = "Enumerator id not found in uploaded enumerators data for the form"
            invalid_records_df = invalid_records_df.merge(
                invalid_enumerator_id_df["errors"],
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

        dropout_enumerator_id_df = self.assignments_df[
            self.assignments_df[column_mapping.enumerator_id].isin(
                [
                    enumerator_id
                    for enumerator_id, status in enumerator_id_query.all()
                    if status == "Dropout"
                ]
            )
        ]
        if len(dropout_enumerator_id_df) > 0:
            record_errors["summary_by_error_type"].append(
                {
                    "error_type": "Dropout enumerator_id's",
                    "error_message": f"The file contains {len(dropout_enumerator_id_df)} enumerator_id(s) that have status 'Dropout' and are ineligible for assignment. The following row numbers contain dropout enumerator_id's: {', '.join(str(row_number) for row_number in dropout_enumerator_id_df.index.to_list())}",
                    "error_count": len(dropout_enumerator_id_df),
                    "row_numbers_with_errors": dropout_enumerator_id_df.index.to_list(),
                }
            )

            dropout_enumerator_id_df[
                "errors"
            ] = "Enumerator id has status 'Dropout' and are ineligible for assignment"
            invalid_records_df = invalid_records_df.merge(
                dropout_enumerator_id_df["errors"],
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

        # Mapping criteria based checks

        try:
            target_mapping = TargetMapping(self.form_uid)
            surveyor_mapping = SurveyorMapping(self.form_uid)
        except MappingError as e:
            raise e

        target_mappings = target_mapping.generate_mappings()
        target_mappings_query = select(
            Values(
                column("target_uid", Integer),
                column("supervisor_uid", Integer),
                name="mappings",
            ).data(
                [
                    (mapping["target_uid"], mapping["supervisor_uid"])
                    for mapping in target_mappings
                ]
                if len(target_mappings) > 0
                else [
                    (0, 0)
                ]  # If there are no mappings, we still need to return a row with 0 values
            )
        ).subquery()

        is_survey_admin = check_if_survey_admin(self.user_uid, self.survey_uid)
        child_users_with_supervisors_query = build_child_users_with_supervisors_query(
            self.user_uid,
            self.survey_uid,
            target_mapping.bottom_level_role_uid,
            is_survey_admin,
        )

        targets_mapped_to_current_user = (
            db.session.query(Target.target_id, target_mappings_query.c.supervisor_uid)
            .join(
                target_mappings_query,
                Target.target_uid == target_mappings_query.c.target_uid,
            )
            .join(
                child_users_with_supervisors_query,
                target_mappings_query.c.supervisor_uid
                == child_users_with_supervisors_query.c.user_uid,
            )
            .filter(
                Target.form_uid == self.form_uid,
            )
            .all()
        )

        surveyor_mappings = surveyor_mapping.generate_mappings()
        surveyor_mappings_query = select(
            Values(
                column("enumerator_uid", Integer),
                column("supervisor_uid", Integer),
                name="mappings",
            ).data(
                [
                    (mapping["enumerator_uid"], mapping["supervisor_uid"])
                    for mapping in surveyor_mappings
                ]
                if len(surveyor_mappings) > 0
                else [
                    (0, 0)
                ]  # If there are no mappings, we still need to return a row with 0 values
            )
        ).subquery()
        surveyors_mapped_to_current_user = (
            db.session.query(
                Enumerator.enumerator_id, surveyor_mappings_query.c.supervisor_uid
            )
            .join(
                surveyor_mappings_query,
                (Enumerator.enumerator_uid == surveyor_mappings_query.c.enumerator_uid)
                & (Enumerator.form_uid == self.form_uid),
            )
            .join(
                child_users_with_supervisors_query,
                surveyor_mappings_query.c.supervisor_uid
                == child_users_with_supervisors_query.c.user_uid,
            )
            .all()
        )

        # Check each target is assignable by the current supervisor as per the mappings
        not_mapped_to_current_user_df = self.assignments_df[
            ~self.assignments_df[column_mapping.target_id].isin(
                [
                    target_id
                    for target_id, supervisor_uid in targets_mapped_to_current_user
                ]
            )
            & self.assignments_df[column_mapping.target_id].isin(
                [row[0] for row in target_id_query.all()]
            )  # Only check targets that are in the database
        ]
        if len(not_mapped_to_current_user_df) > 0:
            record_errors["summary_by_error_type"].append(
                {
                    "error_type": "Not mapped target_id's",
                    "error_message": f"The file contains {len(not_mapped_to_current_user_df)} target_id(s) that are not mapped to current logged in user and hence cannot be assigned by this user. The following row numbers contain such target_id's: {', '.join(str(row_number) for row_number in not_mapped_to_current_user_df.index.to_list())}",
                    "error_count": len(not_mapped_to_current_user_df),
                    "row_numbers_with_errors": not_mapped_to_current_user_df.index.to_list(),
                }
            )

            not_mapped_to_current_user_df[
                "errors"
            ] = "Target is not mapped to current logged in user and hence cannot be assigned"
            invalid_records_df = invalid_records_df.merge(
                not_mapped_to_current_user_df["errors"],
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

        # Check if enumerator is mapped to the same supervisor as the target
        not_mapped_to_same_supervisor_df = self.assignments_df[
            ~self.assignments_df.apply(
                lambda x: self.__check_if_mapped_to_same_supervisor(
                    x[column_mapping.target_id],
                    x[column_mapping.enumerator_id],
                    targets_mapped_to_current_user,
                    surveyors_mapped_to_current_user,
                ),
                axis=1,
            )
            & self.assignments_df[column_mapping.target_id].isin(
                [row[0] for row in target_id_query.all()]
            )  # Only check targets that are in the database
            & self.assignments_df[column_mapping.enumerator_id].isin(
                [enumerator_id for enumerator_id, status in enumerator_id_query.all()]
            )  # Only check enumerators that are in the database
        ]

        if len(not_mapped_to_same_supervisor_df) > 0:
            record_errors["summary_by_error_type"].append(
                {
                    "error_type": "Incorrectly mappings target_id's",
                    "error_message": f"The file contains {len(not_mapped_to_same_supervisor_df)} target_id(s) that are assigned to enumerators mapped to a different supervisor. The following row numbers contain such target_id's: {', '.join(str(row_number) for row_number in not_mapped_to_same_supervisor_df.index.to_list())}",
                    "error_count": len(not_mapped_to_same_supervisor_df),
                    "row_numbers_with_errors": not_mapped_to_same_supervisor_df.index.to_list(),
                }
            )

            not_mapped_to_same_supervisor_df[
                "errors"
            ] = "Target is assigned to an enumerator mapped to a different supervisor"
            invalid_records_df = invalid_records_df.merge(
                not_mapped_to_same_supervisor_df["errors"],
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
            raise InvalidAssignmentRecordsError(record_errors)

        return

    def save_records(self, column_mapping, write_mode):
        """
        Method to save the assignments data to the database
        """

        ####################################################################
        # Prepare a list of the assignment records to insert into the database
        ####################################################################

        # Order the columns in the dataframe so we can easily access them by index
        self.assignments_df = self.assignments_df[self.expected_columns]

        ####################################################################
        # Use the list of assignment records to write to the database
        ####################################################################

        records_to_write = [
            row for row in self.assignments_df.drop_duplicates().itertuples()
        ]

        if write_mode == "overwrite":
            # Delete all existing assignments for the form
            subquery = db.session.query(Target.target_uid).filter(
                Target.form_uid == self.form_uid
            )

            db.session.query(SurveyorAssignment).filter(
                SurveyorAssignment.target_uid.in_(subquery)
            ).update(
                {
                    SurveyorAssignment.user_uid: current_user.user_uid,
                    SurveyorAssignment.to_delete: 1,
                },
                synchronize_session=False,
            )

            db.session.query(SurveyorAssignment).filter(
                SurveyorAssignment.target_uid.in_(subquery)
            ).delete(synchronize_session=False)

            db.session.commit()

        re_assignments_count = 0
        new_assignments_count = 0
        no_changes_count = 0

        for assignment_record in records_to_write:
            # get the target_uid and enumerator_uid
            target_uid = (
                db.session.query(Target.target_uid)
                .filter(
                    Target.form_uid == self.form_uid,
                    Target.target_id == assignment_record[1],
                )
                .first()
                .target_uid
            )
            enumerator_uid = (
                db.session.query(Enumerator.enumerator_uid)
                .filter(
                    Enumerator.form_uid == self.form_uid,
                    Enumerator.enumerator_id == assignment_record[2],
                )
                .first()
                .enumerator_uid
            )

            # query existing assignments for the same target_uid
            assignment_res = (
                db.session.query(SurveyorAssignment)
                .filter(
                    SurveyorAssignment.target_uid == target_uid,
                )
                .first()
            )

            if assignment_res is None:
                # update new_assignments - no record was found for the target
                new_assignments_count += 1
            elif assignment_res.enumerator_uid == enumerator_uid:
                # update no_changes - the enumerator_id has not changed for the target found
                no_changes_count += 1
            else:
                # update re_assignment - the enumerator_id has changed
                re_assignments_count += 1

            # do upsert
            statement = (
                pg_insert(SurveyorAssignment)
                .values(
                    target_uid=target_uid,
                    enumerator_uid=enumerator_uid,
                    user_uid=current_user.user_uid,
                )
                .on_conflict_do_update(
                    constraint="pk_surveyor_assignments",
                    set_={
                        "enumerator_uid": enumerator_uid,
                        "user_uid": current_user.user_uid,
                    },
                )
            )

            db.session.execute(statement)

        db.session.commit()

        response_data = {
            "re_assignments_count": re_assignments_count,
            "new_assignments_count": new_assignments_count,
            "no_changes_count": no_changes_count,
            "assignments_count": len(records_to_write),
        }

        return response_data


def get_next_assignment_email_schedule(form_uid):
    """
    Function to fetch the next assignment email schedule for the given form_uid

    """

    # Get current datetime and current time
    current_datetime = datetime.now()
    current_time = datetime.now().strftime("%H:%M")

    # a subquery to unnest the array of dates and filter dates less than current date
    subquery = (
        db.session.query(
            cast(func.unnest(EmailSchedule.dates) + EmailSchedule.time, Date).label(
                "schedule_date"
            ),
            EmailSchedule.email_schedule_uid,
        )
        .filter(
            func.DATE(current_datetime) <= func.ANY(EmailSchedule.dates),
        )
        .correlate(EmailSchedule)
        .subquery()
    )

    # Alias the subquery
    schedule_dates_subquery = alias(subquery)

    # join schedule_dates_subquery and filter dates only greater than current date time
    email_schedule_res = (
        db.session.query(EmailSchedule, EmailConfig, schedule_dates_subquery)
        .select_from(EmailSchedule)
        .join(
            schedule_dates_subquery,
            and_(
                schedule_dates_subquery.c.email_schedule_uid
                == EmailSchedule.email_schedule_uid,
                cast(
                    schedule_dates_subquery.c.schedule_date + EmailSchedule.time,
                    DateTime,
                )
                >= current_datetime,
            ),
        )
        .join(
            EmailConfig, EmailSchedule.email_config_uid == EmailConfig.email_config_uid
        )
        .filter(
            EmailConfig.form_uid == form_uid,
            func.lower(EmailConfig.config_name) == "assignments",
        )
        .order_by(schedule_dates_subquery.c.schedule_date.asc())
        .first()
    )

    if email_schedule_res:
        (
            email_schedule,
            email_config,
            schedule_date,
            email_schedule_uid,
        ) = email_schedule_res

        return {
            "email_config_uid": email_config.email_config_uid,
            "config_name": email_config.config_name,
            "dates": email_schedule.dates,
            "time": str(email_schedule.time),
            "current_time": str(current_time),
            "email_schedule_uid": email_schedule_uid,
            "schedule_date": schedule_date,
        }

    return None
