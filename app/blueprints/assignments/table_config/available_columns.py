from app import db
from app.blueprints.targets.models import TargetColumnConfig, TargetStatus, Target
from app.blueprints.enumerators.models import EnumeratorColumnConfig
from app.blueprints.forms.models import Form, SCTOQuestion


class AvailableColumns:
    """
    Class to create the list of available columns for the assignments module tables
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

        enumerator_location_columns = []

        if enumerator_location_configured:
            for i, geo_level in enumerate(geo_level_hierarchy.ordered_geo_levels):
                enumerator_location_columns.append(
                    {
                        "column_key": f"surveyor_locations[{i}].location_id",
                        "column_label": f"{geo_level.geo_level_name} ID",
                    }
                )
                enumerator_location_columns.append(
                    {
                        "column_key": f"surveyor_locations[{i}].location_name",
                        "column_label": f"{geo_level.geo_level_name} Name",
                    }
                )

                if geo_level.geo_level_uid == prime_geo_level_uid:
                    break

        result = TargetColumnConfig.query.filter(
            TargetColumnConfig.form_uid == form_uid,
            TargetColumnConfig.column_type == "custom_fields",
        ).all()

        target_custom_fields = []
        for row in result:
            target_custom_fields.append(
                {
                    "column_key": f"custom_fields['{row.column_name}']",
                    "column_label": row.column_name,
                }
            )

        result = EnumeratorColumnConfig.query.filter(
            EnumeratorColumnConfig.form_uid == form_uid,
            EnumeratorColumnConfig.column_type == "custom_fields",
        ).all()

        enumerator_custom_fields = []
        assigned_enumerator_custom_fields = []
        for row in result:
            enumerator_custom_fields.append(
                {
                    "column_key": f"custom_fields['{row.column_name}']",
                    "column_label": row.column_name,
                }
            )

            assigned_enumerator_custom_fields.append(
                {
                    "column_key": f"assigned_enumerator_custom_fields['{row.column_name}']",
                    "column_label": row.column_name,
                }
            )

        result = (
            db.session.query(
                TargetStatus,
                Target,
            )
            .join(
                Target,
                Target.target_uid == TargetStatus.target_uid,
            )
            .filter(Target.form_uid == form_uid)
            .all()
        )

        scto_fields = []

        # Sometimes the formdef_metadata_fields are not present in the SCTOQuestion table so we will handle them manually
        formdef_metadata_fields = [
            "instanceID",
            "formdef_version",
            "starttime",
            "endtime",
            "SubmissionDate",
        ]

        result = (
            SCTOQuestion.query.filter_by(form_uid=form_uid, is_repeat_group=False)
            .filter(
                SCTOQuestion.question_type.notin_(
                    [
                        "begin group",
                        "end group",
                        "begin repeat",
                        "end repeat",
                        "note",
                        "image",
                        "audio",
                        "video",
                        "file",
                        "text audit",
                        "audio audit" "sensor_statistic",
                        "sensor_stream",
                    ]
                )
            )
            .all()
        )

        for row in result:
            if row.question_name not in formdef_metadata_fields:
                scto_fields.append(
                    {
                        "column_key": f"scto_fields.{row.question_name}",
                        "column_label": row.question_name,
                    }
                )

        if len(scto_fields) != 0:
            scto_fields = [
                {
                    "column_key": f"scto_fields.{item}",
                    "column_label": item,
                }
                for item in formdef_metadata_fields
            ] + scto_fields

        self.assignments_main = [
            {
                "column_key": "assigned_enumerator_name",
                "column_label": "Surveyor Name",
            },
            {
                "column_key": "assigned_enumerator_id",
                "column_label": "Surveyor ID",
            },
            {
                "column_key": "assigned_enumerator_home_address",
                "column_label": "Surveyor Address",
            },
            {
                "column_key": "assigned_enumerator_gender",
                "column_label": "Surveyor Gender",
            },
            {
                "column_key": "assigned_enumerator_language",
                "column_label": "Surveyor Language",
            },
            {
                "column_key": "assigned_enumerator_email",
                "column_label": "Surveyor Email",
            },
            {
                "column_key": "assigned_enumerator_mobile_primary",
                "column_label": "Surveyor Mobile",
            },
            "assigned_enumerator_custom_fields_placeholder",
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
            "custom_fields_placeholder",
            "locations_placeholder",
            {
                "column_key": "final_survey_status_label",
                "column_label": "Final Survey Status",
            },
            {
                "column_key": "final_survey_status",
                "column_label": "Final Survey Status Code",
            },
            {
                "column_key": "revisit_sections",
                "column_label": "Revisit Sections",
            },
            {
                "column_key": "num_attempts",
                "column_label": "Total Attempts",
            },
            {
                "column_key": "refusal_flag",
                "column_label": "Refused",
            },
            {
                "column_key": "completed_flag",
                "column_label": "Completed",
            },
            "scto_fields_placeholder",
        ]
        # "supervisors_placeholder", # Add this back in once we have the supervisor hierarchy in place

        self.assignments_main = self.replace_custom_fields_placeholder(
            self.assignments_main, target_custom_fields, "custom_fields_placeholder"
        )

        self.assignments_main = self.replace_custom_fields_placeholder(
            self.assignments_main,
            assigned_enumerator_custom_fields,
            "assigned_enumerator_custom_fields_placeholder",
        )

        self.assignments_main = self.replace_locations_placeholder(
            self.assignments_main, target_location_columns
        )

        self.assignments_main = self.replace_scto_fields_placeholder(
            self.assignments_main, scto_fields
        )

        self.assignments_surveyors = [
            {
                "column_key": "enumerator_id",
                "column_label": "ID",
            },
            {
                "column_key": "name",
                "column_label": "Name",
            },
            {"column_key": "surveyor_status", "column_label": "Status"},
            "locations_placeholder",
            "form_productivity_placeholder",
            {
                "column_key": "gender",
                "column_label": "Gender",
            },
            {
                "column_key": "language",
                "column_label": "Language",
            },
            {
                "column_key": "home_address",
                "column_label": "Address",
            },
            {
                "column_key": "email",
                "column_label": "Email",
            },
            {
                "column_key": "mobile_primary",
                "column_label": "Mobile",
            },
            "custom_fields_placeholder",
        ]

        self.assignments_surveyors = self.replace_custom_fields_placeholder(
            self.assignments_surveyors,
            enumerator_custom_fields,
            "custom_fields_placeholder",
        )

        self.assignments_surveyors = self.replace_locations_placeholder(
            self.assignments_surveyors, enumerator_location_columns
        )

        self.assignments_surveyors = self.replace_form_productivity_placeholder(
            self.assignments_surveyors, survey_uid, form_uid
        )

        self.assignments_review = [
            {
                "column_key": "assigned_enumerator_name",
                "column_label": "Surveyor Name",
            },
            {
                "column_key": "prev_assigned_to",
                "column_label": "Previously Assigned To",
            },
            {
                "column_key": "assigned_enumerator_id",
                "column_label": "Surveyor ID",
            },
            {
                "column_key": "assigned_enumerator_home_address",
                "column_label": "Surveyor Address",
            },
            {
                "column_key": "assigned_enumerator_gender",
                "column_label": "Surveyor Gender",
            },
            {
                "column_key": "assigned_enumerator_language",
                "column_label": "Surveyor Language",
            },
            {
                "column_key": "assigned_enumerator_email",
                "column_label": "Surveyor Email",
            },
            {
                "column_key": "assigned_enumerator_mobile_primary",
                "column_label": "Surveyor Mobile",
            },
            "assigned_enumerator_custom_fields_placeholder",
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
            "custom_fields_placeholder",
            "locations_placeholder",
            {
                "column_key": "final_survey_status_label",
                "column_label": "Final Survey Status",
            },
            {
                "column_key": "final_survey_status",
                "column_label": "Final Survey Status Code",
            },
            {
                "column_key": "revisit_sections",
                "column_label": "Revisit Sections",
            },
            {
                "column_key": "num_attempts",
                "column_label": "Total Attempts",
            },
            {
                "column_key": "refusal_flag",
                "column_label": "Refused",
            },
            {
                "column_key": "completed_flag",
                "column_label": "Completed",
            },
            "scto_fields_placeholder",
        ]
        # "supervisors_placeholder", # Add this back in once we have the supervisor hierarchy in place

        self.assignments_review = self.replace_custom_fields_placeholder(
            self.assignments_review, target_custom_fields, "custom_fields_placeholder"
        )

        self.assignments_review = self.replace_custom_fields_placeholder(
            self.assignments_review,
            assigned_enumerator_custom_fields,
            "assigned_enumerator_custom_fields_placeholder",
        )

        self.assignments_review = self.replace_locations_placeholder(
            self.assignments_review, target_location_columns
        )

        self.assignments_review = self.replace_scto_fields_placeholder(
            self.assignments_review, scto_fields
        )

        self.surveyors = [
            {"column_key": "name", "column_label": "Name"},
            {"column_key": "enumerator_id", "column_label": "ID"},
            {"column_key": "surveyor_status", "column_label": "Status"},
            "locations_placeholder",
            {
                "column_key": "email",
                "column_label": "Email",
            },
            {
                "column_key": "mobile_primary",
                "column_label": "Mobile",
            },
            {
                "column_key": "gender",
                "column_label": "Gender",
            },
            {
                "column_key": "language",
                "column_label": "Language",
            },
            {
                "column_key": "home_address",
                "column_label": "Address",
            },
            "custom_fields_placeholder",
            # "supervisors_placeholder", # Add this back in once we have the supervisor hierarchy in place
        ]

        self.surveyors = self.replace_custom_fields_placeholder(
            self.surveyors, enumerator_custom_fields, "custom_fields_placeholder"
        )

        self.surveyors = self.replace_locations_placeholder(
            self.surveyors, enumerator_location_columns
        )

        self.targets = [
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
            "custom_fields_placeholder",
            "locations_placeholder",
            {
                "column_key": "final_survey_status_label",
                "column_label": "Final Survey Status",
            },
            {
                "column_key": "final_survey_status",
                "column_label": "Final Survey Status Code",
            },
            {
                "column_key": "revisit_sections",
                "column_label": "Revisit Sections",
            },
            {
                "column_key": "num_attempts",
                "column_label": "Total Attempts",
            },
            {
                "column_key": "refusal_flag",
                "column_label": "Refused",
            },
            {
                "column_key": "completed_flag",
                "column_label": "Completed",
            },
            "scto_fields_placeholder",
            # "supervisors_placeholder",  # Add this back in once we have the supervisor hierarchy in place
        ]

        self.targets = self.replace_custom_fields_placeholder(
            self.targets, target_custom_fields, "custom_fields_placeholder"
        )

        self.targets = self.replace_locations_placeholder(
            self.targets, target_location_columns
        )

        self.targets = self.replace_scto_fields_placeholder(self.targets, scto_fields)

    def replace_custom_fields_placeholder(
        self, table_config, custom_fields, placeholder_text
    ):
        """
        Add the custom fields to the table config
        """
        placeholder_index = table_config.index(placeholder_text)
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

    def replace_scto_fields_placeholder(self, table_config, scto_fields):
        """
        Add the scto fields to the table config
        """

        placeholder_index = table_config.index("scto_fields_placeholder")
        table_config = (
            table_config[0:placeholder_index]
            + scto_fields
            + table_config[placeholder_index + 1 :]
        )
        return table_config

    def replace_form_productivity_placeholder(self, table_config, survey_uid, form_uid):
        """
        Add the form productivity columns to the table config
        """

        forms = Form.query.filter(Form.survey_uid == survey_uid).all()
        placeholder_index = table_config.index("form_productivity_placeholder")

        form_productivity_columns = []

        for form in forms:
            if form.form_uid == form_uid:
                form_productivity_columns.append(
                    {
                        "column_key": f"form_productivity.{form.scto_form_id}.total_assigned_targets",
                        "column_label": "Total Assigned Targets",
                    }
                )
                form_productivity_columns.append(
                    {
                        "column_key": f"form_productivity.{form.scto_form_id}.total_pending_targets",
                        "column_label": "Total Pending Targets",
                    }
                )
                form_productivity_columns.append(
                    {
                        "column_key": f"form_productivity.{form.scto_form_id}.total_completed_targets",
                        "column_label": "Total Completed Targets",
                    }
                )

        for form in forms:
            if form.form_uid != form_uid:
                form_productivity_columns.append(
                    {
                        "column_key": f"form_productivity.{form.scto_form_id}.total_assigned_targets",
                        "column_label": "Total Assigned Targets",
                    }
                )
                form_productivity_columns.append(
                    {
                        "column_key": f"form_productivity.{form.scto_form_id}.total_pending_targets",
                        "column_label": "Total Pending Targets",
                    }
                )
                form_productivity_columns.append(
                    {
                        "column_key": f"form_productivity.{form.scto_form_id}.total_completed_targets",
                        "column_label": "Total Completed Targets",
                    }
                )

        table_config = (
            table_config[0:placeholder_index]
            + form_productivity_columns
            + table_config[placeholder_index + 1 :]
        )
        return table_config

    def to_dict(self):
        return {
            "assignments_main": self.assignments_main,
            "assignments_surveyors": self.assignments_surveyors,
            "assignments_review": self.assignments_review,
            "surveyors": self.surveyors,
            "targets": self.targets,
        }
