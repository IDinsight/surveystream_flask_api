from app import db
from app.blueprints.targets.models import TargetColumnConfig
from app.blueprints.enumerators.models import EnumeratorColumnConfig
from app.blueprints.forms.models import ParentForm


class DefaultTableConfig:
    """
    Class to create the default table config for the assignments module tables
    """

    def __init__(
        self,
        form_uid,
        survey_uid,
        geo_level_hierarchy,
        prime_geo_level_uid,
        enumerator_location_configured,
        target_location_configured,
    ):
        target_location_columns = []

        if target_location_configured:
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

            if len(target_location_columns) > 0:
                target_location_columns = [
                    {
                        "group_label": "Target Location Details",
                        "columns": target_location_columns,
                    }
                ]

        enumerator_location_columns = []

        if enumerator_location_configured:
            for i, geo_level in enumerate(geo_level_hierarchy.ordered_geo_levels):
                enumerator_location_columns.append(
                    {
                        "column_key": f"enumerator_locations[{i}].location_id",
                        "column_label": f"{geo_level.geo_level_name} ID",
                    }
                )
                enumerator_location_columns.append(
                    {
                        "column_key": f"enumerator_locations[{i}].location_name",
                        "column_label": f"{geo_level.geo_level_name} Name",
                    }
                )

                if geo_level.geo_level_uid == prime_geo_level_uid:
                    break

            if len(enumerator_location_columns) > 0:
                enumerator_location_columns = [
                    {
                        "group_label": "Surveyor Working Location",
                        "columns": enumerator_location_columns,
                    }
                ]

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
                        "column_label": "Target ID",
                    },
                    {
                        "column_key": "gender",
                        "column_label": "Gender",
                    },
                    {
                        "column_key": "language",
                        "column_label": "Language",
                    },
                ],
            },
            "custom_fields_placeholder",
            "locations_placeholder",
            {
                "group_label": "Target Status Details",
                "columns": [
                    {
                        "column_key": "last_attempt_survey_status_label",
                        "column_label": "Last Attempt Survey Status",
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

        self.assignments_main = self.replace_custom_fields_placeholder(
            self.assignments_main, target_custom_fields
        )

        self.assignments_main = self.replace_locations_placeholder(
            self.assignments_main, target_location_columns
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
            "locations_placeholder",
            "form_productivity_placeholder",
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

        self.assignments_surveyors = self.replace_custom_fields_placeholder(
            self.assignments_surveyors, enumerator_custom_fields
        )

        self.assignments_surveyors = self.replace_locations_placeholder(
            self.assignments_surveyors, enumerator_location_columns
        )

        self.assignments_surveyors = self.replace_form_productivity_placeholder(
            self.assignments_surveyors, survey_uid
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
            "locations_placeholder",
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

        self.surveyors = self.replace_custom_fields_placeholder(
            self.surveyors, enumerator_custom_fields
        )

        self.surveyors = self.replace_locations_placeholder(
            self.surveyors, enumerator_location_columns
        )

        self.targets = [
            {
                "group_label": None,
                "columns": [
                    {
                        "column_key": "target_id",
                        "column_label": "Target ID",
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
            "locations_placeholder",
            {
                "group_label": None,
                "columns": [
                    {
                        "column_key": "last_attempt_survey_status_label",
                        "column_label": "Last Attempt Survey Status",
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

        self.targets = self.replace_custom_fields_placeholder(
            self.targets, target_custom_fields
        )

        self.targets = self.replace_locations_placeholder(
            self.targets, target_location_columns
        )

    def replace_custom_fields_placeholder(self, table_config, custom_fields):
        """
        Add the custom fields to the table config
        """
        placeholder_index = table_config.index("custom_fields_placeholder")
        if placeholder_index is not None:
            table_config = (
                table_config[0:placeholder_index]
                + custom_fields
                + table_config[placeholder_index + 1 :]
            )
        return table_config

    def replace_locations_placeholder(self, table_config, locations):
        """
        Add the locations to the table config
        """

        placeholder_index = table_config.index("locations_placeholder")
        table_config = (
            table_config[0:placeholder_index]
            + locations
            + table_config[placeholder_index + 1 :]
        )
        return table_config

    def replace_form_productivity_placeholder(self, table_config, survey_uid):
        """
        Add the form productivity columns to the table config
        """

        forms = ParentForm.query.filter(ParentForm.survey_uid == survey_uid).all()
        placeholder_index = table_config.index("form_productivity_placeholder")
        table_config = (
            table_config[0:placeholder_index]
            + [
                {
                    "group_label": f"Form Productivity ({form.form_name})",
                    "columns": [
                        {
                            "column_key": f"form_productivity.{form.scto_form_id}.total_assigned_targets",
                            "column_label": "Total Assigned Targets",
                        },
                        {
                            "column_key": f"form_productivity.{form.scto_form_id}.total_pending_targets",
                            "column_label": "Total Pending Targets",
                        },
                        {
                            "column_key": f"form_productivity.{form.scto_form_id}.total_completed_targets",
                            "column_label": "Total Completed Targets",
                        },
                    ],
                }
                for form in forms
            ]
            + table_config[placeholder_index + 1 :]
        )
        return table_config
