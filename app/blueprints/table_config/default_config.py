from app import db
from app.blueprints.targets.models import TargetColumnConfig
from app.blueprints.enumerators.models import EnumeratorColumnConfig


class DefaultTableConfig:
    """
    Class to create the default table config for the assignments module tables
    """

    def __init__(self, form_uid, geo_level_hierarchy, prime_geo_level_uid):
        target_location_columns = []

        for i, geo_level in enumerate(geo_level_hierarchy.ordered_geo_levels):
            target_location_columns.append(
                {
                    "column_key": f"target_locations[{i}].location_id",
                    "column_label": f"{geo_level.geo_level_name} ID",
                }
            )
            target_location_columns.append(
                {
                    "column_key": f"target_locations[{i}].location_name",
                    "column_label": f"{geo_level.geo_level_name} Name",
                }
            )

        surveyor_location_columns = []

        for i, geo_level in enumerate(geo_level_hierarchy.ordered_geo_levels):
            if geo_level.geo_level_uid == prime_geo_level_uid:
                break
            else:
                surveyor_location_columns.append(
                    {
                        "column_key": f"locations[{i}].location_id",
                        "column_label": f"{geo_level.geo_level_name} ID",
                    }
                )
                surveyor_location_columns.append(
                    {
                        "column_key": f"locations[{i}].location_name",
                        "column_label": f"{geo_level.geo_level_name} Name",
                    }
                )

        result = TargetColumnConfig.query.filter(
            TargetColumnConfig.form_uid == form_uid,
            TargetColumnConfig.column_type == "custom_fields",
        ).all()

        target_custom_fields = []
        for row in result:
            target_custom_fields.append(
                {
                    "group_label": None,
                    "columns": [
                        {
                            "column_key": f"custom_fields['{row.column_name}']",
                            "column_label": row.column_name,
                        }
                    ],
                }
            )

        result = EnumeratorColumnConfig.query.filter(
            EnumeratorColumnConfig.form_uid == form_uid,
            EnumeratorColumnConfig.column_type == "custom_fields",
        ).all()

        enumerator_custom_fields = []
        for row in result:
            enumerator_custom_fields.append(
                {
                    "group_label": None,
                    "columns": [
                        {
                            "column_key": f"custom_fields['{row.column_name}']",
                            "column_label": row.column_name,
                        }
                    ],
                }
            )

        self.assignments_main = [
            {
                "group_label": None,
                "columns": [
                    {
                        "column_key": "assigned_enumerator_name",
                        "column_label": "Surveyor Name",
                    },
                ],
            },
            {
                "group_label": "Target Details",
                "columns": [
                    {
                        "column_key": "target_id",
                        "column_label": "Unique ID",
                    },
                    {
                        "column_key": "gender",
                        "column_label": "Gender",
                    },
                    {
                        "column_key": "language",
                        "column_label": "Language",
                    },
                    "target_custom_fields_placeholder",
                ],
            },
            {
                "group_label": "Target Location Details",
                "columns": target_location_columns,
            },
            {
                "group_label": "Target Status Details",
                "columns": [
                    {
                        "column_key": "last_attempt_survey_status_label",
                        "column_label": "Interview Status",
                    },
                    {
                        "column_key": "revisit_sections",
                        "column_label": "Revisit Sections",
                    },
                    {
                        "column_key": "num_attempts",
                        "column_label": "Total Attempts",
                    },
                ],
            },
            # "supervisors_placeholder", # Add this back in once we have the supervisor hierarchy in place
        ]

        placeholder_index = self.assignments_main[1]["columns"].index(
            "target_custom_fields_placeholder"
        )
        if placeholder_index is not None:
            self.assignments_main[1]["columns"] = (
                self.assignments_main[1]["columns"][0:placeholder_index]
                + [custom_field["columns"][0] for custom_field in target_custom_fields]
                + self.assignments_main[1]["columns"][placeholder_index + 1 :]
            )

        self.assignments_surveyors = [
            {
                "group_label": None,
                "columns": [
                    {
                        "column_key": "assigned_enumerator_name",
                        "column_label": "Surveyor Name",
                    },
                ],
            },
            {
                "group_label": None,
                "columns": [
                    {"column_key": "surveyor_status", "column_label": "Status"},
                ],
            },
            {
                "group_label": "Surveyor Working Location",
                "columns": target_location_columns,
            },
            {
                "group_label": None,
                "columns": [
                    {"column_key": "total_assigned", "column_label": "Total Assigned"},
                ],
            },
            {
                "group_label": None,
                "columns": [
                    {
                        "column_key": "total_completed",
                        "column_label": "Total Completed",
                    },
                ],
            },
            {
                "group_label": None,
                "columns": [
                    {"column_key": "total_pending", "column_label": "Total Pending"},
                ],
            },
            {
                "group_label": None,
                "columns": [
                    {
                        "column_key": "gender",
                        "column_label": "Gender",
                    }
                ],
            },
            {
                "group_label": None,
                "columns": [
                    {
                        "column_key": "language",
                        "column_label": "Language",
                    }
                ],
            },
            {
                "group_label": None,
                "columns": [
                    {
                        "column_key": "home_address",
                        "column_label": "Address",
                    }
                ],
            },
            "custom_fields_placeholder",
        ]

        placeholder_index = self.assignments_surveyors.index(
            "custom_fields_placeholder"
        )
        if placeholder_index is not None:
            self.assignments_surveyors = (
                self.assignments_surveyors[0:placeholder_index]
                + enumerator_custom_fields
                + self.assignments_surveyors[placeholder_index + 1 :]
            )

        self.assignments_review = [
            {
                "group_label": None,
                "columns": [
                    {
                        "column_key": "assigned_enumerator_name",
                        "column_label": "Surveyor Name",
                    },
                ],
            },
            {
                "group_label": None,
                "columns": [
                    {
                        "column_key": "prev_assigned_to",
                        "column_label": "Previously Assigned To",
                    },
                ],
            },
            {
                "group_label": None,
                "columns": [
                    {"column_key": "target_id", "column_label": "Target Unique ID"},
                ],
            },
            {
                "group_label": None,
                "columns": [
                    {
                        "column_key": "last_attempt_survey_status_label",
                        "column_label": "Target Status",
                    },
                ],
            },
        ]

        self.surveyors = [
            {
                "group_label": None,
                "columns": [
                    {"column_key": "name", "column_label": "Name"},
                ],
            },
            {
                "group_label": None,
                "columns": [
                    {"column_key": "enumerator_id", "column_label": "ID"},
                ],
            },
            {
                "group_label": None,
                "columns": [
                    {"column_key": "surveyor_status", "column_label": "Status"},
                ],
            },
            {
                "group_label": "Surveyor Working Location",
                "columns": target_location_columns,
            },
            {
                "group_label": None,
                "columns": [
                    {"column_key": "total_assigned", "column_label": "Total Assigned"},
                ],
            },
            {
                "group_label": None,
                "columns": [
                    {
                        "column_key": "total_completed",
                        "column_label": "Total Completed",
                    },
                ],
            },
            {
                "group_label": None,
                "columns": [
                    {"column_key": "total_pending", "column_label": "Total Pending"},
                ],
            },
            {
                "group_label": None,
                "columns": [
                    {
                        "column_key": "email",
                        "column_label": "Email",
                    }
                ],
            },
            {
                "group_label": None,
                "columns": [
                    {
                        "column_key": "mobile_primary",
                        "column_label": "Mobile",
                    }
                ],
            },
            {
                "group_label": None,
                "columns": [
                    {
                        "column_key": "gender",
                        "column_label": "Gender",
                    }
                ],
            },
            {
                "group_label": None,
                "columns": [
                    {
                        "column_key": "language",
                        "column_label": "Language",
                    }
                ],
            },
            {
                "group_label": None,
                "columns": [
                    {
                        "column_key": "home_address",
                        "column_label": "Address",
                    }
                ],
            },
            "custom_fields_placeholder",
            # "supervisors_placeholder", # Add this back in once we have the supervisor hierarchy in place
        ]

        placeholder_index = self.surveyors.index("custom_fields_placeholder")
        if placeholder_index is not None:
            self.surveyors = (
                self.surveyors[0:placeholder_index]
                + enumerator_custom_fields
                + self.surveyors[placeholder_index + 1 :]
            )

        self.targets = [
            {
                "group_label": None,
                "columns": [
                    {
                        "column_key": "target_id",
                        "column_label": "Unique ID",
                    }
                ],
            },
            {
                "group_label": None,
                "columns": [
                    {
                        "column_key": "gender",
                        "column_label": "Gender",
                    }
                ],
            },
            {
                "group_label": None,
                "columns": [
                    {
                        "column_key": "language",
                        "column_label": "Language",
                    }
                ],
            },
            "custom_fields_placeholder",
            {"group_label": "Location Details", "columns": target_location_columns},
            {
                "group_label": None,
                "columns": [
                    {
                        "column_key": "last_attempt_survey_status_label",
                        "column_label": "Interview Status",
                    },
                ],
            },
            {
                "group_label": None,
                "columns": [
                    {
                        "column_key": "revisit_sections",
                        "column_label": "Revisit Sections",
                    },
                ],
            },
            {
                "group_label": None,
                "columns": [
                    {
                        "column_key": "num_attempts",
                        "column_label": "Total Attempts",
                    },
                ],
            },
            # "supervisors_placeholder",  # Add this back in once we have the supervisor hierarchy in place
        ]

        placeholder_index = self.targets.index("custom_fields_placeholder")
        if placeholder_index is not None:
            self.targets = (
                self.targets[0:placeholder_index]
                + target_custom_fields
                + self.targets[placeholder_index + 1 :]
            )
