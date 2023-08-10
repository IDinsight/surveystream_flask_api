import io
import pandas as pd
import numpy as np
from csv import DictReader
from app.blueprints.surveys.models import Survey
from app.blueprints.locations.models import Location
from .models import Enumerator
from .errors import (
    HeaderRowEmptyError,
    InvalidEnumeratorsError,
    InvalidColumnMappingError,
)


class EnumeratorColumnMapping:
    """
    Class to represent the enumerator column mapping and run validations on it
    """

    def __init__(self, column_mapping, prime_geo_level_uid, geo_levels):
        try:
            self.__validate_column_mapping(
                column_mapping, prime_geo_level_uid, geo_levels
            )
            self.enumerator_id = column_mapping["enumerator_id"]
            self.first_name = column_mapping["first_name"]
            self.middle_name = column_mapping["middle_name"]
            self.last_name = column_mapping["last_name"]
            self.email = column_mapping["email"]
            self.mobile_primary = column_mapping["mobile_primary"]
            self.language = column_mapping["language"]
            self.home_address = column_mapping["home_address"]
            self.gender = column_mapping["gender"]
            self.enumerator_type = column_mapping["enumerator_type"]

            if column_mapping.get("location_id_column"):
                self.location_id_column = column_mapping["location_id_column"]

            if column_mapping.get("custom_fields"):
                self.custom_fields = column_mapping["custom_fields"]

        except:
            raise

    def __validate_column_mapping(
        self, column_mapping, prime_geo_level_uid, geo_levels
    ):
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
        duplicates = [key for key, values in rev_multidict.items() if len(values) > 1]
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

    def __init__(self, csv_string):
        try:
            self.col_names = self.__get_col_names(csv_string)
        except:
            raise
        self.enumerators_df = self.__build_enumerators_df(csv_string)

    def __get_col_names(self, csv_string):
        col_names = DictReader(io.StringIO(csv_string)).fieldnames
        if len(col_names) == 0:
            raise HeaderRowEmptyError(
                "Column names were not found in the file. Make sure the first row of the file contains column names."
            )

        return col_names

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

        # Shift the index by 1 so that the row numbers start at 1
        enumerators_df.index += 1

        # Rename the index column to row_number
        enumerators_df.index.name = "row_number"

        return enumerators_df

    def validate_records(
        self, expected_columns, column_mapping, form, prime_geo_level_uid, mode
    ):
        """
        Method to run validations on the locations data

        :param expected_columns: List of expected column names from the column mapping
        """

        file_errors = []

        # Each mapped column should appear in the csv file exactly once
        file_columns = self.enumerators_df.columns.to_list()
        for column_name in expected_columns:
            if file_columns.count(column_name) != 1:
                file_errors.append(
                    f"Column name '{column_name}' from the column mapping appears {file_columns.count(column_name)} times in the uploaded file. It should appear exactly once."
                )

        # Each column in the csv file should be mapped exactly once
        for column_name in file_columns:
            if expected_columns.count(column_name) != 1:
                file_errors.append(
                    f"Column name '{column_name}' in the csv file appears {expected_columns.count(column_name)} times in the column mapping. It should appear exactly once."
                )

        # The file should contain no blank fields
        # TODO restrict this to mandatory fields only
        # blank_fields = [
        #     f"'column': {self.enumerators_df.columns[j]}, 'row': {i + 1}"
        #     for i, j in zip(*np.where(pd.isnull(self.enumerators_df)))
        # ]
        # if len(blank_fields) > 0:
        #     blank_fields_formatted = "\n".join(item for item in blank_fields)
        #     file_errors.append(
        #         f"The file contains {len(blank_fields)} blank fields. Blank fields are not allowed. Blank fields are found in the following columns and rows:\n{blank_fields_formatted}"
        #     )

        # The file should have no duplicate rows
        duplicates_df = self.enumerators_df[self.enumerators_df.duplicated(keep=False)]
        if len(duplicates_df) > 0:
            file_errors.append(
                f"The file has {len(duplicates_df)} duplicate rows. Duplicate rows are not allowed. The following rows are duplicates:\n{duplicates_df.to_string()}"
            )

        # The file should have no duplicate enumerator IDs
        duplicates_df = self.enumerators_df[
            self.enumerators_df.duplicated(subset="enumerator_id", keep=False)
        ]
        if len(duplicates_df) > 0:
            file_errors.append(
                f"The file has {len(duplicates_df)} duplicate enumerator_id's. The following rows have duplicates on enumerator_id:\n{duplicates_df.to_string()}"
            )

        # If the mode is `append`, the file should have no enumerator_id's that are already in the database
        if mode == "append":
            enumerator_id_query = (
                Enumerator.query.filter(
                    Enumerator.form_uid == form.form_uid,
                )
                .with_entities(Enumerator.enumerator_id)
                .distinct()
            )
            invalid_enumerator_id_df = self.enumerators_df[
                self.enumerators_df["enumerator_id"].isin(
                    [row[0] for row in enumerator_id_query.all()]
                )
            ]
            if len(invalid_enumerator_id_df) > 0:
                file_errors.append(
                    f"The file contains {len(invalid_enumerator_id_df)} enumerator_id's that are already in the database. The following rows have enumerator_id's that are already in the database:\n{invalid_enumerator_id_df.to_string()}"
                )

        # If the location_id_column is mapped, the file should contain no location_id's that are not in the database
        if hasattr(column_mapping, "location_id_column"):
            location_id_query = (
                Location.query.filter(
                    Location.survey_uid == form.survey_uid,
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
                file_errors.append(
                    f"The file contains {len(invalid_location_id_df)} invalid location_id's. The following rows have location_id's that were not found in the locations data for the given survey and prime geo level:\n{invalid_location_id_df.to_string()}"
                )

        if len(file_errors) > 0:
            raise InvalidEnumeratorsError(file_errors)

        return
