import base64
from pathlib import Path

import jsondiff
import pandas as pd
import pytest
from utils import (
    create_new_survey_role_with_permissions,
    login_user,
    update_logged_in_user_roles,
)


@pytest.mark.notifications
class TestNotifications:
    @pytest.fixture
    def user_with_super_admin_permissions(self, client, test_user_credentials):
        # Set the user to have super admin permissions
        update_logged_in_user_roles(
            client,
            test_user_credentials,
            is_survey_admin=True,
            survey_uid=1,
            is_super_admin=True,
        )
        login_user(client, test_user_credentials)

    @pytest.fixture
    def user_with_survey_admin_permissions(self, client, test_user_credentials):
        # Set the user to have survey admin permissions
        update_logged_in_user_roles(
            client,
            test_user_credentials,
            is_survey_admin=True,
            survey_uid=1,
            is_super_admin=False,
        )
        update_logged_in_user_roles(
            client,
            test_user_credentials,
            is_survey_admin=False,
            survey_uid=2,
            is_super_admin=False,
            roles=[],
        )
        login_user(client, test_user_credentials)

    @pytest.fixture
    def user_with_assignments_permissions(self, client, test_user_credentials):
        # Assign new roles and permissions
        new_role = create_new_survey_role_with_permissions(
            client,
            test_user_credentials,
            "Assignments Role",
            [9],
            1,
        )

        update_logged_in_user_roles(
            client,
            test_user_credentials,
            is_survey_admin=False,
            survey_uid=1,
            is_super_admin=False,
            roles=[1],
        )

        login_user(client, test_user_credentials)

    @pytest.fixture
    def user_with_no_permissions(self, client, test_user_credentials):
        # Assign no roles and permissions
        update_logged_in_user_roles(
            client,
            test_user_credentials,
            is_survey_admin=False,
            survey_uid=2,
            is_super_admin=False,
            roles=[],
        )
        update_logged_in_user_roles(
            client,
            test_user_credentials,
            is_survey_admin=False,
            survey_uid=1,
            is_super_admin=False,
            roles=[],
        )

        login_user(client, test_user_credentials)

    @pytest.fixture(
        params=[
            ("user_with_super_admin_permissions", True),
            ("user_with_survey_admin_permissions", True),
            ("user_with_assignments_permissions", True),
            ("user_with_no_permissions", False),
        ],
        ids=[
            "super_admin_permissions",
            "survey_admin_permissions",
            "assignment_permissions",
            "no_permissions",
        ],
    )
    def user_permissions(self, request):
        return request.param

    @pytest.fixture()
    def create_survey(self, client, login_test_user, csrf_token, test_user_credentials):
        """
        Insert new survey as a setup step for the form tests
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
    def create_second_survey(
        self, client, login_test_user, csrf_token, test_user_credentials, create_survey
    ):
        """
        Insert new survey as a setup step for the form tests
        """

        payload = {
            "survey_id": "test_survey2",
            "survey_name": "Test Survey2",
            "survey_description": "A test survey",
            "project_name": "Test Project",
            "surveying_method": "in-person",
            "irb_approval": "Yes",
            "planned_start_date": "2021-01-01",
            "planned_end_date": "2021-12-31",
            "state": "Draft",
            "config_status": "In Progress - Configuration",
            "created_by_user_uid": 1,
        }

        response = client.post(
            "/api/surveys",
            query_string={"user_uid": 1},
            json=payload,
            content_type="application/json",
            headers={"X-CSRF-Token": csrf_token},
        )
        assert response.status_code == 201

        yield

    @pytest.fixture()
    def update_module_selection(
        self, client, login_test_user, csrf_token, test_user_credentials, create_survey
    ):
        """
        Update new module_selection as a setup step for the module_selection tests
        """

        payload = {
            "survey_uid": 1,
            "modules": ["1", "2", "3", "4", "5", "7", "8", "9", "13", "14"],
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
    def update_second_survey_module_selection(
        self,
        client,
        login_test_user,
        csrf_token,
        test_user_credentials,
        create_second_survey,
    ):
        """
        Update new module_selection as a setup step for the module_selection tests
        """

        payload = {
            "survey_uid": 2,
            "modules": ["9", "11"],
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
    def create_module_questionnaire(
        self,
        client,
        login_test_user,
        csrf_token,
        test_user_credentials,
        create_survey,
        update_module_selection,
    ):
        """
        Insert new module_questionnaire as a setup step for the module_questionnaire tests
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
        Insert new form as a setup step for the form tests
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
    def create_geo_levels_for_targets_file(
        self, client, login_test_user, csrf_token, create_form
    ):
        """
        Insert new geo levels as a setup step for the location upload tests
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
        print(response.json)

        assert response.status_code == 200

        yield

    @pytest.fixture()
    def create_locations(
        self,
        client,
        login_test_user,
        create_geo_levels_for_targets_file,
        csrf_token,
    ):
        """
        Upload locations csv as a setup step for the targets upload tests
        """

        filepath = (
            Path(__file__).resolve().parent
            / f"data/file_uploads/sample_locations_small.csv"
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
                    "column_source": "target_id1",
                },
                {
                    "column_name": "language",
                    "column_type": "basic_details",
                    "bulk_editable": True,
                    "contains_pii": True,
                    "column_source": "language",
                },
                {
                    "column_name": "gender",
                    "column_type": "basic_details",
                    "bulk_editable": False,
                    "contains_pii": True,
                    "column_source": "gender",
                },
                {
                    "column_name": "Name",
                    "column_type": "custom_fields",
                    "bulk_editable": False,
                    "contains_pii": True,
                    "column_source": "name",
                },
                {
                    "column_name": "Mobile no.",
                    "column_type": "custom_fields",
                    "bulk_editable": False,
                    "contains_pii": True,
                    "column_source": "mobile_primary",
                },
                {
                    "column_name": "Address",
                    "column_type": "custom_fields",
                    "bulk_editable": True,
                    "contains_pii": True,
                    "column_source": "address",
                },
                {
                    "column_name": "bottom_geo_level_location",
                    "column_type": "location",
                    "bulk_editable": True,
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
    def create_target_config(self, client, csrf_token, login_test_user, create_form):
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

        filepath = (
            Path(__file__).resolve().parent
            / f"data/file_uploads/sample_targets_small.csv"
        )

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
            Path(__file__).resolve().parent
            / f"data/file_uploads/sample_enumerators_small.csv"
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
        print(response.json)
        assert response.status_code == 200

    @pytest.fixture()
    def create_scto_question_mapping(
        self, client, csrf_token, login_test_user, create_form
    ):
        """
        Test that the SCTO question mapping is inserted correctly
        """

        # Insert the SCTO question mapping
        payload = {
            "form_uid": 1,
            "survey_status": "test_survey_status_error",
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

    @pytest.fixture()
    def create_survey_notification(
        self, client, login_test_user, csrf_token, create_form
    ):
        """
        Create Survey Notification
        """

        payload = {
            "survey_uid": 1,
            "module_id": 1,
            "resolution_status": "in progress",
            "message": "Your survey end date is approaching",
            "severity": "warning",
            "type": "survey",
        }
        response = client.post(
            "/api/notifications",
            json=payload,
            content_type="application/json",
            headers={"X-CSRF-Token": csrf_token},
        )
        print(response.json)
        assert response.status_code == 200

        yield

    @pytest.fixture()
    def create_survey_notification_for_assignments(
        self, client, login_test_user, csrf_token, create_survey_notification
    ):
        """
        Create Survey Notification
        """

        payload = {
            "survey_uid": 1,
            "module_id": 9,
            "resolution_status": "in progress",
            "message": "No user mappings found",
            "severity": "error",
            "type": "survey",
        }
        response = client.post(
            "/api/notifications",
            json=payload,
            content_type="application/json",
            headers={"X-CSRF-Token": csrf_token},
        )
        print(response.json)
        assert response.status_code == 200

        yield

    @pytest.fixture()
    def create_second_survey_notification_for_assignments(
        self,
        client,
        login_test_user,
        csrf_token,
        create_survey_notification_for_assignments,
        create_second_survey,
        update_second_survey_module_selection,
    ):
        """
        Create Survey Notification
        """

        payload = {
            "survey_uid": 2,
            "module_id": 9,
            "resolution_status": "in progress",
            "message": "No user mappings found",
            "severity": "error",
            "type": "survey",
        }
        response = client.post(
            "/api/notifications",
            json=payload,
            content_type="application/json",
            headers={"X-CSRF-Token": csrf_token},
        )
        print(response.json)
        assert response.status_code == 200

        yield

    @pytest.fixture()
    def create_second_survey_notification_for_DQ(
        self,
        client,
        login_test_user,
        csrf_token,
        create_second_survey_notification_for_assignments,
        create_second_survey,
        update_second_survey_module_selection,
    ):
        """
        Create Survey Notification
        """

        payload = {
            "survey_uid": 2,
            "module_id": 11,
            "resolution_status": "in progress",
            "message": "DQ: Survey status variable missing",
            "severity": "error",
            "type": "survey",
        }
        response = client.post(
            "/api/notifications",
            json=payload,
            content_type="application/json",
            headers={"X-CSRF-Token": csrf_token},
        )
        print(response.json)
        assert response.status_code == 200

        yield

    @pytest.fixture()
    def create_user_notification(
        self, client, login_test_user, csrf_token, create_form
    ):
        """
        Create User Notifications
        """

        payload = {
            "user_uid": 1,
            "resolution_status": "in progress",
            "message": "Your password has been reset",
            "severity": "alert",
            "type": "user",
        }

        # add a delay to ensure the notification is created after the survey notification
        response = client.post(
            "/api/notifications",
            json=payload,
            content_type="application/json",
            headers={"X-CSRF-Token": csrf_token},
        )
        print(response.json)
        assert response.status_code == 200

        yield

    def test_notifications_create_user_notifications(
        self,
        client,
        login_test_user,
        create_form,
        csrf_token,
    ):
        payload = {
            "user_uid": 1,
            "resolution_status": "in progress",
            "message": "End date reached",
            "severity": "alert",
            "type": "user",
        }
        response = client.post(
            "/api/notifications",
            json=payload,
            content_type="application/json",
            headers={"X-CSRF-Token": csrf_token},
        )

        print(response.json)
        assert response.status_code == 200
        expected_response = {
            "success": True,
            "message": "Notification created successfully",
            "data": {
                "notification_uid": 1,
                "severity": "alert",
                "resolution_status": "in progress",
                "message": "End date reached",
            },
        }

        response_json = response.json
        # Remove the created_at from the response for comparison
        if "data" in response_json and "created_at" in response_json["data"]:
            del response_json["data"]["created_at"]

        checkdiff = jsondiff.diff(expected_response, response_json)
        assert checkdiff == {}

    def test_notifications_create_user_notifications_user_not_found(
        self,
        client,
        login_test_user,
        create_form,
        csrf_token,
    ):
        payload = {
            "user_uid": 1717166,
            "resolution_status": "in progress",
            "message": "Password changed",
            "severity": "alert",
            "type": "user",
        }
        response = client.post(
            "/api/notifications",
            json=payload,
            content_type="application/json",
            headers={"X-CSRF-Token": csrf_token},
        )

        print(response.json)
        assert response.status_code == 404
        expected_response = {"error": "User not found", "success": False}

        checkdiff = jsondiff.diff(expected_response, response.json)
        assert checkdiff == {}

    def test_notifications_create_user_notifications_with_error(
        self,
        client,
        login_test_user,
        create_form,
        csrf_token,
    ):
        payload = {
            "user_uid": 1,
            "resolution_status": "in progressss",
            "severity": "alerttt",
        }
        response = client.post(
            "/api/notifications",
            json=payload,
            content_type="application/json",
            headers={"X-CSRF-Token": csrf_token},
        )

        print(response.json)
        assert response.status_code == 422
        expected_response = {
            "message": {
                "severity": [
                    "Invalid Notification severity, valid values are alert, warning, error"
                ],
                "resolution_status": [
                    "Invalid Resolution Status valid values are in progress, done"
                ],
                "message": ["This field is required."],
                "type": ["This field is required."],
            },
            "success": False,
        }

        checkdiff = jsondiff.diff(expected_response, response.json)
        assert checkdiff == {}

    def test_notifications_create_notification_error_no_survey_or_user(
        self,
        client,
        login_test_user,
        create_form,
        csrf_token,
    ):
        payload = {
            "resolution_status": "in progress",
            "message": "End date reached",
            "severity": "alert",
        }
        response = client.post(
            "/api/notifications",
            json=payload,
            content_type="application/json",
            headers={"X-CSRF-Token": csrf_token},
        )

        print(response.json)
        assert response.status_code == 422
        expected_response = {
            "message": {
                "type": ["This field is required."],
            },
            "success": False,
        }

        checkdiff = jsondiff.diff(expected_response, response.json)
        assert checkdiff == {}

    def test_notifications_create_survey_notifications(
        self,
        client,
        login_test_user,
        create_survey_notification,
        csrf_token,
        test_user_credentials,
    ):
        payload = {
            "survey_uid": 1,
            "module_id": 4,
            "resolution_status": "in progress",
            "message": "End date reached",
            "severity": "error",
            "type": "survey",
        }
        response = client.post(
            "/api/notifications",
            json=payload,
            content_type="application/json",
            headers={"X-CSRF-Token": csrf_token},
        )

        print(response.json)
        assert response.status_code == 200
        expected_response = {
            "success": True,
            "message": "Notification created successfully",
            "data": {
                "notification_uid": 2,
                "severity": "error",
                "resolution_status": "in progress",
                "message": "End date reached",
            },
        }

        response_json = response.json
        # Remove the created_at from the response for comparison
        if "data" in response_json and "created_at" in response_json["data"]:
            del response_json["data"]["created_at"]

        checkdiff = jsondiff.diff(expected_response, response_json)
        assert checkdiff == {}

        get_module_response = client.get(
            "/api/module-status/1",
            content_type="application/json",
            headers={"X-CSRF-Token": csrf_token},
        )
        print(get_module_response.json)

        expected_response = {
            "success": True,
            "data": [
                {"survey_uid": 1, "module_id": 1, "config_status": "Done"},
                {"survey_uid": 1, "module_id": 2, "config_status": "Done"},
                {
                    "survey_uid": 1,
                    "module_id": 3,
                    "config_status": "In Progress - Incomplete",
                },
                {"survey_uid": 1, "module_id": 4, "config_status": "Error"},
                {"survey_uid": 1, "module_id": 5, "config_status": "Not Started"},
                {"survey_uid": 1, "module_id": 7, "config_status": "Not Started"},
                {"survey_uid": 1, "module_id": 8, "config_status": "Not Started"},
                {"survey_uid": 1, "module_id": 9, "config_status": "Not Started"},
                {"survey_uid": 1, "module_id": 13, "config_status": "Not Started"},
                {"survey_uid": 1, "module_id": 14, "config_status": "Done"},
                {"survey_uid": 1, "module_id": 17, "config_status": "Not Started"},
                {"survey_uid": 1, "module_id": 16, "config_status": "Not Started"},
            ],
        }

        assert get_module_response.json == expected_response

        # Test the get all surveys endpoint returns error status
        response = client.get("/api/surveys")
        assert response.status_code == 200

        expected_response = {
            "data": [
                {
                    "survey_uid": 1,
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
                    "last_updated_at": "2023-05-30 00:00:00",
                    "created_by_user_uid": test_user_credentials["user_uid"],
                    "error": True,
                }
            ],
            "success": True,
        }

        # Replace the last_updated_at field in the expected response with the value from the actual response
        expected_response["data"][0]["last_updated_at"] = response.json["data"][0][
            "last_updated_at"
        ]
        checkdiff = jsondiff.diff(expected_response, response.json)
        assert checkdiff == {}

    def test_notifications_create_survey_notifications_error_no_survey(
        self,
        client,
        login_test_user,
        create_form,
        csrf_token,
    ):
        payload = {
            "survey_uid": 1234563634356789045677,
            "module_id": 4,
            "resolution_status": "in progress",
            "message": "End date reached",
            "severity": "alert",
            "type": "survey",
        }
        response = client.post(
            "/api/notifications",
            json=payload,
            content_type="application/json",
            headers={"X-CSRF-Token": csrf_token},
        )

        print(response.json)
        assert response.status_code == 404
        expected_response = {"error": "Survey not found", "success": False}

        checkdiff = jsondiff.diff(expected_response, response.json)
        assert checkdiff == {}

    def test_notifications_create_survey_notifications_error_no_module(
        self,
        client,
        login_test_user,
        create_form,
        csrf_token,
    ):
        payload = {
            "survey_uid": 1,
            "module_id": 4123450,
            "resolution_status": "in progress",
            "message": "End date reached",
            "severity": "alert",
            "type": "survey",
        }
        response = client.post(
            "/api/notifications",
            json=payload,
            content_type="application/json",
            headers={"X-CSRF-Token": csrf_token},
        )

        print(response.json)
        assert response.status_code == 404
        expected_response = {"error": "Module not found", "success": False}

        checkdiff = jsondiff.diff(expected_response, response.json)
        assert checkdiff == {}

    def test_notifications_get_user_notifications_blank_notifications(
        self,
        client,
        login_test_user,
        create_form,
        csrf_token,
    ):
        response = client.get(
            "/api/notifications",
            content_type="application/json",
            headers={"X-CSRF-Token": csrf_token},
        )

        print(response.json)
        assert response.status_code == 200
        expected_response = {
            "success": True,
            "data": [],
        }

        checkdiff = jsondiff.diff(expected_response, response.json)
        assert checkdiff == {}

    def test_notifications_get_user_notifications_all_notifications(
        self,
        client,
        create_user_notification,
        create_second_survey_notification_for_DQ,
        csrf_token,
        user_permissions,
        request,
    ):
        """
        TEST Get user notifications based on multiple roles
        Expect:
            Super Admin: All notifications
            Survey Admin: Only 1st survey's notification
            No permission: Only user notification
            Assignment Role user :
                1st Survey Assignment Notifications
                2nd Survey Admin - All notifications
                User notifications
        """
        user_fixture, expected_permission = user_permissions
        request.getfixturevalue(user_fixture)

        response = client.get(
            "/api/notifications",
            content_type="application/json",
            headers={"X-CSRF-Token": csrf_token},
        )

        print(response.json)
        assert response.status_code == 200
        if user_fixture == "user_with_super_admin_permissions":
            expected_response = {
                "success": True,
                "data": [
                    {
                        "survey_id": "test_survey2",
                        "survey_uid": 2,
                        "module_name": "Data Quality",
                        "module_id": 11,
                        "notification_uid": 4,
                        "severity": "error",
                        "resolution_status": "in progress",
                        "message": "DQ: Survey status variable missing",
                        "type": "survey",
                    },
                    {
                        "survey_id": "test_survey2",
                        "survey_uid": 2,
                        "module_name": "Assignments",
                        "module_id": 9,
                        "notification_uid": 3,
                        "severity": "error",
                        "resolution_status": "in progress",
                        "message": "No user mappings found",
                        "type": "survey",
                    },
                    {
                        "survey_id": "test_survey",
                        "survey_uid": 1,
                        "module_name": "Assignments",
                        "module_id": 9,
                        "notification_uid": 2,
                        "severity": "error",
                        "resolution_status": "in progress",
                        "message": "No user mappings found",
                        "type": "survey",
                    },
                    {
                        "survey_id": "test_survey",
                        "survey_uid": 1,
                        "module_name": "Background Details",
                        "module_id": 1,
                        "notification_uid": 1,
                        "severity": "warning",
                        "resolution_status": "in progress",
                        "message": "Your survey end date is approaching",
                        "type": "survey",
                    },
                    {
                        "type": "user",
                        "notification_uid": 1,
                        "severity": "alert",
                        "resolution_status": "in progress",
                        "message": "Your password has been reset",
                    },
                ],
            }
        elif user_fixture == "user_with_survey_admin_permissions":
            expected_response = {
                "success": True,
                "data": [
                    {
                        "survey_id": "test_survey",
                        "survey_uid": 1,
                        "module_name": "Assignments",
                        "module_id": 9,
                        "notification_uid": 2,
                        "severity": "error",
                        "resolution_status": "in progress",
                        "message": "No user mappings found",
                        "type": "survey",
                    },
                    {
                        "survey_id": "test_survey",
                        "survey_uid": 1,
                        "module_name": "Background Details",
                        "module_id": 1,
                        "notification_uid": 1,
                        "severity": "warning",
                        "resolution_status": "in progress",
                        "message": "Your survey end date is approaching",
                        "type": "survey",
                    },
                    {
                        "type": "user",
                        "notification_uid": 1,
                        "severity": "alert",
                        "resolution_status": "in progress",
                        "message": "Your password has been reset",
                    },
                ],
            }
        elif user_fixture == "user_with_assignments_permissions":
            expected_response = {
                "success": True,
                "data": [
                    {
                        "survey_id": "test_survey2",
                        "survey_uid": 2,
                        "module_name": "Data Quality",
                        "module_id": 11,
                        "notification_uid": 4,
                        "severity": "error",
                        "resolution_status": "in progress",
                        "message": "DQ: Survey status variable missing",
                        "type": "survey",
                    },
                    {
                        "survey_id": "test_survey2",
                        "survey_uid": 2,
                        "module_name": "Assignments",
                        "module_id": 9,
                        "notification_uid": 3,
                        "severity": "error",
                        "resolution_status": "in progress",
                        "message": "No user mappings found",
                        "type": "survey",
                    },
                    {
                        "survey_id": "test_survey",
                        "survey_uid": 1,
                        "module_name": "Assignments",
                        "module_id": 9,
                        "notification_uid": 2,
                        "severity": "error",
                        "resolution_status": "in progress",
                        "message": "No user mappings found",
                        "type": "survey",
                    },
                    {
                        "type": "user",
                        "notification_uid": 1,
                        "severity": "alert",
                        "resolution_status": "in progress",
                        "message": "Your password has been reset",
                    },
                ],
            }
        else:
            expected_response = {
                "success": True,
                "data": [
                    {
                        "notification_uid": 1,
                        "severity": "alert",
                        "resolution_status": "in progress",
                        "message": "Your password has been reset",
                        "type": "user",
                    }
                ],
            }
        response_json = response.json

        # Remove the created_at from the response for comparison
        for notification in response_json.get("data", []):
            if "created_at" in notification:
                del notification["created_at"]
            else:
                print("Created_at missing in notification", notification)
                assert False

        checkdiff = jsondiff.diff(expected_response, response_json)
        assert checkdiff == {}

    def test_notifications_update_user_notification(
        self,
        client,
        login_test_user,
        create_user_notification,
        csrf_token,
    ):
        payload = {
            "type": "user",
            "notification_uid": 1,
            "resolution_status": "done",
            "message": "Your password has been reset",
            "severity": "alert",
        }
        response = client.put(
            "/api/notifications",
            json=payload,
            content_type="application/json",
            headers={"X-CSRF-Token": csrf_token},
        )
        print(response.json)
        assert response.status_code == 200

        expected_response = {
            "success": True,
            "message": "Notification updated successfully",
            "data": {
                "notification_uid": 1,
                "severity": "alert",
                "resolution_status": "done",
                "message": "Your password has been reset",
            },
        }

        response_json = response.json

        # Remove the created_at from the response for comparison
        if "data" in response_json and "created_at" in response_json["data"]:
            del response_json["data"]["created_at"]

        checkdiff = jsondiff.diff(expected_response, response_json)
        assert checkdiff == {}

    def test_notifications_update_survey_notification(
        self,
        client,
        login_test_user,
        create_survey_notification,
        csrf_token,
    ):
        payload = {
            "type": "survey",
            "notification_uid": 1,
            "severity": "alert",
            "resolution_status": "done",
            "message": "Your survey ended yesterday",
        }

        response = client.put(
            "/api/notifications",
            json=payload,
            content_type="application/json",
            headers={"X-CSRF-Token": csrf_token},
        )
        print(response.json)
        assert response.status_code == 200

        expected_response = {
            "success": True,
            "message": "Notification updated successfully",
            "data": {
                "notification_uid": 1,
                "severity": "alert",
                "resolution_status": "done",
                "message": "Your survey ended yesterday",
            },
        }

        response_json = response.json

        # Remove the created_at from the response for comparison
        if "data" in response_json and "created_at" in response_json["data"]:
            del response_json["data"]["created_at"]

        checkdiff = jsondiff.diff(expected_response, response_json)
        assert checkdiff == {}

    def test_notifications_update_survey_notification_error_no_notification_exists(
        self,
        client,
        login_test_user,
        create_user_notification,
        csrf_token,
    ):
        payload = {
            "type": "survey",
            "notification_uid": 1,
            "severity": "alert",
            "resolution_status": "done",
            "message": "Your survey ended yesterday",
        }

        response = client.put(
            "/api/notifications",
            json=payload,
            content_type="application/json",
            headers={"X-CSRF-Token": csrf_token},
        )
        print(response.json)
        assert response.status_code == 404

        expected_response = {"error": "Notification not found", "success": False}

        checkdiff = jsondiff.diff(expected_response, response.json)
        assert checkdiff == {}

    def test_notifications_update_notification_error_no_notification_uid(
        self,
        client,
        login_test_user,
        create_user_notification,
        csrf_token,
    ):
        payload = {
            "type": "survey",
            "severity": "alert",
            "resolution_status": "done",
            "message": "Your survey ended yesterday",
        }
        response = client.put(
            "/api/notifications",
            json=payload,
            content_type="application/json",
            headers={"X-CSRF-Token": csrf_token},
        )
        print(response.json)
        assert response.status_code == 422
        expected_response = {
            "message": {"notification_uid": ["This field is required."]},
            "success": False,
        }

        checkdiff = jsondiff.diff(expected_response, response.json)
        assert checkdiff == {}

    def test_notifications_resolve_notification(
        self,
        client,
        login_test_user,
        create_survey_notification_for_assignments,
        csrf_token,
    ):
        payload = {
            "survey_uid": 1,
            "module_id": 9,
            "resolution_status": "done",
        }
        response = client.patch(
            "/api/notifications",
            json=payload,
            content_type="application/json",
            headers={"X-CSRF-Token": csrf_token},
        )
        print(response.json)
        assert response.status_code == 200

        get_response = client.get(
            "/api/notifications",
            content_type="application/json",
            headers={"X-CSRF-Token": csrf_token},
        )
        assert get_response.status_code == 200

        print(get_response.json)

        expected_response = {
            "success": True,
            "data": [
                {
                    "survey_id": "test_survey",
                    "survey_uid": 1,
                    "module_name": "Assignments",
                    "module_id": 9,
                    "type": "survey",
                    "notification_uid": 2,
                    "severity": "error",
                    "resolution_status": "done",
                    "message": "No user mappings found",
                },
                {
                    "survey_id": "test_survey",
                    "survey_uid": 1,
                    "module_name": "Background Details",
                    "module_id": 1,
                    "type": "survey",
                    "notification_uid": 1,
                    "severity": "warning",
                    "resolution_status": "in progress",
                    "message": "Your survey end date is approaching",
                },
            ],
        }

        response_json = get_response.json

        # Remove the created_at from the response for comparison
        for notification in response_json.get("data", []):
            if "created_at" in notification:
                del notification["created_at"]
            else:
                print("Created_at missing in notification", notification)
                assert False

        checkdiff = jsondiff.diff(expected_response, response_json)
        assert checkdiff == {}

        get_module_response = client.get(
            "/api/module-status/1",
            content_type="application/json",
            headers={"X-CSRF-Token": csrf_token},
        )
        print(get_module_response.json)

        assert get_module_response.status_code == 200

        expected_get_module_response = {
            "success": True,
            "data": [
                {"survey_uid": 1, "module_id": 1, "config_status": "Done"},
                {"survey_uid": 1, "module_id": 2, "config_status": "Done"},
                {
                    "survey_uid": 1,
                    "module_id": 3,
                    "config_status": "In Progress - Incomplete",
                },
                {
                    "survey_uid": 1,
                    "module_id": 4,
                    "config_status": "In Progress - Incomplete",
                },
                {"survey_uid": 1, "module_id": 5, "config_status": "Not Started"},
                {"survey_uid": 1, "module_id": 7, "config_status": "Not Started"},
                {"survey_uid": 1, "module_id": 8, "config_status": "Not Started"},
                {"survey_uid": 1, "module_id": 9, "config_status": "Not Started"},
                {"survey_uid": 1, "module_id": 13, "config_status": "Not Started"},
                {"survey_uid": 1, "module_id": 14, "config_status": "Done"},
                {"survey_uid": 1, "module_id": 17, "config_status": "Not Started"},
                {"survey_uid": 1, "module_id": 16, "config_status": "Not Started"},
            ],
        }
        checkdiff = jsondiff.diff(
            get_module_response.json, expected_get_module_response
        )

        assert checkdiff == {}

    def test_create_action_notification_without_any_data(
        self, client, login_test_user, csrf_token, create_form
    ):
        """
        Test create notification without any data in modules

        Expect:
            No Notification created
        """
        payload = {
            "survey_uid": 1,
            "action": "Location hierarchy changed",
            "form_uid": 1,
        }
        response = client.post(
            "/api/notifications/action",
            json=payload,
            content_type="application/json",
            headers={"X-CSRF-Token": csrf_token},
        )

        print(response.json)
        assert response.status_code == 422
        expected_response = {
            "error": "No notification created for the action, conditions not met",
            "success": False,
        }

        response_json = response.json

        checkdiff = jsondiff.diff(expected_response, response_json)
        assert checkdiff == {}

    def test_create_action_notification_no_enum(
        self, client, login_test_user, csrf_token, create_form, upload_targets_csv
    ):
        """
        Test create notification with targets and locations data

        Expect:
            Notification created for target and locations
        """
        payload = {
            "survey_uid": 1,
            "action": "Location hierarchy changed",
            "form_uid": 1,
        }
        response = client.post(
            "/api/notifications/action",
            json=payload,
            content_type="application/json",
            headers={"X-CSRF-Token": csrf_token},
        )

        print(response.json)
        assert response.status_code == 200
        expected_response = {
            "success": True,
            "message": "Notification created successfully",
        }

        response_json = response.json

        checkdiff = jsondiff.diff(expected_response, response_json)
        assert checkdiff == {}
        query_string = {
            "user_uid": 1,
        }
        get_response = client.get(
            "/api/notifications",
            query_string=query_string,
            content_type="application/json",
            headers={"X-CSRF-Token": csrf_token},
        )

        print(get_response.json)
        assert get_response.status_code == 200

        expected_get_response = {
            "success": True,
            "data": [
                {
                    "survey_id": "test_survey",
                    "survey_uid": 1,
                    "module_name": "Locations",
                    "module_id": 5,
                    "type": "survey",
                    "notification_uid": 1,
                    "severity": "error",
                    "resolution_status": "in progress",
                    "message": "Location hierarchy has been changed for this survey. Kindly reupload the locations data.",
                }
            ],
        }

        get_response_json = get_response.json

        # Remove the created_at from the response for comparison
        for notification in get_response_json.get("data", []):
            if "created_at" in notification:
                del notification["created_at"]
            else:
                print("Created_at missing in notification", notification)
                assert False

        checkdiff = jsondiff.diff(expected_get_response, get_response_json)
        assert checkdiff == {}

    def test_create_action_notification_all(
        self,
        client,
        login_test_user,
        csrf_token,
        create_form,
        upload_targets_csv,
        upload_enumerators_csv,
    ):
        """
        Test create notification with targets, locations,enumerators data existing

        Expect:
            Notification created for targets, locations, enumerators
        """
        payload = {
            "survey_uid": 1,
            "action": "Locations reuploaded",
            "form_uid": 1,
        }
        response = client.post(
            "/api/notifications/action",
            json=payload,
            content_type="application/json",
            headers={"X-CSRF-Token": csrf_token},
        )

        print(response.json)
        assert response.status_code == 200
        expected_response = {
            "success": True,
            "message": "Notification created successfully",
        }

        response_json = response.json

        checkdiff = jsondiff.diff(expected_response, response_json)
        assert checkdiff == {}
        query_string = {
            "user_uid": 1,
        }
        get_response = client.get(
            "/api/notifications",
            query_string=query_string,
            content_type="application/json",
            headers={"X-CSRF-Token": csrf_token},
        )

        print(get_response.json)
        assert get_response.status_code == 200

        expected_get_response = {
            "success": True,
            "data": [
                {
                    "survey_id": "test_survey",
                    "survey_uid": 1,
                    "module_name": "Enumerators",
                    "module_id": 7,
                    "type": "survey",
                    "notification_uid": 1,
                    "severity": "error",
                    "resolution_status": "in progress",
                    "message": "Locations data has been reuploaded for this survey. Kindly reupload the enumerators data.",
                },
                {
                    "survey_id": "test_survey",
                    "survey_uid": 1,
                    "module_name": "Targets",
                    "module_id": 8,
                    "type": "survey",
                    "notification_uid": 2,
                    "severity": "error",
                    "resolution_status": "in progress",
                    "message": "Locations data has been reuploaded for this survey. Kindly reupload the targets data.",
                },
                {
                    "survey_id": "test_survey",
                    "survey_uid": 1,
                    "module_name": "User and Role Management",
                    "module_id": 4,
                    "type": "survey",
                    "notification_uid": 3,
                    "severity": "error",
                    "resolution_status": "in progress",
                    "message": "Locations data has been reuploaded for this survey. Kindly update user location details.",
                },
            ],
        }

        get_response_json = get_response.json
        print(get_response_json)
        # Remove the created_at from the response for comparison
        for notification in get_response_json.get("data", []):
            if "created_at" in notification:
                del notification["created_at"]
            else:
                print("Created_at missing in notification", notification)
                assert False

        checkdiff = jsondiff.diff(expected_get_response, get_response_json)
        assert checkdiff == {}

    def test_create_duplicate_notification(
        self,
        client,
        login_test_user,
        csrf_token,
        create_form,
        upload_targets_csv,
        upload_enumerators_csv,
    ):
        """
        Test create duplicate notification

        Expect:
            Error 422
        """
        payload = {
            "survey_uid": 1,
            "action": "Locations reuploaded",
            "form_uid": 1,
        }
        response = client.post(
            "/api/notifications/action",
            json=payload,
            content_type="application/json",
            headers={"X-CSRF-Token": csrf_token},
        )

        print(response.json)
        assert response.status_code == 200
        expected_response = {
            "success": True,
            "message": "Notification created successfully",
        }

        response_json = response.json

        checkdiff = jsondiff.diff(expected_response, response_json)
        assert checkdiff == {}

        # Send the same request again
        duplicate_response = client.post(
            "/api/notifications/action",
            json=payload,
            content_type="application/json",
            headers={"X-CSRF-Token": csrf_token},
        )
        print(duplicate_response.json)
        assert response.status_code == 200

    def test_check_module_error(
        self,
        client,
        login_test_user,
        csrf_token,
        create_form,
        upload_targets_csv,
        upload_enumerators_csv,
    ):
        payload = {
            "survey_uid": 1,
            "action": "Locations reuploaded",
            "form_uid": 1,
        }
        response = client.post(
            "/api/notifications/action",
            json=payload,
            content_type="application/json",
            headers={"X-CSRF-Token": csrf_token},
        )
        get_config_status = client.get(
            "/api/surveys/1/config-status",
            content_type="application/json",
            headers={"X-CSRF-Token": csrf_token},
        )

        expected_response = {
            "success": True,
            "data": {
                "overall_status": "In Progress - Configuration",
                "Background Details": {"status": "Done", "optional": False},
                "Feature Selection": {"status": "Done", "optional": False},
                "Survey Information": [
                    {
                        "name": "SurveyCTO Integration",
                        "status": "In Progress - Incomplete",
                        "optional": False,
                    },
                    {
                        "name": "User and Role Management",
                        "status": "Error",
                        "optional": False,
                    },
                    {"name": "Locations", "status": "Done", "optional": False},
                    {"name": "Enumerators", "status": "Error", "optional": False},
                    {"name": "Targets", "status": "Error", "optional": False},
                    {
                        "name": "Survey Status for Targets",
                        "status": "Done",
                        "optional": False,
                    },
                    {"name": "Supervisor Mapping", "status": "Not Started", "optional": False},
                ],
                "Module Configuration": [
                    {
                        "module_id": 9,
                        "name": "Assignments",
                        "status": "In Progress",
                        "optional": False,
                    },
                    {
                        "module_id": 13,
                        "name": "Surveyor Hiring",
                        "status": "Not Started",
                        "optional": False,
                    },
                    {
                        "module_id": 16,
                        "name": "Assignments Column Configuration",
                        "status": "Not Started",
                        "optional": True,
                    },
                ],
                "completion_stats": {
                    "num_modules": 10,
                    "num_completed": 4,
                    "num_in_progress": 1,
                    "num_in_progress_incomplete": 1,
                    "num_not_started": 1,
                    "num_error": 3,
                    "num_optional": 0,
                },
            },
        }

        print(get_config_status.json)
        checkdiff = jsondiff.diff(expected_response, get_config_status.json)

        assert checkdiff == {}

    def test_get_errored_modules(
        self,
        client,
        login_test_user,
        csrf_token,
        create_form,
        upload_targets_csv,
        upload_enumerators_csv,
    ):
        """
        Test that errored modules can be retrieved
        """

        payload = {
            "survey_uid": 1,
            "action": "Locations reuploaded",
            "form_uid": 1,
        }
        response = client.post(
            "/api/notifications/action",
            json=payload,
            content_type="application/json",
            headers={"X-CSRF-Token": csrf_token},
        )

        response = client.get("/api/surveys/1/modules")
        print(response.json)
        assert response.status_code == 200

        expected_response = {
            "data": [
                {"module_id": 1, "name": "Background Details", "error": False},
                {"module_id": 2, "name": "Feature Selection", "error": False},
                {"module_id": 3, "name": "SurveyCTO Integration", "error": False},
                {"module_id": 4, "name": "User and Role Management", "error": True},
                {"module_id": 5, "name": "Locations", "error": False},
                {"module_id": 7, "name": "Enumerators", "error": True},
                {"module_id": 8, "name": "Targets", "error": True},
                {"module_id": 9, "name": "Assignments", "error": False},
                {"module_id": 13, "name": "Surveyor Hiring", "error": False},
                {"module_id": 14, "name": "Survey Status for Targets", "error": False},
                {
                    "module_id": 16,
                    "name": "Assignments Column Configuration",
                    "error": False,
                },
                {"module_id": 17, "name": "Supervisor Mapping", "error": False},
            ],
            "success": True,
        }

        checkdiff = jsondiff.diff(expected_response, response.json)
        assert checkdiff == {}

    def test_create_bulk_notifications(
        self,
        client,
        login_test_user,
        csrf_token,
        create_form,
        upload_targets_csv,
        upload_enumerators_csv,
    ):
        """
        Test Create multiple notifications together using bulk endpoint

        Expect: Success
        """
        payload = {
            "actions": [
                {
                    "survey_uid": 1,
                    "action": "Location hierarchy changed",
                    "form_uid": 1,
                },
                {
                    "survey_uid": 1,
                    "action": "Prime location updated",
                    "form_uid": 1,
                },
            ]
        }
        response = client.post(
            "/api/notifications/action/bulk",
            json=payload,
            content_type="application/json",
            headers={"X-CSRF-Token": csrf_token},
        )
        print(response.json)
        assert response.status_code == 200
        expected_response = {
            "success": True,
            "message": "Notifications created successfully",
            "data": [
                {
                    "survey_uid": "1",
                    "action": "Location hierarchy changed",
                    "message": "Notification created successfully",
                },
                {
                    "survey_uid": "1",
                    "action": "Prime location updated",
                    "message": "Notification created successfully",
                },
            ],
        }

        response_json = response.json

        checkdiff = jsondiff.diff(expected_response, response_json)
        assert checkdiff == {}

    def test_create_bulk_notifications_error(
        self,
        client,
        login_test_user,
        csrf_token,
        create_form,
        upload_targets_csv,
        upload_enumerators_csv,
    ):
        """
        Test Create multiple notifications together using bulk endpoint when actions have error

        Expect: 422, Errored action reported back
        """
        payload = {
            "actions": [
                {
                    "survey_uid": 1,
                    "action": "Location hierarchy changed",
                    "form_uid": 1,
                },
                {
                    "survey_uid": 1,
                    "action": "Prime Location updated_errror",
                    "form_uid": 1,
                },
            ]
        }
        response = client.post(
            "/api/notifications/action/bulk",
            json=payload,
            content_type="application/json",
            headers={"X-CSRF-Token": csrf_token},
        )

        print(response.json)
        assert response.status_code == 422

        expected_response = {
            "error": ["Action Prime Location updated_errror not found"],
            "success": False,
        }

        response_json = response.json

        checkdiff = jsondiff.diff(expected_response, response_json)
        assert checkdiff == {}

    def test_refresh_scto_form_definition_mapping_variable_missing(
        self, client, login_test_user, csrf_token, create_scto_question_mapping
    ):
        """
        Test that refreshing the scto form definition from SCTO gives the same result
        """

        # Ingest the SCTO variables from SCTO into the database
        response = client.post(
            "/api/forms/1/scto-form-definition/refresh",
            headers={"X-CSRF-Token": csrf_token},
        )
        assert response.status_code == 200

        # Check if any notification raised
        get_response = client.get(
            "/api/notifications",
            content_type="application/json",
            headers={"X-CSRF-Token": csrf_token},
        )
        print(get_response.json)
        assert get_response.status_code == 200

        expected_get_response = {
            "success": True,
            "data": [
                {
                    "survey_id": "test_survey",
                    "survey_uid": 1,
                    "module_name": "SurveyCTO Integration",
                    "module_id": 3,
                    "type": "survey",
                    "notification_uid": 1,
                    "severity": "error",
                    "resolution_status": "in progress",
                    "message": "Following SCTO Question mapping variables are missing in form definition: test_enumerator_id, test_location_1, test_revisit_section, test_survey_status_error, test_target_id. Please review form changes.",
                }
            ],
        }

        get_response_json = get_response.json
        print(get_response_json)
        # Remove the created_at from the response for comparison
        for notification in get_response_json.get("data", []):
            if "created_at" in notification:
                del notification["created_at"]
            else:
                print("Created_at missing in notification", notification)
                assert False

        checkdiff = jsondiff.diff(expected_get_response, get_response_json)
        assert checkdiff == {}
