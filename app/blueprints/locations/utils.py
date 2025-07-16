import io
from csv import DictReader

import numpy as np
import pandas as pd

from .errors import (
    HeaderRowEmptyError,
    InvalidGeoLevelHierarchyError,
    InvalidGeoLevelMappingError,
    InvalidLocationsError,
)


class GeoLevelHierarchy:
    """
    Class to represent the geo level hierarchy and run validations on it
    """

    def __init__(self, geo_levels):
        self.geo_levels = geo_levels

        try:
            self.__validate_hierarchy()
        except:
            raise

        self.ordered_geo_levels = self.__get_ordered_geo_levels()

    def __get_ordered_geo_levels(self):
        """
        Method to create an ordered list of geo levels based on the geo level hierarchy
        This method assumes that the geo level hierarchy has been validated
        """
        ordered_geo_levels = [
            geo_level
            for geo_level in self.geo_levels
            if geo_level.parent_geo_level_uid is None
        ]
        for i in range(len(self.geo_levels) - 1):
            for geo_level in self.geo_levels:
                if (
                    geo_level.parent_geo_level_uid
                    == ordered_geo_levels[i].geo_level_uid
                ):
                    ordered_geo_levels.append(geo_level)

        return ordered_geo_levels

    def __validate_hierarchy(self):
        """
        Method to run validations on the geo level hierarchy and raise an exception containing a list of errors
        """
        errors_list = []

        # Prechecks before we validate the tree

        # There should be at least one geo level
        if len(self.geo_levels) == 0:
            errors_list.append(
                "Cannot create the location type hierarchy because no location types have been defined for the survey."
            )
            raise InvalidGeoLevelHierarchyError(errors_list)

        # There should be no duplicates on geo_level_uid
        geo_level_uids = [geo_level.geo_level_uid for geo_level in self.geo_levels]

        for geo_level_uid in geo_level_uids:
            if geo_level_uids.count(geo_level_uid) > 1:
                error_message = f"Each location type unique id defined in the location type hierarchy should appear exactly once in the hierarchy. Location type with geo_level_uid='{geo_level_uid}' appears {geo_level_uids.count(geo_level_uid)} times in the hierarchy."

                if error_message not in errors_list:
                    errors_list.append(error_message)

        # There should be no duplicates on geo_level_name
        geo_level_names = [geo_level.geo_level_name for geo_level in self.geo_levels]
        for geo_level_name in geo_level_names:
            if geo_level_names.count(geo_level_name) > 1:
                error_message = f"Each location type name defined in the location type hierarchy should appear exactly once in the hierarchy. Location type with geo_level_name='{geo_level_name}' appears {geo_level_names.count(geo_level_name)} times in the hierarchy."

                if error_message not in errors_list:
                    errors_list.append(error_message)

        if len(errors_list) > 0:
            raise InvalidGeoLevelHierarchyError(errors_list)

        # Now validate the tree

        # Exactly one geo level should have no parent
        root_nodes = [
            geo_level
            for geo_level in self.geo_levels
            if geo_level.parent_geo_level_uid is None
        ]

        if len(root_nodes) == 0:
            errors_list.append(
                f"The hierarchy should have exactly one top level location type (ie, a location type with no parent). The current hierarchy has 0 location types with no parent."
            )
            raise InvalidGeoLevelHierarchyError(errors_list)
        elif len(root_nodes) > 1:
            errors_list.append(
                f"The hierarchy should have exactly one top level location type (ie, a location type with no parent). The current hierarchy has {len(root_nodes)} location types with no parent:\n{', '.join([geo_level.geo_level_name for geo_level in root_nodes])}"
            )
            raise InvalidGeoLevelHierarchyError(errors_list)

        # Traverse the tree to validate the following:
        # 1. Each location type should have at most one child location type
        # 2. The location type hierarchy should not have any cycles
        # 3. There are no location types that couldn't be visited from the top level location type (graph is connected)
        root_node = root_nodes[0]
        visited_nodes = [root_node]

        while True:
            child_nodes = [
                geo_level
                for geo_level in self.geo_levels
                if geo_level.parent_geo_level_uid == visited_nodes[-1].geo_level_uid
            ]

            if len(child_nodes) > 1:
                errors_list.append(
                    f"Each location type should have at most one child location type. Location type '{visited_nodes[-1].geo_level_name}' has {len(child_nodes)} child location types:\n{', '.join([geo_level.geo_level_name for geo_level in child_nodes])}"
                )
                raise InvalidGeoLevelHierarchyError(errors_list)
            elif len(child_nodes) == 1:
                if child_nodes[0].geo_level_uid in [
                    geo_level.geo_level_uid for geo_level in visited_nodes
                ]:
                    errors_list.append(
                        f"The location type hierarchy should not have any cycles. The current hierarchy has a cycle starting with location type '{child_nodes[0].geo_level_name}'."
                    )
                    raise InvalidGeoLevelHierarchyError(errors_list)
                visited_nodes.append(child_nodes[0])
            elif len(child_nodes) == 0:
                break

        # Now check that all nodes were visited
        if len(visited_nodes) != len(self.geo_levels):
            unvisited_nodes = [
                geo_level
                for geo_level in self.geo_levels
                if geo_level.geo_level_uid
                not in [visited_node.geo_level_uid for visited_node in visited_nodes]
            ]

            errors_list.append(
                f"All location types in the hierarchy should be able to be connected back to the top level location type via a chain of parent location type references. The current hierarchy has {len(unvisited_nodes)} location types that cannot be connected:\n{', '.join([geo_level.geo_level_name for geo_level in unvisited_nodes])}"
            )

            # Attempt to diagnose the unvisited nodes
            # Not exhaustive of all issues
            for geo_level in unvisited_nodes:
                # Check for self-referencing
                if geo_level.parent_geo_level_uid == geo_level.geo_level_uid:
                    errors_list.append(
                        f"Location type '{geo_level.geo_level_name}' is referenced as its own parent. Self-referencing is not allowed."
                    )

                # Check for parent referencing a non-existent geo level
                elif geo_level.parent_geo_level_uid not in [
                    geo_level.geo_level_uid for geo_level in self.geo_levels
                ]:
                    errors_list.append(
                        f"Location type '{geo_level.geo_level_name}' references a parent location type with unique id '{geo_level.parent_geo_level_uid}' that is not found in the hierarchy."
                    )

        if len(errors_list) > 0:
            raise InvalidGeoLevelHierarchyError(errors_list)

        return


