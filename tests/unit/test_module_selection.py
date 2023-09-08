import jsondiff
import pytest
import re


@pytest.mark.module_selection
class TestModuleSelection:
    @pytest.fixture()
    def create_survey(self, client, login_test_user, csrf_token, test_user_credentials):
        """
        Insert new survey as a setup step for the survey tests
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
    def create_module_selection(
        self, client, login_test_user, csrf_token, test_user_credentials, create_survey
    ):
        """
        Insert new module_selection as a setup step for the module_selection tests
        """

        payload = {
            "survey_uid": 1,
            "modules": ["1", "2", "3", "4", "5", "6", "7", "8", "13", "14"],
        }

        response = client.post(
            "/api/module-status",
            json=payload,
            content_type="application/json",
            headers={"X-CSRF-Token": csrf_token},
        )
        assert response.status_code == 200

        yield

    def test_create_module_selection(
        self,
        client,
        login_test_user,
        create_module_selection,
        test_user_credentials,
    ):
        """
        Test that the create_module_selection is inserted correctly
        """

        # Test the survey was inserted correctly
        response = client.get("/api/module-status/1")
        assert response.status_code == 200

        expected_response = {
            "data": [
                {"config_status": "In Progress", "module_id": 1, "survey_uid": 1},
                {"config_status": "Not Started", "module_id": 2, "survey_uid": 1},
                {"config_status": "Not Started", "module_id": 3, "survey_uid": 1},
                {"config_status": "Not Started", "module_id": 4, "survey_uid": 1},
                {"config_status": "Not Started", "module_id": 5, "survey_uid": 1},
                {"config_status": "Not Started", "module_id": 6, "survey_uid": 1},
                {"config_status": "Not Started", "module_id": 7, "survey_uid": 1},
                {"config_status": "Not Started", "module_id": 8, "survey_uid": 1},
                {"config_status": "Not Started", "module_id": 13, "survey_uid": 1},
                {"config_status": "Not Started", "module_id": 14, "survey_uid": 1},
            ],
            "success": True,
        }

        checkdiff = jsondiff.diff(expected_response, response.json)
        assert checkdiff == {}

    @pytest.fixture()
    def update_module_selection(
        self, client, login_test_user, csrf_token, test_user_credentials, create_survey
    ):
        """
        Update new module_selection as a setup step for the module_selection tests
        """

        payload = {
            "survey_uid": 1,
            "modules": ["1", "2", "3", "4", "5", "6", "7", "8", "14"],
        }

        response = client.post(
            "/api/module-status",
            json=payload,
            content_type="application/json",
            headers={"X-CSRF-Token": csrf_token},
        )
        assert response.status_code == 200

        yield

    def test_update_module_selection(
        self,
        client,
        login_test_user,
        update_module_selection,
        test_user_credentials,
    ):
        """
        Test that the update_module_selection is update correctly
        """

        # Test the survey was inserted correctly
        response = client.get("/api/module-status/1")
        assert response.status_code == 200

        expected_response = {
            "data": [
                {"config_status": "In Progress", "module_id": 1, "survey_uid": 1},
                {"config_status": "Not Started", "module_id": 2, "survey_uid": 1},
                {"config_status": "Not Started", "module_id": 3, "survey_uid": 1},
                {"config_status": "Not Started", "module_id": 4, "survey_uid": 1},
                {"config_status": "Not Started", "module_id": 5, "survey_uid": 1},
                {"config_status": "Not Started", "module_id": 6, "survey_uid": 1},
                {"config_status": "Not Started", "module_id": 7, "survey_uid": 1},
                {"config_status": "Not Started", "module_id": 8, "survey_uid": 1},
                {"config_status": "Not Started", "module_id": 14, "survey_uid": 1},
            ],
            "success": True,
        }

        checkdiff = jsondiff.diff(expected_response, response.json)
        assert checkdiff == {}
