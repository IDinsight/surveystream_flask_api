import base64
import io
import pandas as pd
import numpy as np


def run_location_mapping_validations(geo_levels, geo_level_mapping):
    """
    Function to run validations on the location type column mapping and return a list of errors

    :param geo_levels: List of geo levels for the survey from the database
    :param geo_level_mapping: List of geo level column mappings from the request payload
    """

    mapping_errors = []

    # Each geo level should appear in the mapping exactly once
    for geo_level in geo_levels:
        geo_level_mapping_count = 0
        for mapping in geo_level_mapping:
            if geo_level.geo_level_uid == mapping["geo_level_uid"]:
                geo_level_mapping_count += 1
        if geo_level_mapping_count != 1:
            mapping_errors.append(
                f"Each location type defined in the location type hierarchy should appear exactly once in the location type column mapping. Location type '{geo_level.geo_level_name}' appears {geo_level_mapping_count} times in the location type mapping."
            )

    # Each geo level in the mapping should be one of the geo levels for the survey
    for mapping in geo_level_mapping:
        if mapping["geo_level_uid"] not in [
            geo_level.geo_level_uid for geo_level in geo_levels
        ]:
            mapping_errors.append(
                f"Location type '{mapping['geo_level_uid']}' in the location type column mapping is not one of the location types for the survey."
            )

    # Mapped column names should be unique
    column_names = []
    for mapping in geo_level_mapping:
        if mapping["location_id_column"] in column_names:
            mapping_errors.append(
                f"Column name '{mapping['location_id_column']}' appears more than once in the location type column mapping. Column names should be unique."
            )
        if mapping["location_name_column"] in column_names:
            mapping_errors.append(
                f"Column name '{mapping['location_name_column']}' appears more than once in the location type column mapping. Column names should be unique."
            )
        column_names.append(mapping["location_id_column"])
        column_names.append(mapping["location_name_column"])

    return mapping_errors


def build_locations_df(csv_string, col_names):
    """
    Function to create and format the locations dataframe from the decoded csv file string

    :param base64_file_content: Base64-encoded csv file content from the request payload
    """

    # Read the csv content into a dataframe
    locations_df = pd.read_csv(
        io.StringIO(csv_string),
        dtype=str,
        keep_default_na=False,
    )

    # Override the column names in case there are duplicate column names
    # This is needed because pandas will append a .1 to the duplicate column name
    # Get column names from csv file using DictReader

    locations_df.columns = col_names

    # Strip white space from all columns
    for index in range(locations_df.shape[1]):
        locations_df.iloc[:, index] = locations_df.iloc[:, index].str.strip()

    # Replace empty strings with NaN
    locations_df = locations_df.replace("", np.nan)

    # Shift the index by 1 so that the row numbers start at 1
    locations_df.index += 1

    # Rename the index column to row_number
    locations_df.index.name = "row_number"

    return locations_df


def run_locations_file_validations(
    locations_df, expected_columns, ordered_geo_levels, geo_level_mapping_lookup
):
    """
    Function to run validations on the locations file and return a list of errors

    :param locations_df: Locations dataframe
    :param expected_columns: List of expected column names from the column mapping
    :param ordered_geo_levels: List of geo levels for the survey from the database in descending order based on the location type hierarchy
    :param geo_level_mapping_lookup: Dictionary of geo level column mappings from the request payload keyed by geo level uid
    """

    file_errors = []

    # Each mapped column should appear in the csv file exactly once
    file_columns = locations_df.columns.to_list()
    for column_name in expected_columns:
        if file_columns.count(column_name) != 1:
            file_errors.append(
                f"Column name '{column_name}' from the column mapping appears {file_columns.count(column_name)} times in the uploaded file. It should appear exactly once."
            )

    # Each column in the csv file should be mapped exactly once
    for column_name in file_columns:
        if expected_columns.count(column_name) != 1:
            file_errors.append(
                f"Column name '{column_name}' in the csv file appears {expected_columns.count(column_name)} times in the location type column mapping. It should appear exactly once."
            )

    # The file should contain no blank fields
    blank_fields = [
        f"'column': {locations_df.columns[j]}, 'row': {i + 1}"
        for i, j in zip(*np.where(pd.isnull(locations_df)))
    ]
    if len(blank_fields) > 0:
        blank_fields_formatted = "\n".join(item for item in blank_fields)
        file_errors.append(
            f"The file contains {len(blank_fields)} blank fields. Blank fields are not allowed. Blank fields are found in the following columns and rows:\n{blank_fields_formatted}"
        )

    # The file should have no duplicate rows
    duplicates_df = locations_df[locations_df.duplicated(keep=False)]
    if len(duplicates_df) > 0:
        file_errors.append(
            f"The file has {len(duplicates_df)} duplicate rows. Duplicate rows are not allowed. The following rows are duplicates:\n{duplicates_df.to_string()}"
        )

    # A location cannot be assigned to multiple parents
    for geo_level in reversed(ordered_geo_levels):
        if geo_level.parent_geo_level_uid is not None:
            geo_level_id_column_name = geo_level_mapping_lookup[
                geo_level.geo_level_uid
            ]["location_id_column"]
            parent_geo_level_id_column_name = geo_level_mapping_lookup[
                geo_level.parent_geo_level_uid
            ]["location_id_column"]
            # If we deduplicate on the parent location id column and the location id column, the number of rows should be the same as just deduplicating on the location id column
            # If this check fails we know that the location id column has locations that are mapped to more than one parent
            if len(
                locations_df[
                    locations_df.duplicated(
                        subset=[
                            parent_geo_level_id_column_name,
                            geo_level_id_column_name,
                        ],
                    )
                ]
            ) != len(
                locations_df[
                    locations_df.duplicated(
                        subset=[geo_level_id_column_name],
                    )
                ]
            ):
                file_errors.append(
                    f"Location type {geo_level.geo_level_name} has location id's that are mapped to more than one parent location in column {parent_geo_level_id_column_name}. A location (defined by the location id column) cannot be assigned to multiple parents. Make sure to use a unique location id for each location. The following rows have location id's that are mapped to more than one parent location:\n{locations_df[locations_df.drop_duplicates(subset=[parent_geo_level_id_column_name, geo_level_id_column_name]).duplicated(subset=[geo_level_id_column_name], keep=False).reindex(locations_df.index, fill_value=False)].to_string()}"
                )

    return file_errors