class LocationColumnMapping:
    """
    Class to represent the location column mapping and run validations on it
    """

    def __init__(self, geo_levels, column_mapping):
        try:
            self.__validate_column_mapping(geo_levels, column_mapping)
        except:
            raise

        self.geo_level_mapping_lookup = {
            mapping["geo_level_uid"]: mapping for mapping in column_mapping
        }

    def get_by_uid(self, geo_level_uid):
        """
        Method to return the column mapping for a given geo level uid
        """
        return self.geo_level_mapping_lookup[geo_level_uid]

    def __validate_column_mapping(self, geo_levels, column_mapping):
        """
        Method to run validations on the location column mapping and raise an exception containing a list of errors

        :param geo_levels: List of geo levels for the survey from the database
        :param column_mapping: List of geo level column mappings from the request payload
        """

        mapping_errors = []

        # Each geo level should appear in the mapping exactly once
        for geo_level in geo_levels:
            geo_level_mapping_count = 0
            for mapping in column_mapping:
                if geo_level.geo_level_uid == mapping["geo_level_uid"]:
                    geo_level_mapping_count += 1
            if geo_level_mapping_count != 1:
                mapping_errors.append(
                    f"Each location type defined in the location type hierarchy should appear exactly once in the location type column mapping. Location type '{geo_level.geo_level_name}' appears {geo_level_mapping_count} times in the location type mapping."
                )

        # Each geo level in the mapping should be one of the geo levels for the survey
        for mapping in column_mapping:
            if mapping["geo_level_uid"] not in [
                geo_level.geo_level_uid for geo_level in geo_levels
            ]:
                mapping_errors.append(
                    f"Location type '{mapping['geo_level_uid']}' in the location type column mapping is not one of the location types for the survey."
                )

        # Mapped column names should be unique
        column_names = []
        for mapping in column_mapping:
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

        if len(mapping_errors) > 0:
            raise InvalidGeoLevelMappingError(mapping_errors)

        return


