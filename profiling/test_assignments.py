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
    def create_form(
        self, client, login_test_user, csrf_token, create_module_questionnaire
    ):
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
            Path(__file__).resolve().parent / f"assets/sample_locations_small.csv"
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

        df = pd.read_csv(filepath, dtype=str)
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
        assert checkdiff == {}

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
                "email": "newuser1@example.com",
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
                "email": "newuser2@example.com",
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
                "email": "newuser3@example.com",
                "first_name": "John",
                "last_name": "Doe",
                "roles": [3],
                "gender": "Male",
                "languages": ["Hindi", "Telugu", "English"],
                "locations": [1],
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
    def add_user_hierarchy(
        self,
        client,
        login_test_user,
        csrf_token,
        create_roles,
        add_fsl_1_user,
        add_fsl_2_user,
        add_fsl_3_user,
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
                    "bulk_editable": False,
                },
                {
                    "column_name": "name",
                    "column_type": "personal_details",
                    "bulk_editable": False,
                },
                {
                    "column_name": "email",
                    "column_type": "personal_details",
                    "bulk_editable": False,
                },
                {
                    "column_name": "mobile_primary",
                    "column_type": "personal_details",
                    "bulk_editable": False,
                },
                {
                    "column_name": "language",
                    "column_type": "personal_details",
                    "bulk_editable": True,
                },
                {
                    "column_name": "home_address",
                    "column_type": "personal_details",
                    "bulk_editable": False,
                },
                {
                    "column_name": "gender",
                    "column_type": "personal_details",
                    "bulk_editable": False,
                },
                {
                    "column_name": "prime_geo_level_location",
                    "column_type": "location",
                    "bulk_editable": True,
                },
                {
                    "column_name": "Mobile (Secondary)",
                    "column_type": "custom_fields",
                    "bulk_editable": True,
                },
                {
                    "column_name": "Age",
                    "column_type": "custom_fields",
                    "bulk_editable": False,
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
            Path(__file__).resolve().parent / f"assets/sample_enumerators_small.csv"
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
                    "bulk_editable": False,
                    "contains_pii": False,
                },
                {
                    "column_name": "language",
                    "column_type": "basic_details",
                    "bulk_editable": True,
                    "contains_pii": True,
                },
                {
                    "column_name": "gender",
                    "column_type": "basic_details",
                    "bulk_editable": False,
                    "contains_pii": True,
                },
                {
                    "column_name": "Name",
                    "column_type": "custom_fields",
                    "bulk_editable": False,
                    "contains_pii": True,
                },
                {
                    "column_name": "Mobile no.",
                    "column_type": "custom_fields",
                    "bulk_editable": False,
                    "contains_pii": True,
                },
                {
                    "column_name": "Address",
                    "column_type": "custom_fields",
                    "bulk_editable": True,
                    "contains_pii": True,
                },
                {
                    "column_name": "bottom_geo_level_location",
                    "column_type": "location",
                    "bulk_editable": True,
                    "contains_pii": True,
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
    def upload_targets_csv(self, client, login_test_user, create_locations, csrf_token):
        """
        Upload the targets csv
        """

        filepath = Path(__file__).resolve().parent / f"assets/sample_targets_small.csv"

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
            "config_name": "Assignments",
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
                {"target_uid": 1, "enumerator_uid": 1},
                {"target_uid": 2, "enumerator_uid": 2},
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

        # Since this user is not mapped to child users with target mapping, the response should be empty
        expected_response = {
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
                            "role_name": "Core User",
                            "role_uid": 1,
                            "supervisor_email": "newuser1@example.com",
                            "supervisor_name": "Tim Doe",
                        },
                        {
                            "role_name": "Cluster Coordinator",
                            "role_uid": 2,
                            "supervisor_email": "newuser2@example.com",
                            "supervisor_name": "Ron Doe",
                        },
                        {
                            "role_name": "Regional Coordinator",
                            "role_uid": 3,
                            "supervisor_email": "newuser3@example.com",
                            "supervisor_name": "John Doe",
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
                            "role_name": "Core User",
                            "role_uid": 1,
                            "supervisor_email": "newuser1@example.com",
                            "supervisor_name": "Tim Doe",
                        },
                        {
                            "role_name": "Cluster Coordinator",
                            "role_uid": 2,
                            "supervisor_email": "newuser2@example.com",
                            "supervisor_name": "Ron Doe",
                        },
                        {
                            "role_name": "Regional Coordinator",
                            "role_uid": 3,
                            "supervisor_email": "newuser3@example.com",
                            "supervisor_name": "John Doe",
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
        assert checkdiff == {}

    def test_multiple_assignments(
        self,
        client,
        login_test_user,
        upload_enumerators_csv,
        upload_targets_csv,
        add_user_hierarchy,
        csrf_token,
    ):
        """
        Test creating assignments between multiple targets and enumerators
        """

        payload = {
            "assignments": [
                {"target_uid": 1, "enumerator_uid": 1},
                {"target_uid": 2, "enumerator_uid": 2},
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

        assert response.status_code == 200

        expected_response = {
            "data": [
                {
                    "assigned_enumerator_custom_fields": {
                        "Age": "1",
                        "Mobile (Secondary)": "1123456789",
                        "column_mapping": {
                            "custom_fields": [
                                {
                                    "column_name": "mobile_secondary1",
                                    "field_label": "Mobile (Secondary)",
                                },
                                {"column_name": "age1", "field_label": "Age"},
                            ],
                            "email": "email1",
                            "enumerator_id": "enumerator_id1",
                            "enumerator_type": "enumerator_type1",
                            "gender": "gender1",
                            "home_address": "home_address1",
                            "language": "language1",
                            "location_id_column": "district_id1",
                            "mobile_primary": "mobile_primary1",
                            "name": "name1",
                        },
                    },
                    "assigned_enumerator_email": "eric.dodge@idinsight.org",
                    "assigned_enumerator_gender": "Male",
                    "assigned_enumerator_home_address": "my house",
                    "assigned_enumerator_id": "0294612",
                    "assigned_enumerator_language": "English",
                    "assigned_enumerator_mobile_primary": "0123456789",
                    "assigned_enumerator_name": "Eric Dodge",
                    "assigned_enumerator_uid": 1,
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
                                {"column_name": "address1", "field_label": "Address"},
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
                            "role_name": "Core User",
                            "role_uid": 1,
                            "supervisor_email": "newuser1@example.com",
                            "supervisor_name": "Tim Doe",
                        },
                        {
                            "role_name": "Cluster Coordinator",
                            "role_uid": 2,
                            "supervisor_email": "newuser2@example.com",
                            "supervisor_name": "Ron Doe",
                        },
                        {
                            "role_name": "Regional Coordinator",
                            "role_uid": 3,
                            "supervisor_email": "newuser3@example.com",
                            "supervisor_name": "John Doe",
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
                    "assigned_enumerator_custom_fields": {
                        "Age": "2",
                        "Mobile (Secondary)": "1123456789",
                        "column_mapping": {
                            "custom_fields": [
                                {
                                    "column_name": "mobile_secondary1",
                                    "field_label": "Mobile (Secondary)",
                                },
                                {"column_name": "age1", "field_label": "Age"},
                            ],
                            "email": "email1",
                            "enumerator_id": "enumerator_id1",
                            "enumerator_type": "enumerator_type1",
                            "gender": "gender1",
                            "home_address": "home_address1",
                            "language": "language1",
                            "location_id_column": "district_id1",
                            "mobile_primary": "mobile_primary1",
                            "name": "name1",
                        },
                    },
                    "assigned_enumerator_email": "jahnavi.meher@idinsight.org",
                    "assigned_enumerator_gender": "Female",
                    "assigned_enumerator_home_address": "my house",
                    "assigned_enumerator_id": "0294613",
                    "assigned_enumerator_language": "Telugu",
                    "assigned_enumerator_mobile_primary": "0123456789",
                    "assigned_enumerator_name": "Jahnavi Meher",
                    "assigned_enumerator_uid": 2,
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
                                {"column_name": "address1", "field_label": "Address"},
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
                            "role_name": "Core User",
                            "role_uid": 1,
                            "supervisor_email": "newuser1@example.com",
                            "supervisor_name": "Tim Doe",
                        },
                        {
                            "role_name": "Cluster Coordinator",
                            "role_uid": 2,
                            "supervisor_email": "newuser2@example.com",
                            "supervisor_name": "Ron Doe",
                        },
                        {
                            "role_name": "Regional Coordinator",
                            "role_uid": 3,
                            "supervisor_email": "newuser3@example.com",
                            "supervisor_name": "John Doe",
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

        # Check the response
        response = client.get("/api/assignments", query_string={"form_uid": 1})

        checkdiff = jsondiff.diff(expected_response, response.json)
        assert checkdiff == {}

    def test_upload_assignments_overwrite_csv(
        self,
        client,
        login_test_user,
        create_assignments,
        csrf_token,
        request,
        create_email_config,
        create_email_schedule,
    ):
        """
        Function to test uploading asssignments csv with overwrite mode
        """

        filepath = Path(__file__).resolve().parent / f"assets/sample_assignments.csv"

        # Read the targets.csv file and convert it to base64
        with open(filepath, "rb") as f:
            assignments_csv = f.read()
            assignments_csv_encoded = base64.b64encode(assignments_csv).decode("utf-8")

        # Try to upload the targets csv
        payload = {
            "column_mapping": {
                "target_id": "target_id1",
                "enumerator_id": "enumerator_id1",
            },
            "file": assignments_csv_encoded,
            "mode": "overwrite",
        }

        response = client.post(
            "/api/assignments",
            query_string={"form_uid": 1},
            json=payload,
            content_type="application/json",
            headers={"X-CSRF-Token": csrf_token},
        )

        current_datetime = datetime.now()
        formatted_date = current_datetime.strftime("%a, %d %b %Y") + " 00:00:00 GMT"
        current_time = datetime.now().strftime("%H:%M")

        # Define the format corresponding to the date string
        date_format = "%a, %d %b %Y %H:%M:%S %Z"

        assert response.status_code == 200
        assert datetime.strptime(
            response.json["data"]["email_schedule"]["schedule_date"],
            date_format,
        ) >= datetime.strptime(formatted_date, date_format)
        expected_put_response = {
            "data": {
                "assignments_count": 2,
                "new_assignments_count": 2,
                "no_changes_count": 0,
                "re_assignments_count": 0,
                "email_schedule": {
                    "config_name": "Assignments",
                    "dates": response.json["data"]["email_schedule"]["dates"],
                    "schedule_date": response.json["data"]["email_schedule"][
                        "schedule_date"
                    ],
                    "current_time": current_time,
                    "email_schedule_uid": response.json["data"]["email_schedule"][
                        "email_schedule_uid"
                    ],
                    "email_config_uid": 1,
                    "time": response.json["data"]["email_schedule"]["time"],
                },
            },
            "message": "Success",
        }

        checkdiff = jsondiff.diff(expected_put_response, response.json)
        assert checkdiff == {}

        expected_response = {
            "data": [
                {
                    "assigned_enumerator_custom_fields": {
                        "Age": "2",
                        "Mobile (Secondary)": "1123456789",
                        "column_mapping": {
                            "custom_fields": [
                                {
                                    "column_name": "mobile_secondary1",
                                    "field_label": "Mobile (Secondary)",
                                },
                                {"column_name": "age1", "field_label": "Age"},
                            ],
                            "email": "email1",
                            "enumerator_id": "enumerator_id1",
                            "enumerator_type": "enumerator_type1",
                            "gender": "gender1",
                            "home_address": "home_address1",
                            "language": "language1",
                            "location_id_column": "district_id1",
                            "mobile_primary": "mobile_primary1",
                            "name": "name1",
                        },
                    },
                    "assigned_enumerator_email": "jahnavi.meher@idinsight.org",
                    "assigned_enumerator_gender": "Female",
                    "assigned_enumerator_home_address": "my house",
                    "assigned_enumerator_id": "0294613",
                    "assigned_enumerator_language": "Telugu",
                    "assigned_enumerator_mobile_primary": "0123456789",
                    "assigned_enumerator_name": "Jahnavi Meher",
                    "assigned_enumerator_uid": 2,
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
                            "role_name": "Core User",
                            "role_uid": 1,
                            "supervisor_email": "newuser1@example.com",
                            "supervisor_name": "Tim Doe",
                        },
                        {
                            "role_name": "Cluster Coordinator",
                            "role_uid": 2,
                            "supervisor_email": "newuser2@example.com",
                            "supervisor_name": "Ron Doe",
                        },
                        {
                            "role_name": "Regional Coordinator",
                            "role_uid": 3,
                            "supervisor_email": "newuser3@example.com",
                            "supervisor_name": "John Doe",
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
                    "assigned_enumerator_custom_fields": {
                        "Age": "4",
                        "Mobile (Secondary)": "1123456789",
                        "column_mapping": {
                            "custom_fields": [
                                {
                                    "column_name": "mobile_secondary1",
                                    "field_label": "Mobile (Secondary)",
                                },
                                {"column_name": "age1", "field_label": "Age"},
                            ],
                            "email": "email1",
                            "enumerator_id": "enumerator_id1",
                            "enumerator_type": "enumerator_type1",
                            "gender": "gender1",
                            "home_address": "home_address1",
                            "language": "language1",
                            "location_id_column": "district_id1",
                            "mobile_primary": "mobile_primary1",
                            "name": "name1",
                        },
                    },
                    "assigned_enumerator_email": "griffin.muteti@idinsight.org",
                    "assigned_enumerator_gender": "Male",
                    "assigned_enumerator_home_address": "my house",
                    "assigned_enumerator_id": "0294615",
                    "assigned_enumerator_language": "Swahili",
                    "assigned_enumerator_mobile_primary": "0123456789",
                    "assigned_enumerator_name": "Griffin Muteti",
                    "assigned_enumerator_uid": 4,
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
                            "role_name": "Core User",
                            "role_uid": 1,
                            "supervisor_email": "newuser1@example.com",
                            "supervisor_name": "Tim Doe",
                        },
                        {
                            "role_name": "Cluster Coordinator",
                            "role_uid": 2,
                            "supervisor_email": "newuser2@example.com",
                            "supervisor_name": "Ron Doe",
                        },
                        {
                            "role_name": "Regional Coordinator",
                            "role_uid": 3,
                            "supervisor_email": "newuser3@example.com",
                            "supervisor_name": "John Doe",
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

        # Check the response
        response = client.get("/api/assignments", query_string={"form_uid": 1})

        checkdiff = jsondiff.diff(expected_response, response.json)
        assert checkdiff == {}

    def test_eligible_enumerators(
        self,
        app,
        client,
        login_test_user,
        upload_enumerators_csv,
        upload_targets_csv,
        add_user_hierarchy,
        csrf_token,
    ):
        """
        Test the assignable enumerators endpoint
        We will also check that the productivity stats are correct
        """

        payload = {
            "assignments": [
                {"target_uid": 1, "enumerator_uid": 1},
                {"target_uid": 2, "enumerator_uid": 2},
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
        assert response.status_code == 200

        # Check the response
        expected_response = {
            "data": [
                {
                    "custom_fields": {
                        "Age": "1",
                        "Mobile (Secondary)": "1123456789",
                        "column_mapping": {
                            "custom_fields": [
                                {
                                    "column_name": "mobile_secondary1",
                                    "field_label": "Mobile (Secondary)",
                                },
                                {"column_name": "age1", "field_label": "Age"},
                            ],
                            "email": "email1",
                            "enumerator_id": "enumerator_id1",
                            "enumerator_type": "enumerator_type1",
                            "gender": "gender1",
                            "home_address": "home_address1",
                            "language": "language1",
                            "location_id_column": "district_id1",
                            "mobile_primary": "mobile_primary1",
                            "name": "name1",
                        },
                    },
                    "email": "eric.dodge@idinsight.org",
                    "enumerator_id": "0294612",
                    "surveyor_locations": [
                        {
                            "geo_level_name": "District",
                            "geo_level_uid": 1,
                            "location_id": "1",
                            "location_name": "ADILABAD",
                            "location_uid": 1,
                        }
                    ],
                    "enumerator_uid": 1,
                    "form_productivity": {
                        "test_scto_input_output": {
                            "form_name": "Agrifieldnet Main Form",
                            "scto_form_id": "test_scto_input_output",
                            "total_assigned_targets": 1,
                            "total_completed_targets": 0,
                            "total_pending_targets": 1,
                            "avg_num_completed_per_day": 0,
                            "avg_num_submissions_per_day": 0,
                        }
                    },
                    "gender": "Male",
                    "home_address": "my house",
                    "language": "English",
                    "mobile_primary": "0123456789",
                    "name": "Eric Dodge",
                    "supervisors": [
                        {
                            "role_name": "Core User",
                            "role_uid": 1,
                            "supervisor_email": "newuser1@example.com",
                            "supervisor_name": "Tim Doe",
                        },
                        {
                            "role_name": "Cluster Coordinator",
                            "role_uid": 2,
                            "supervisor_email": "newuser2@example.com",
                            "supervisor_name": "Ron Doe",
                        },
                        {
                            "role_name": "Regional Coordinator",
                            "role_uid": 3,
                            "supervisor_email": "newuser3@example.com",
                            "supervisor_name": "John Doe",
                        },
                    ],
                    "surveyor_status": "Active",
                },
                {
                    "custom_fields": {
                        "Age": "2",
                        "Mobile (Secondary)": "1123456789",
                        "column_mapping": {
                            "custom_fields": [
                                {
                                    "column_name": "mobile_secondary1",
                                    "field_label": "Mobile (Secondary)",
                                },
                                {"column_name": "age1", "field_label": "Age"},
                            ],
                            "email": "email1",
                            "enumerator_id": "enumerator_id1",
                            "enumerator_type": "enumerator_type1",
                            "gender": "gender1",
                            "home_address": "home_address1",
                            "language": "language1",
                            "location_id_column": "district_id1",
                            "mobile_primary": "mobile_primary1",
                            "name": "name1",
                        },
                    },
                    "email": "jahnavi.meher@idinsight.org",
                    "enumerator_id": "0294613",
                    "surveyor_locations": [
                        {
                            "geo_level_name": "District",
                            "geo_level_uid": 1,
                            "location_id": "1",
                            "location_name": "ADILABAD",
                            "location_uid": 1,
                        }
                    ],
                    "enumerator_uid": 2,
                    "form_productivity": {
                        "test_scto_input_output": {
                            "form_name": "Agrifieldnet Main Form",
                            "scto_form_id": "test_scto_input_output",
                            "total_assigned_targets": 1,
                            "total_completed_targets": 0,
                            "total_pending_targets": 1,
                            "avg_num_completed_per_day": 0,
                            "avg_num_submissions_per_day": 0,
                        }
                    },
                    "gender": "Female",
                    "home_address": "my house",
                    "language": "Telugu",
                    "mobile_primary": "0123456789",
                    "name": "Jahnavi Meher",
                    "supervisors": [
                        {
                            "role_name": "Core User",
                            "role_uid": 1,
                            "supervisor_email": "newuser1@example.com",
                            "supervisor_name": "Tim Doe",
                        },
                        {
                            "role_name": "Cluster Coordinator",
                            "role_uid": 2,
                            "supervisor_email": "newuser2@example.com",
                            "supervisor_name": "Ron Doe",
                        },
                        {
                            "role_name": "Regional Coordinator",
                            "role_uid": 3,
                            "supervisor_email": "newuser3@example.com",
                            "supervisor_name": "John Doe",
                        },
                    ],
                    "surveyor_status": "Active",
                },
                {
                    "custom_fields": {
                        "Age": "4",
                        "Mobile (Secondary)": "1123456789",
                        "column_mapping": {
                            "custom_fields": [
                                {
                                    "column_name": "mobile_secondary1",
                                    "field_label": "Mobile (Secondary)",
                                },
                                {"column_name": "age1", "field_label": "Age"},
                            ],
                            "email": "email1",
                            "enumerator_id": "enumerator_id1",
                            "enumerator_type": "enumerator_type1",
                            "gender": "gender1",
                            "home_address": "home_address1",
                            "language": "language1",
                            "location_id_column": "district_id1",
                            "mobile_primary": "mobile_primary1",
                            "name": "name1",
                        },
                    },
                    "email": "griffin.muteti@idinsight.org",
                    "enumerator_id": "0294615",
                    "surveyor_locations": [
                        {
                            "geo_level_name": "District",
                            "geo_level_uid": 1,
                            "location_id": "1",
                            "location_name": "ADILABAD",
                            "location_uid": 1,
                        }
                    ],
                    "enumerator_uid": 4,
                    "form_productivity": {
                        "test_scto_input_output": {
                            "form_name": "Agrifieldnet Main Form",
                            "scto_form_id": "test_scto_input_output",
                            "total_assigned_targets": 0,
                            "total_completed_targets": 0,
                            "total_pending_targets": 0,
                            "avg_num_completed_per_day": 0,
                            "avg_num_submissions_per_day": 0,
                        }
                    },
                    "gender": "Male",
                    "home_address": "my house",
                    "language": "Swahili",
                    "mobile_primary": "0123456789",
                    "name": "Griffin Muteti",
                    "supervisors": [
                        {
                            "role_name": "Core User",
                            "role_uid": 1,
                            "supervisor_email": "newuser1@example.com",
                            "supervisor_name": "Tim Doe",
                        },
                        {
                            "role_name": "Cluster Coordinator",
                            "role_uid": 2,
                            "supervisor_email": "newuser2@example.com",
                            "supervisor_name": "Ron Doe",
                        },
                        {
                            "role_name": "Regional Coordinator",
                            "role_uid": 3,
                            "supervisor_email": "newuser3@example.com",
                            "supervisor_name": "John Doe",
                        },
                    ],
                    "surveyor_status": "Active",
                },
            ],
            "success": True,
        }

        response = client.get(
            "/api/assignments/enumerators", query_string={"form_uid": 1}
        )

        print(response.json)
        checkdiff = jsondiff.diff(expected_response, response.json)
        assert checkdiff == {}

    def test_asssignment_targets(
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
        response = client.get("/api/assignments/targets", query_string={"form_uid": 1})

        response.status_code == 200

        # Check the response
        expected_response = {
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
                            "role_name": "Core User",
                            "role_uid": 1,
                            "supervisor_email": "newuser1@example.com",
                            "supervisor_name": "Tim Doe",
                        },
                        {
                            "role_name": "Cluster Coordinator",
                            "role_uid": 2,
                            "supervisor_email": "newuser2@example.com",
                            "supervisor_name": "Ron Doe",
                        },
                        {
                            "role_name": "Regional Coordinator",
                            "role_uid": 3,
                            "supervisor_email": "newuser3@example.com",
                            "supervisor_name": "John Doe",
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
                            "role_name": "Core User",
                            "role_uid": 1,
                            "supervisor_email": "newuser1@example.com",
                            "supervisor_name": "Tim Doe",
                        },
                        {
                            "role_name": "Cluster Coordinator",
                            "role_uid": 2,
                            "supervisor_email": "newuser2@example.com",
                            "supervisor_name": "Ron Doe",
                        },
                        {
                            "role_name": "Regional Coordinator",
                            "role_uid": 3,
                            "supervisor_email": "newuser3@example.com",
                            "supervisor_name": "John Doe",
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
        assert checkdiff == {}
