import base64
import json
from datetime import datetime, timedelta
from pathlib import Path

import jsondiff
import pandas as pd
import pytest

from app import db


@pytest.mark.assignments
class TestAssignments:
    @pytest.fixture()
    def create_survey(self, client, login_test_user, csrf_token, test_user_credentials):
        """
        Insert new survey
        """

        payload = {
            "survey_id": "test_survey",
            "survey_name": "Test Survey",
            "survey_description": "A test survey",
            "project_name": "Test Project",
            "surveying_method": "in-person",
            "irb_approval": "Yes",
            "planned_start_date": "2021-01-01",
            "planned_end_date": "2021-12-31",
            "state": "Draft",
            "prime_geo_level_uid": 1,
            "config_status": "In Progress - Configuration",
            "created_by_user_uid": test_user_credentials["user_uid"],
        }

        response = client.post(
            "/api/surveys",
            query_string={"user_uid": 3},
            json=payload,
            content_type="application/json",
            headers={"X-CSRF-Token": csrf_token},
        )
        assert response.status_code == 201

        yield

    @pytest.fixture()
    def create_module_questionnaire(
        self, client, login_test_user, csrf_token, test_user_credentials, create_survey
    ):
        """
        Insert new module_questionnaire to set up mapping criteria needed for assignments
        """

        payload = {
            "assignment_process": "Manual",
            "language_location_mapping": False,
            "reassignment_required": False,
            "target_mapping_criteria": ["Location"],
            "surveyor_mapping_criteria": ["Location"],
            "supervisor_hierarchy_exists": False,
            "supervisor_surveyor_relation": "1:many",
            "survey_uid": 1,
            "target_assignment_criteria": ["Location of surveyors"],
        }

        response = client.put(
            "/api/module-questionnaire/1",
            json=payload,
            content_type="application/json",
            headers={"X-CSRF-Token": csrf_token},
        )
        assert response.status_code == 200

        yield

    @pytest.fixture()
    def create_module_selection(
        self,
        client,
        login_test_user,
        csrf_token,
        test_user_credentials,
        create_module_questionnaire,
    ):
        """
        Insert assignments module_selection
        """

        payload = {
            "survey_uid": 1,
            "modules": ["9"],
        }

        response = client.post(
            "/api/module-status",
            json=payload,
            content_type="application/json",
            headers={"X-CSRF-Token": csrf_token},
        )
        assert response.status_code == 200

        yield

    @pytest.fixture()
    def create_form(self, client, login_test_user, csrf_token, create_module_selection):
        """
        Insert new form
        """

        payload = {
            "survey_uid": 1,
            "scto_form_id": "test_scto_input_output",
            "form_name": "Agrifieldnet Main Form",
            "tz_name": "Asia/Kolkata",
            "scto_server_name": "dod",
            "encryption_key_shared": True,
            "server_access_role_granted": True,
            "server_access_allowed": True,
            "form_type": "parent",
            "parent_form_uid": None,
            "dq_form_type": None,
            "number_of_attempts": 7,
        }

        response = client.post(
            "/api/forms",
            json=payload,
            content_type="application/json",
            headers={"X-CSRF-Token": csrf_token},
        )
        assert response.status_code == 201

        yield

    @pytest.fixture()
    def create_scto_question_mapping(
        self, client, csrf_token, login_test_user, create_form
    ):
        """
        Insert SCTO question mapping as a setup step for the tests
        """

        # Insert the SCTO question mapping
        payload = {
            "form_uid": 1,
            "survey_status": "test_survey_status",
            "revisit_section": "test_revisit_section",
            "target_id": "test_target_id",
            "enumerator_id": "test_enumerator_id",
            "locations": {
                "location_1": "test_location_1",
            },
        }

        response = client.post(
            "/api/forms/1/scto-question-mapping",
            json=payload,
            content_type="application/json",
            headers={"X-CSRF-Token": csrf_token},
        )
        assert response.status_code == 201

        yield

    @pytest.fixture()
    def create_geo_levels(self, client, login_test_user, csrf_token, create_form):
        """
        Insert new geo levels
        These correspond to the geo levels found in the locations test files
        """

        payload = {
            "geo_levels": [
                {
                    "geo_level_uid": None,
                    "geo_level_name": "District",
                    "parent_geo_level_uid": None,
                },
                {
                    "geo_level_uid": None,
                    "geo_level_name": "Mandal",
                    "parent_geo_level_uid": 1,
                },
                {
                    "geo_level_uid": None,
                    "geo_level_name": "PSU",
                    "parent_geo_level_uid": 2,
                },
            ]
        }

        response = client.put(
            "/api/locations/geo-levels",
            query_string={"survey_uid": 1},
            json=payload,
            content_type="application/json",
            headers={"X-CSRF-Token": csrf_token},
        )
        assert response.status_code == 200

        yield

    @pytest.fixture()
    def create_locations(
        self,
        client,
        login_test_user,
        create_geo_levels,
        csrf_token,
    ):
        """
        Insert new locations
        """

        filepath = (
            Path(__file__).resolve().parent / f"assets/sample_locations_medium.csv"
        )

        # Read the locations.csv file and convert it to base64
        with open(filepath, "rb") as f:
            locations_csv = f.read()
            locations_csv_encoded = base64.b64encode(locations_csv).decode("utf-8")

        # Try to upload the locations csv
        payload = {
            "geo_level_mapping": [
                {
                    "geo_level_uid": 1,
                    "location_name_column": "district_name",
                    "location_id_column": "district_id",
                },
                {
                    "geo_level_uid": 2,
                    "location_name_column": "mandal_name",
                    "location_id_column": "mandal_id",
                },
                {
                    "geo_level_uid": 3,
                    "location_name_column": "psu_name",
                    "location_id_column": "psu_id",
                },
            ],
            "file": locations_csv_encoded,
        }

        response = client.post(
            "/api/locations",
            query_string={"survey_uid": 1},
            json=payload,
            content_type="application/json",
            headers={"X-CSRF-Token": csrf_token},
        )

        assert response.status_code == 200

        """        df = pd.read_csv(filepath, dtype=str)
        df.rename(
            columns={
                "district_id": "District ID",
                "district_name": "District Name",
                "mandal_id": "Mandal ID",
                "mandal_name": "Mandal Name",
                "psu_id": "PSU ID",
                "psu_name": "PSU Name",
            },
            inplace=True,
        )

        expected_response = {
            "data": {
                "ordered_columns": [
                    "District ID",
                    "District Name",
                    "Mandal ID",
                    "Mandal Name",
                    "PSU ID",
                    "PSU Name",
                ],
                "records": df.to_dict(orient="records"),
            },
            "success": True,
        }
        # Check the response
        response = client.get("/api/locations", query_string={"survey_uid": 1})

        checkdiff = jsondiff.diff(expected_response, response.json)
        assert checkdiff == {}"""

    @pytest.fixture()
    def create_roles(self, client, login_test_user, csrf_token):
        """
        Insert new roles as a setup step
        """

        payload = {
            "roles": [
                {
                    "role_uid": None,
                    "role_name": "Core User",
                    "reporting_role_uid": None,
                    "permissions": [9],
                },
                {
                    "role_uid": None,
                    "role_name": "Cluster Coordinator",
                    "reporting_role_uid": 1,
                    "permissions": [9],
                },
                {
                    "role_uid": None,
                    "role_name": "Regional Coordinator",
                    "reporting_role_uid": 2,
                    "permissions": [9],
                },
            ]
        }

        response = client.put(
            "/api/roles",
            query_string={"survey_uid": 1},
            json=payload,
            content_type="application/json",
            headers={"X-CSRF-Token": csrf_token},
        )
        assert response.status_code == 200

        yield

    @pytest.fixture()
    def add_fsl_1_user(self, client, login_test_user, csrf_token, create_roles):
        """
        Add users at with field supervisor level 1 role
        """
        # Add core team user
        response = client.post(
            "/api/users",
            json={
                "survey_uid": 1,
                "email": "utkarsh.gupta+u000@idinsight.org",
                "first_name": "Tim",
                "last_name": "Doe",
                "roles": [1],
            },
            content_type="application/json",
            headers={"X-CSRF-Token": csrf_token},
        )

        assert response.status_code == 200
        assert b"Success: user invited" in response.data
        response_data = json.loads(response.data)
        core_user = response_data.get("user")

        return core_user

    @pytest.fixture()
    def add_fsl_2_user(self, client, login_test_user, csrf_token, create_roles):
        """
        Add users at with field supervisor level 2 role
        """
        # Add CC user
        response = client.post(
            "/api/users",
            json={
                "survey_uid": 1,
                "email": "utkarsh.gupta+u00@idinsight.org",
                "first_name": "Ron",
                "last_name": "Doe",
                "roles": [2],
            },
            content_type="application/json",
            headers={"X-CSRF-Token": csrf_token},
        )

        assert response.status_code == 200
        assert b"Success: user invited" in response.data
        response_data = json.loads(response.data)
        cc_user = response_data.get("user")

        return cc_user

    @pytest.fixture()
    def add_fsl_3_user(self, client, login_test_user, csrf_token, create_roles):
        """
        Add users at with field supervisor level 3 role (lowest level)
        """
        # Add RC user
        response = client.post(
            "/api/users",
            json={
                "survey_uid": 1,
                "email": "utkarsh.gupta+u0@idinsight.org",
                "first_name": "John",
                "last_name": "Doe",
                "roles": [3],
                "gender": "Male",
                "languages": ["Hindi", "Telugu", "English"],
                "location_uids": [1],
            },
            content_type="application/json",
            headers={"X-CSRF-Token": csrf_token},
        )

        assert response.status_code == 200
        assert b"Success: user invited" in response.data
        response_data = json.loads(response.data)
        rc_user = response_data.get("user")

        return rc_user

    @pytest.fixture()
    def add_another_fsl_3_user(self, client, login_test_user, csrf_token, create_roles):
        """
        Add users at with field supervisor level 3 role (lowest level)
        """
        # Add RC user
        response = client.post(
            "/api/users",
            json={
                "survey_uid": 1,
                "email": "utkarsh.gupta+u1@idinsight.org",
                "first_name": "John",
                "last_name": "Doe",
                "roles": [3],
                "gender": "Male",
                "languages": ["Hindi", "Telugu", "English"],
                "location_uids": [2, 3, 4],
            },
            content_type="application/json",
            headers={"X-CSRF-Token": csrf_token},
        )
        print(response.json)
        assert response.status_code == 200
        assert b"Success: user invited" in response.data
        response_data = json.loads(response.data)
        rc_user = response_data.get("user")

        return rc_user

    @pytest.fixture()
    def add_user_hierarchy(
        self,
        client,
        login_test_user,
        csrf_token,
        create_roles,
        add_fsl_1_user,
        add_fsl_2_user,
        add_fsl_3_user,
        add_another_fsl_3_user,
    ):
        """
        Define user hierarchy dependencies between fsl 1, fsl 2 and fsl 3 users added
        """

        # Add user hierarchy records between rc and cc
        payload = {
            "survey_uid": 1,
            "role_uid": 3,
            "user_uid": add_fsl_3_user["user_uid"],
            "parent_user_uid": add_fsl_2_user["user_uid"],
        }

        response = client.put(
            "/api/user-hierarchy",
            json=payload,
            content_type="application/json",
            headers={"X-CSRF-Token": csrf_token},
        )

        assert response.status_code == 200
        # Add user hierarchy records between rc and cc
        payload = {
            "survey_uid": 1,
            "role_uid": 3,
            "user_uid": add_another_fsl_3_user["user_uid"],
            "parent_user_uid": add_fsl_2_user["user_uid"],
        }

        response = client.put(
            "/api/user-hierarchy",
            json=payload,
            content_type="application/json",
            headers={"X-CSRF-Token": csrf_token},
        )

        assert response.status_code == 200

        # Add user hierarchy records between cc and core user
        payload = {
            "survey_uid": 1,
            "role_uid": 2,
            "user_uid": add_fsl_2_user["user_uid"],
            "parent_user_uid": add_fsl_1_user["user_uid"],
        }

        response = client.put(
            "/api/user-hierarchy",
            json=payload,
            content_type="application/json",
            headers={"X-CSRF-Token": csrf_token},
        )

        assert response.status_code == 200

    @pytest.fixture()
    def create_enumerator_column_config(
        self, client, login_test_user, create_form, csrf_token
    ):
        """
        Create the enumerators column config
        """

        payload = {
            "form_uid": 1,
            "column_config": [
                {
                    "column_name": "enumerator_id",
                    "column_type": "personal_details",
                    "allow_null_values": False,
                },
                {
                    "column_name": "name",
                    "column_type": "personal_details",
                    "allow_null_values": False,
                },
                {
                    "column_name": "email",
                    "column_type": "personal_details",
                    "allow_null_values": False,
                },
                {
                    "column_name": "mobile_primary",
                    "column_type": "personal_details",
                    "allow_null_values": False,
                },
                {
                    "column_name": "language",
                    "column_type": "personal_details",
                    "allow_null_values": True,
                },
                {
                    "column_name": "home_address",
                    "column_type": "personal_details",
                    "allow_null_values": False,
                },
                {
                    "column_name": "gender",
                    "column_type": "personal_details",
                    "allow_null_values": False,
                },
                {
                    "column_name": "prime_geo_level_location",
                    "column_type": "location",
                    "allow_null_values": True,
                },
                {
                    "column_name": "Mobile (Secondary)",
                    "column_type": "custom_fields",
                    "allow_null_values": True,
                },
                {
                    "column_name": "Age",
                    "column_type": "custom_fields",
                    "allow_null_values": False,
                },
            ],
        }

        response = client.put(
            "/api/enumerators/column-config",
            query_string={"form_uid": 1},
            json=payload,
            content_type="application/json",
            headers={"X-CSRF-Token": csrf_token},
        )

        assert response.status_code == 200

        yield

    @pytest.fixture()
    def upload_enumerators_csv(
        self, client, login_test_user, create_locations, csrf_token
    ):
        """
        Insert enumerators
        Include a custom field
        Include a location id column that corresponds to the prime geo level for the survey (district)
        """

        filepath = (
            Path(__file__).resolve().parent / f"assets/sample_enumerators_large.csv"
        )

        # Read the enumerators.csv file and convert it to base64
        with open(filepath, "rb") as f:
            enumerators_csv = f.read()
            enumerators_csv_encoded = base64.b64encode(enumerators_csv).decode("utf-8")

        # Try to upload the enumerators csv
        payload = {
            "column_mapping": {
                "enumerator_id": "enumerator_id1",
                "name": "name1",
                "email": "email1",
                "mobile_primary": "mobile_primary1",
                "language": "language1",
                "home_address": "home_address1",
                "gender": "gender1",
                "enumerator_type": "enumerator_type1",
                "location_id_column": "district_id1",
                "custom_fields": [
                    {
                        "field_label": "Mobile (Secondary)",
                        "column_name": "mobile_secondary1",
                    },
                    {
                        "field_label": "Age",
                        "column_name": "age1",
                    },
                ],
            },
            "file": enumerators_csv_encoded,
            "mode": "overwrite",
        }

        response = client.post(
            "/api/enumerators",
            query_string={"form_uid": 1},
            json=payload,
            content_type="application/json",
            headers={"X-CSRF-Token": csrf_token},
        )
        assert response.status_code == 200

    @pytest.fixture()
    def create_target_config(self, client, login_test_user, create_form, csrf_token):
        """
        Load target config table for tests with form inputs
        """

        payload = {
            "form_uid": 1,
            "target_source": "csv",
        }

        response = client.post(
            "/api/targets/config",
            json=payload,
            content_type="application/json",
            headers={"X-CSRF-Token": csrf_token},
        )
        print(response.json)
        assert response.status_code == 200

    @pytest.fixture()
    def create_target_column_config(
        self, client, login_test_user, create_form, csrf_token
    ):
        """
        Upload the targets column config
        """

        payload = {
            "form_uid": 1,
            "column_config": [
                {
                    "column_name": "target_id",
                    "column_type": "basic_details",
                    "allow_null_values": False,
                    "contains_pii": False,
                    "column_source": "target_id1",
                },
                {
                    "column_name": "language",
                    "column_type": "basic_details",
                    "allow_null_values": True,
                    "contains_pii": True,
                    "column_source": "language",
                },
                {
                    "column_name": "gender",
                    "column_type": "basic_details",
                    "allow_null_values": False,
                    "contains_pii": True,
                    "column_source": "gender",
                },
                {
                    "column_name": "Name",
                    "column_type": "custom_fields",
                    "allow_null_values": False,
                    "contains_pii": True,
                    "column_source": "name",
                },
                {
                    "column_name": "Mobile no.",
                    "column_type": "custom_fields",
                    "allow_null_values": False,
                    "contains_pii": True,
                    "column_source": "mobile_primary",
                },
                {
                    "column_name": "Address",
                    "column_type": "custom_fields",
                    "allow_null_values": True,
                    "contains_pii": True,
                    "column_source": "address",
                },
                {
                    "column_name": "bottom_geo_level_location",
                    "column_type": "location",
                    "allow_null_values": True,
                    "contains_pii": True,
                    "column_source": "psu_id",
                },
            ],
        }

        response = client.put(
            "/api/targets/column-config",
            query_string={"form_uid": 1},
            json=payload,
            content_type="application/json",
            headers={"X-CSRF-Token": csrf_token},
        )

        assert response.status_code == 200

        yield

    @pytest.fixture()
    def upload_targets_csv(
        self,
        client,
        login_test_user,
        create_locations,
        create_target_config,
        csrf_token,
    ):
        """
        Upload the targets csv
        """

        filepath = Path(__file__).resolve().parent / f"assets/sample_targets_large.csv"

        # Read the targets.csv file and convert it to base64
        with open(filepath, "rb") as f:
            targets_csv = f.read()
            targets_csv_encoded = base64.b64encode(targets_csv).decode("utf-8")

        # Try to upload the targets csv
        payload = {
            "column_mapping": {
                "target_id": "target_id1",
                "language": "language1",
                "gender": "gender1",
                "location_id_column": "psu_id1",
                "custom_fields": [
                    {
                        "field_label": "Mobile no.",
                        "column_name": "mobile_primary1",
                    },
                    {
                        "field_label": "Name",
                        "column_name": "name1",
                    },
                    {
                        "field_label": "Address",
                        "column_name": "address1",
                    },
                ],
            },
            "file": targets_csv_encoded,
            "mode": "overwrite",
        }

        response = client.post(
            "/api/targets",
            query_string={"form_uid": 1},
            json=payload,
            content_type="application/json",
            headers={"X-CSRF-Token": csrf_token},
        )
        assert response.status_code == 200

    @pytest.fixture
    def create_email_config(
        self, client, login_test_user, csrf_token, test_user_credentials, create_form
    ):
        """
        Insert an email config as a setup step for email tests
        """
        payload = {
            "config_name": "AssignmentsConfig",
            "form_uid": 1,
            "report_users": [1, 2, 3],
            "email_source": "SurveyStream Data",
            "email_source_gsheet_link": "test_key",
            "email_source_gsheet_tab": "test_tab",
            "email_source_gsheet_header_row": 1,
            "email_source_tablename": "test_table",
            "email_source_columns": ["test_column"],
        }
        response = client.post(
            "/api/emails/config",
            json=payload,
            content_type="application/json",
            headers={"X-CSRF-Token": csrf_token},
        )
        assert response.status_code == 201
        return response.json["data"]

    @pytest.fixture
    def create_email_template(
        self,
        client,
        login_test_user,
        csrf_token,
        test_user_credentials,
        create_email_config,
    ):
        """
        Insert email template as a setup for tests
        """
        payload = {
            "subject": "Test Assignments Email",
            "language": "english",
            "content": "Test Content",
            "email_config_uid": create_email_config["email_config_uid"],
            "variable_list": [],
            "table_list": [
                {
                    "table_name": "Assignments: Default",
                    "column_mapping": {
                        "test_column1": "TEST Column 1",
                        "test_column2": "TEST Column 2",
                    },
                    "sort_list": {"test_column1": "asc", "test_column2": "desc"},
                    "variable_name": "test_table+_1",
                    "filter_list": [
                        {
                            "filter_group": [
                                {
                                    "table_name": "Assignments: Default",
                                    "filter_variable": "test_column",
                                    "filter_operator": "Is",
                                    "filter_value": "test_value",
                                },
                                {
                                    "table_name": "Assignments: Default",
                                    "filter_variable": "test_column2",
                                    "filter_operator": "Is",
                                    "filter_value": "test_value2",
                                },
                            ]
                        },
                        {
                            "filter_group": [
                                {
                                    "table_name": "Assignments: Default",
                                    "filter_variable": "test_column",
                                    "filter_operator": "Is",
                                    "filter_value": "test_value",
                                },
                                {
                                    "table_name": "Assignments: Default",
                                    "filter_variable": "test_column2",
                                    "filter_operator": "Is not",
                                    "filter_value": "test_value2",
                                },
                            ]
                        },
                    ],
                }
            ],
        }
        response = client.post(
            "/api/emails/template",
            json=payload,
            content_type="application/json",
            headers={"X-CSRF-Token": csrf_token},
        )
        print(response.json)
        assert response.status_code == 201
        return response.json["data"]

    @pytest.fixture
    def create_email_schedule(
        self,
        client,
        login_test_user,
        csrf_token,
        test_user_credentials,
        create_email_config,
    ):
        """
        Test fixture for creating an automated email schedule.
        """
        current_datetime = datetime.now()

        schedules = []

        # this will create 3 schedules with future dates starting with the current date
        # this is helpful because it will help with create assignment tests where we check for the next possible date
        for i in range(3):
            # Calculate future dates
            future_dates = [
                (current_datetime + timedelta(days=j)).strftime("%Y-%m-%d")
                for j in range(1 + i * 3, 4 + i * 3)
            ]
            # Add today's date

            # Calculate different times
            current_time = (current_datetime + timedelta(hours=i + 2)).time()

            # Calculate time based on iteration
            if i == 0:
                current_time_past = (current_datetime - timedelta(hours=i + 2)).time()
                formatted_time = current_time_past.strftime("%H:%M")
                future_dates.append(current_datetime.strftime("%Y-%m-%d"))
            elif i == 2:
                future_dates.append(current_datetime.strftime("%Y-%m-%d"))
                formatted_time = current_time.strftime("%H:%M")

            else:
                formatted_time = current_time.strftime("%H:%M")

            # Create payload
            payload = {
                "dates": future_dates,
                "time": formatted_time,
                "email_config_uid": create_email_config["email_config_uid"],
                "email_schedule_name": "Test Schedule " + str(i),
            }

            # Send request
            response = client.post(
                "/api/emails/schedule",
                json=payload,
                content_type="application/json",
                headers={"X-CSRF-Token": csrf_token},
            )
            assert response.status_code == 201

            # Append schedule data to the list
            schedules.append(response.json["data"])
        return schedules[0]

    @pytest.fixture
    def create_assignments(
        self,
        client,
        login_test_user,
        upload_enumerators_csv,
        upload_targets_csv,
        add_user_hierarchy,
        csrf_token,
    ):
        """
        Test fixture for initializing assignments

        """
        payload = {
            "assignments": [
                {"target_uid": 11000, "enumerator_uid": 1},
                {"target_uid": 14555, "enumerator_uid": 2},
            ],
            "form_uid": 1,
        }

        response = client.put(
            "/api/assignments",
            query_string={"form_uid": 1},
            json=payload,
            content_type="application/json",
            headers={"X-CSRF-Token": csrf_token},
        )
        print(response.json)
        assert response.status_code == 200

    ####################################################
    ## FIXTURES END HERE
    ####################################################

    def test_assignments_empty_assignment_table(
        self,
        client,
        login_test_user,
        upload_enumerators_csv,
        upload_targets_csv,
        add_user_hierarchy,
        csrf_token,
        request,
    ):
        """
        Test the assignments endpoint response when the assignment table is empty
        """
        # Check the response
        response = client.get("/api/assignments", query_string={"form_uid": 1})
        assert response.status_code == 200

        # Since this user is not mapped to child users with target mapping, the response should be empty
        """expected_response = {
            "data": [
                {
                    "assigned_enumerator_custom_fields": None,
                    "assigned_enumerator_email": None,
                    "assigned_enumerator_gender": None,
                    "assigned_enumerator_home_address": None,
                    "assigned_enumerator_id": None,
                    "assigned_enumerator_language": None,
                    "assigned_enumerator_mobile_primary": None,
                    "assigned_enumerator_name": None,
                    "assigned_enumerator_uid": None,
                    "completed_flag": None,
                    "custom_fields": {
                        "Address": "Hyderabad",
                        "Mobile no.": "1234567890",
                        "Name": "Anil",
                        "column_mapping": {
                            "custom_fields": [
                                {
                                    "column_name": "mobile_primary1",
                                    "field_label": "Mobile no.",
                                },
                                {"column_name": "name1", "field_label": "Name"},
                                {
                                    "column_name": "address1",
                                    "field_label": "Address",
                                },
                            ],
                            "gender": "gender1",
                            "language": "language1",
                            "location_id_column": "psu_id1",
                            "target_id": "target_id1",
                        },
                    },
                    "form_uid": 1,
                    "gender": "Male",
                    "language": "Telugu",
                    "last_attempt_survey_status": None,
                    "last_attempt_survey_status_label": "Not Attempted",
                    "final_survey_status": None,
                    "final_survey_status_label": "Not Attempted",
                    "scto_fields": None,
                    "supervisors": [
                        {
                            "role_name": "Regional Coordinator",
                            "role_uid": 3,
                            "supervisor_email": "newuser3@example.com",
                            "supervisor_name": "John Doe",
                        },
                        {
                            "role_name": "Cluster Coordinator",
                            "role_uid": 2,
                            "supervisor_email": "newuser2@example.com",
                            "supervisor_name": "Ron Doe",
                        },
                        {
                            "role_name": "Core User",
                            "role_uid": 1,
                            "supervisor_email": "newuser1@example.com",
                            "supervisor_name": "Tim Doe",
                        },
                    ],
                    "location_uid": 4,
                    "num_attempts": 0,
                    "refusal_flag": None,
                    "revisit_sections": None,
                    "target_assignable": True,
                    "target_id": "1",
                    "target_locations": [
                        {
                            "geo_level_name": "District",
                            "geo_level_uid": 1,
                            "location_id": "1",
                            "location_name": "ADILABAD",
                            "location_uid": 1,
                        },
                        {
                            "geo_level_name": "Mandal",
                            "geo_level_uid": 2,
                            "location_id": "1101",
                            "location_name": "ADILABAD RURAL",
                            "location_uid": 2,
                        },
                        {
                            "geo_level_name": "PSU",
                            "geo_level_uid": 3,
                            "location_id": "17101102",
                            "location_name": "ANKOLI",
                            "location_uid": 4,
                        },
                    ],
                    "target_uid": 1,
                    "webapp_tag_color": None,
                },
                {
                    "assigned_enumerator_custom_fields": None,
                    "assigned_enumerator_email": None,
                    "assigned_enumerator_gender": None,
                    "assigned_enumerator_home_address": None,
                    "assigned_enumerator_id": None,
                    "assigned_enumerator_language": None,
                    "assigned_enumerator_mobile_primary": None,
                    "assigned_enumerator_name": None,
                    "assigned_enumerator_uid": None,
                    "completed_flag": None,
                    "custom_fields": {
                        "Address": "South Delhi",
                        "Mobile no.": "1234567891",
                        "Name": "Anupama",
                        "column_mapping": {
                            "custom_fields": [
                                {
                                    "column_name": "mobile_primary1",
                                    "field_label": "Mobile no.",
                                },
                                {"column_name": "name1", "field_label": "Name"},
                                {
                                    "column_name": "address1",
                                    "field_label": "Address",
                                },
                            ],
                            "gender": "gender1",
                            "language": "language1",
                            "location_id_column": "psu_id1",
                            "target_id": "target_id1",
                        },
                    },
                    "form_uid": 1,
                    "gender": "Female",
                    "language": "Hindi",
                    "last_attempt_survey_status": None,
                    "last_attempt_survey_status_label": "Not Attempted",
                    "final_survey_status": None,
                    "final_survey_status_label": "Not Attempted",
                    "scto_fields": None,
                    "supervisors": [
                        {
                            "role_name": "Regional Coordinator",
                            "role_uid": 3,
                            "supervisor_email": "newuser3@example.com",
                            "supervisor_name": "John Doe",
                        },
                        {
                            "role_name": "Cluster Coordinator",
                            "role_uid": 2,
                            "supervisor_email": "newuser2@example.com",
                            "supervisor_name": "Ron Doe",
                        },
                        {
                            "role_name": "Core User",
                            "role_uid": 1,
                            "supervisor_email": "newuser1@example.com",
                            "supervisor_name": "Tim Doe",
                        },
                    ],
                    "location_uid": 4,
                    "num_attempts": 0,
                    "refusal_flag": None,
                    "revisit_sections": None,
                    "target_assignable": True,
                    "target_id": "2",
                    "target_locations": [
                        {
                            "geo_level_name": "District",
                            "geo_level_uid": 1,
                            "location_id": "1",
                            "location_name": "ADILABAD",
                            "location_uid": 1,
                        },
                        {
                            "geo_level_name": "Mandal",
                            "geo_level_uid": 2,
                            "location_id": "1101",
                            "location_name": "ADILABAD RURAL",
                            "location_uid": 2,
                        },
                        {
                            "geo_level_name": "PSU",
                            "geo_level_uid": 3,
                            "location_id": "17101102",
                            "location_name": "ANKOLI",
                            "location_uid": 4,
                        },
                    ],
                    "target_uid": 2,
                    "webapp_tag_color": None,
                },
            ],
            "success": True,
        }
        print(response.json)
        checkdiff = jsondiff.diff(expected_response, response.json)
        assert checkdiff == {}"""

    def test_assignments_create_assignments(
        self,
        app,
        client,
        login_test_user,
        upload_enumerators_csv,
        upload_targets_csv,
        add_user_hierarchy,
        csrf_token,
        request,
    ):
        """
        Test the create assignments endpoint
        """
        # Create 50 assignments with target_uids from 1-50 assigned to enumerator_uid 1
        assignments = [{"target_uid": i, "enumerator_uid": i} for i in range(1, 51)]

        payload = {
            "assignments": assignments,
            "form_uid": 1,
        }
        response = client.put(
            "/api/assignments",
            query_string={"form_uid": 1, "validate_mapping": True},
            json=payload,
            content_type="application/json",
            headers={"X-CSRF-Token": csrf_token},
        )
        print(response.json)

        assert response.status_code == 200

    def test_assignments_create_and_get_assignments(
        self,
        app,
        client,
        login_test_user,
        upload_enumerators_csv,
        upload_targets_csv,
        add_user_hierarchy,
        csrf_token,
        request,
    ):
        """
        Test the assignable targets endpoint
        """
        payload = {
            "assignments": [
                {"target_uid": 14000, "enumerator_uid": 1},
                {"target_uid": 12000, "enumerator_uid": 1},
            ],
            "form_uid": 1,
        }
        response = client.put(
            "/api/assignments",
            query_string={"form_uid": 1, "validate_mapping": True},
            json=payload,
            content_type="application/json",
            headers={"X-CSRF-Token": csrf_token},
        )
        print(response.json)

        assert response.status_code == 200
        response = client.get("/api/assignments/targets", query_string={"form_uid": 1})

        assert response.status_code == 200

        # Check the response
        """        expected_response = {
            "data": [
                {
                    "completed_flag": None,
                    "custom_fields": {
                        "Address": "Hyderabad",
                        "Mobile no.": "1234567890",
                        "Name": "Anil",
                        "column_mapping": {
                            "custom_fields": [
                                {
                                    "column_name": "mobile_primary1",
                                    "field_label": "Mobile no.",
                                },
                                {"column_name": "name1", "field_label": "Name"},
                                {
                                    "column_name": "address1",
                                    "field_label": "Address",
                                },
                            ],
                            "gender": "gender1",
                            "language": "language1",
                            "location_id_column": "psu_id1",
                            "target_id": "target_id1",
                        },
                    },
                    "final_survey_status": None,
                    "final_survey_status_label": None,
                    "form_uid": 1,
                    "gender": "Male",
                    "language": "Telugu",
                    "last_attempt_survey_status": None,
                    "last_attempt_survey_status_label": None,
                    "location_uid": 4,
                    "num_attempts": None,
                    "refusal_flag": None,
                    "revisit_sections": None,
                    "scto_fields": None,
                    "supervisors": [
                        {
                            "role_name": "Regional Coordinator",
                            "role_uid": 3,
                            "supervisor_email": "newuser3@example.com",
                            "supervisor_name": "John Doe",
                        },
                        {
                            "role_name": "Cluster Coordinator",
                            "role_uid": 2,
                            "supervisor_email": "newuser2@example.com",
                            "supervisor_name": "Ron Doe",
                        },
                        {
                            "role_name": "Core User",
                            "role_uid": 1,
                            "supervisor_email": "newuser1@example.com",
                            "supervisor_name": "Tim Doe",
                        },
                    ],
                    "target_assignable": None,
                    "target_id": "1",
                    "target_locations": [
                        {
                            "geo_level_name": "District",
                            "geo_level_uid": 1,
                            "location_id": "1",
                            "location_name": "ADILABAD",
                            "location_uid": 1,
                        },
                        {
                            "geo_level_name": "Mandal",
                            "geo_level_uid": 2,
                            "location_id": "1101",
                            "location_name": "ADILABAD RURAL",
                            "location_uid": 2,
                        },
                        {
                            "geo_level_name": "PSU",
                            "geo_level_uid": 3,
                            "location_id": "17101102",
                            "location_name": "ANKOLI",
                            "location_uid": 4,
                        },
                    ],
                    "target_uid": 1,
                    "webapp_tag_color": None,
                },
                {
                    "completed_flag": None,
                    "custom_fields": {
                        "Address": "South Delhi",
                        "Mobile no.": "1234567891",
                        "Name": "Anupama",
                        "column_mapping": {
                            "custom_fields": [
                                {
                                    "column_name": "mobile_primary1",
                                    "field_label": "Mobile no.",
                                },
                                {"column_name": "name1", "field_label": "Name"},
                                {
                                    "column_name": "address1",
                                    "field_label": "Address",
                                },
                            ],
                            "gender": "gender1",
                            "language": "language1",
                            "location_id_column": "psu_id1",
                            "target_id": "target_id1",
                        },
                    },
                    "final_survey_status": None,
                    "final_survey_status_label": None,
                    "form_uid": 1,
                    "gender": "Female",
                    "language": "Hindi",
                    "last_attempt_survey_status": None,
                    "last_attempt_survey_status_label": None,
                    "location_uid": 4,
                    "num_attempts": None,
                    "refusal_flag": None,
                    "revisit_sections": None,
                    "scto_fields": None,
                    "supervisors": [
                        {
                            "role_name": "Regional Coordinator",
                            "role_uid": 3,
                            "supervisor_email": "newuser3@example.com",
                            "supervisor_name": "John Doe",
                        },
                        {
                            "role_name": "Cluster Coordinator",
                            "role_uid": 2,
                            "supervisor_email": "newuser2@example.com",
                            "supervisor_name": "Ron Doe",
                        },
                        {
                            "role_name": "Core User",
                            "role_uid": 1,
                            "supervisor_email": "newuser1@example.com",
                            "supervisor_name": "Tim Doe",
                        },
                    ],
                    "target_assignable": None,
                    "target_id": "2",
                    "target_locations": [
                        {
                            "geo_level_name": "District",
                            "geo_level_uid": 1,
                            "location_id": "1",
                            "location_name": "ADILABAD",
                            "location_uid": 1,
                        },
                        {
                            "geo_level_name": "Mandal",
                            "geo_level_uid": 2,
                            "location_id": "1101",
                            "location_name": "ADILABAD RURAL",
                            "location_uid": 2,
                        },
                        {
                            "geo_level_name": "PSU",
                            "geo_level_uid": 3,
                            "location_id": "17101102",
                            "location_name": "ANKOLI",
                            "location_uid": 4,
                        },
                    ],
                    "target_uid": 2,
                    "webapp_tag_color": None,
                },
            ],
            "success": True,
        }

        print(response.json)
        checkdiff = jsondiff.diff(expected_response, response.json)
        assert checkdiff == {}"""

    def test_get_target_mapping(
        self,
        client,
        login_test_user,
        create_target_column_config,
        upload_targets_csv,
        request,
        csrf_token,
        add_user_hierarchy,
    ):
        """
        Test fetching the mapping config for targets

        """

        response = client.get(
            "/api/mapping/targets-mapping",
            query_string={"form_uid": 1},
            content_type="application/json",
        )
        print(response.json)

        assert response.status_code == 200