class LocationsUpload:
    """
    Class to represent the locations data and run validations on it
    """

    def __init__(self, csv_string):
        try:
            self.col_names = self.__get_col_names(csv_string)
        except HeaderRowEmptyError as e:
            raise e
        self.locations_df = self.__build_locations_df(csv_string)

    def __get_col_names(self, csv_string):
        col_names = DictReader(io.StringIO(csv_string)).fieldnames
        if len(col_names) == 0:
            raise HeaderRowEmptyError(
                "Column names were not found in the file. Make sure the first row of the file contains column names."
            )

        return col_names

    def __build_locations_df(self, csv_string):
        """
        Method to create and format the locations dataframe from the decoded csv file string
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

        locations_df.columns = self.col_names

        # Strip white space from all columns
        for index in range(locations_df.shape[1]):
            locations_df.iloc[:, index] = locations_df.iloc[:, index].str.strip()

        # Replace empty strings with NaN
        locations_df = locations_df.replace("", np.nan)

        # Shift the index by 2 so that the row numbers start at 2 (1 is reserved for the header row)
        locations_df.index += 2

        # Rename the index column to row_number
        locations_df.index.name = "row_number"

        return locations_df

    def validate_records(
        self,
        expected_columns,
        ordered_geo_levels,
        geo_level_mapping_lookup,
        existing_location_df=None,
    ):
        """
        Method to run validations on the locations data

        :param expected_columns: List of expected column names from the column mapping
        :param ordered_geo_levels: List of geo levels for the survey from the database in descending order based on the location type hierarchy
        :param geo_level_mapping_lookup: Dictionary of geo level column mappings from the request payload keyed by geo level uid
        """
        record_errors = {"summary_by_error_type": []}

        file_columns = self.locations_df.columns.to_list()

        # 1. Each mapped column should appear in the csv file exactly once
        for column_name in expected_columns:
            count = file_columns.count(column_name)
            if count != 1:
                record_errors["summary_by_error_type"].append(
                    {
                        "error_type": "Column mapping error",
                        "error_message": f"Column name '{column_name}' from the column mapping appears {count} time(s) in the uploaded file. It should appear exactly once.",
                        "error_count": "1",
                        "row_numbers_with_errors": [],
                    }
                )

        # 2. The file should contain no blank fields
        blank_fields = [
            (self.locations_df.columns[j], i)
            for i, j in zip(*np.where(pd.isnull(self.locations_df)))
        ]
        if len(blank_fields) > 0:
            columns = set([col for col, _ in blank_fields])
            rows = sorted(set([int(row) + 2 for _, row in blank_fields]))
            record_errors["summary_by_error_type"].append(
                {
                    "error_type": "Blank field",
                    "error_message": f"Blank values are not allowed in the following columns: {', '.join(sorted(columns))}. Blank values in these columns were found for the following row(s): {', '.join(str(r) for r in rows)}",
                    "error_count": str(len(blank_fields)),
                    "row_numbers_with_errors": rows,
                }
            )

        # 3. The file should have no duplicate rows
        duplicates_df = self.locations_df[self.locations_df.duplicated(keep=False)]
        if len(duplicates_df) > 0:
            record_errors["summary_by_error_type"].append(
                {
                    "error_type": "Duplicate rows",
                    "error_message": f"The file has {len(duplicates_df)} duplicate row(s). Duplicate rows are not allowed. The following row numbers are duplicates: {', '.join(str(row_number) for row_number in duplicates_df.index.to_list())}",
                    "error_count": str(len(duplicates_df)),
                    "row_numbers_with_errors": duplicates_df.index.astype(
                        int
                    ).to_list(),
                }
            )

        # 4. Duplicate rows with existing data (for append)
        if existing_location_df is not None:
            intersection_df = pd.merge(
                self.locations_df,
                existing_location_df,
                how="inner",
                on=expected_columns,
                suffixes=("_uploaded", "_existing"),
            )
            if not intersection_df.empty:
                rows = [int(row) + 2 for row in intersection_df.index]
                record_errors["summary_by_error_type"].append(
                    {
                        "error_type": "Duplicate with existing data",
                        "error_message": f"The uploaded file has some rows that already exist in SurveyStream. The following row numbers in the uploaded file are duplicates of existing data: {', '.join(str(r) for r in rows)}",
                        "error_count": str(len(rows)),
                        "row_numbers_with_errors": rows,
                    }
                )
            combined_df = pd.concat([self.locations_df, existing_location_df])
            combined_df.reset_index(inplace=True, drop=True)
        else:
            combined_df = self.locations_df

        # 5. A location (defined by location_id) cannot be assigned to multiple parents
        for geo_level in reversed(ordered_geo_levels):
            if geo_level.parent_geo_level_uid is not None:
                geo_level_id_column_name = geo_level_mapping_lookup[
                    geo_level.geo_level_uid
                ]["location_id_column"]
                parent_geo_level_id_column_name = geo_level_mapping_lookup[
                    geo_level.parent_geo_level_uid
                ]["location_id_column"]
                if len(
                    combined_df[
                        combined_df.duplicated(
                            subset=[
                                parent_geo_level_id_column_name,
                                geo_level_id_column_name,
                            ],
                        )
                    ]
                ) != len(
                    combined_df[
                        combined_df.duplicated(
                            subset=[geo_level_id_column_name],
                        )
                    ]
                ):
                    error_rows = (
                        combined_df[
                            combined_df.drop_duplicates(
                                subset=[
                                    parent_geo_level_id_column_name,
                                    geo_level_id_column_name,
                                ]
                            )
                            .duplicated(subset=[geo_level_id_column_name], keep=False)
                            .reindex(combined_df.index, fill_value=False)
                        ]
                        .index.astype(int)
                        .to_list()
                    )
                    record_errors["summary_by_error_type"].append(
                        {
                            "error_type": "Location assigned to multiple parents",
                            "error_message": f"Location type {geo_level.geo_level_name} has location id's that are mapped to more than one parent location in column {parent_geo_level_id_column_name}. The following rows have location id's that are mapped to more than one parent location: {', '.join(str(r) for r in error_rows)}",
                            "error_count": str(len(error_rows)),
                            "row_numbers_with_errors": error_rows,
                        }
                    )

        # 6. A location (defined by location_id) cannot have multiple location names
        for geo_level in reversed(ordered_geo_levels):
            geo_level_id_column_name = geo_level_mapping_lookup[
                geo_level.geo_level_uid
            ]["location_id_column"]
            geo_level_name_column_name = geo_level_mapping_lookup[
                geo_level.geo_level_uid
            ]["location_name_column"]
            if len(
                combined_df[
                    combined_df.duplicated(
                        subset=[geo_level_id_column_name, geo_level_name_column_name],
                    )
                ]
            ) != len(
                combined_df[
                    combined_df.duplicated(
                        subset=[geo_level_id_column_name],
                    )
                ]
            ):
                error_rows = (
                    combined_df[
                        combined_df.drop_duplicates(
                            subset=[
                                geo_level_id_column_name,
                                geo_level_name_column_name,
                            ]
                        )
                        .duplicated(subset=[geo_level_id_column_name], keep=False)
                        .reindex(combined_df.index, fill_value=False)
                    ]
                    .index.astype(int)
                    .to_list()
                )
                record_errors["summary_by_error_type"].append(
                    {
                        "error_type": "Location id with multiple names",
                        "error_message": f"Location type {geo_level.geo_level_name} has location id's that have more than one location name. The following rows have location id's that have more than one location name: {', '.join(str(r) for r in error_rows)}",
                        "error_count": str(len(error_rows)),
                        "row_numbers_with_errors": error_rows,
                    }
                )

        if len(record_errors["summary_by_error_type"]) > 0:
            raise InvalidLocationsError(record_errors)

        return


class GeoLevelPayloadItem:
    """
    Utility class used to convert a geo level payload dictionary into an object
    This is needed because the GeoLevelHierarchy class expects a list of objects
    """

    def __init__(self, payload_dict):
        self.geo_level_uid = payload_dict["geo_level_uid"]
        self.geo_level_name = payload_dict["geo_level_name"]
        self.parent_geo_level_uid = payload_dict["parent_geo_level_uid"]
