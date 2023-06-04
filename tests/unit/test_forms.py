import jsondiff
import pytest
from utils import load_reference_data


@pytest.mark.forms
class TestForms:
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
    def create_form(self, client, login_test_user, csrf_token, create_survey):
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
            "scto_variable_mapping": "",
        }

        response = client.post(
            "/api/forms",
            json=payload,
            content_type="application/json",
            headers={"X-CSRF-Token": csrf_token},
        )
        assert response.status_code == 201

        yield

    def test_create_form(self, client, login_test_user, create_form):
        """
        Test that the form is inserted correctly
        """

        # Test the form was inserted correctly
        response = client.get("/api/forms?survey_uid=1")
        assert response.status_code == 200

        expected_response = {
            "data": [
                {
                    "form_uid": 1,
                    "survey_uid": 1,
                    "scto_form_id": "test_scto_input_output",
                    "form_name": "Agrifieldnet Main Form",
                    "tz_name": "Asia/Kolkata",
                    "scto_server_name": "dod",
                    "encryption_key_shared": True,
                    "server_access_role_granted": True,
                    "server_access_allowed": True,
                    "scto_variable_mapping": "",
                    "last_ingested_at": None,
                }
            ],
            "success": True,
        }

        checkdiff = jsondiff.diff(expected_response, response.json)
        assert checkdiff == {}

    def test_get_forms(
        self, client, login_test_user, create_form, test_user_credentials
    ):
        """
        Test the different ways to get forms
        """

        expected_response = {
            "data": [
                {
                    "form_uid": 1,
                    "survey_uid": 1,
                    "scto_form_id": "test_scto_input_output",
                    "form_name": "Agrifieldnet Main Form",
                    "tz_name": "Asia/Kolkata",
                    "scto_server_name": "dod",
                    "encryption_key_shared": True,
                    "server_access_role_granted": True,
                    "server_access_allowed": True,
                    "scto_variable_mapping": "",
                    "last_ingested_at": None,
                }
            ],
            "success": True,
        }

        # Get the form using the survey_uid
        response = client.get("/api/forms?survey_uid=1")
        assert response.status_code == 200

        checkdiff = jsondiff.diff(expected_response, response.json)
        assert checkdiff == {}

        # Get the form without a filter
        response = client.get("/api/forms")
        assert response.status_code == 200

        checkdiff = jsondiff.diff(expected_response, response.json)
        assert checkdiff == {}

        # Get the form using the form_uid
        response = client.get("/api/forms/1")
        assert response.status_code == 200

        expected_response["data"] = expected_response["data"][0]

        checkdiff = jsondiff.diff(expected_response, response.json)
        assert checkdiff == {}

    def test_update_form(self, client, login_test_user, create_form, csrf_token):
        """
        Test that an existing form can be updated
        """

        payload = {
            "scto_form_id": "agrifieldnet_scto_form",
            "form_name": "Agrifieldnet Main Form",
            "tz_name": "Asia/Kolkata",
            "scto_server_name": "hki",
            "encryption_key_shared": False,
            "server_access_role_granted": False,
            "server_access_allowed": False,
            "scto_variable_mapping": {"test": "test"},
        }

        response = client.put(
            "/api/forms/1",
            json=payload,
            content_type="application/json",
            headers={"X-CSRF-Token": csrf_token},
        )
        assert response.status_code == 200

        response = client.get("/api/forms/1")
        assert response.status_code == 200

        expected_response = {
            "data": {
                "form_uid": 1,
                "survey_uid": 1,
                "scto_form_id": "agrifieldnet_scto_form",
                "form_name": "Agrifieldnet Main Form",
                "tz_name": "Asia/Kolkata",
                "scto_server_name": "hki",
                "encryption_key_shared": False,
                "server_access_role_granted": False,
                "server_access_allowed": False,
                "scto_variable_mapping": "{'test': 'test'}",
                "last_ingested_at": None,
            },
            "success": True,
        }

        checkdiff = jsondiff.diff(expected_response, response.json)
        assert checkdiff == {}

    def test_delete_form(self, client, login_test_user, create_form, csrf_token):
        """
        Test that a form can be deleted
        """

        response = client.delete(
            "/api/forms/1",
            headers={"X-CSRF-Token": csrf_token},
        )
        assert response.status_code == 204

        # Check the response
        response = client.get("/api/forms/1")

        assert response.status_code == 404

    def test_delete_survey_cascade_to_form(
        self, client, login_test_user, create_form, csrf_token
    ):
        """
        Test that deleting the survey deletes the form
        """

        response = client.delete(
            "/api/surveys/1",
            headers={"X-CSRF-Token": csrf_token},
        )
        assert response.status_code == 204

        # Check the response
        response = client.get("/api/forms/1")

        assert response.status_code == 404

    def test_scto_form_definition(
        self, client, login_test_user, csrf_token, create_form
    ):
        """
        Test ingest the scto form definition from SCTO and fetching them from the database
        """

        expected_response = load_reference_data("scto-questions.json")

        # Ingest the SCTO variables from SCTO into the database
        response = client.post(
            "/api/forms/1/scto-form-definition/refresh",
            headers={"X-CSRF-Token": csrf_token},
        )
        assert response.status_code == 200

        # Get the SCTO questions from the database
        response = client.get(
            "/api/forms/1/scto-form-definition/scto-questions",
        )
        assert response.status_code == 200

        checkdiff = jsondiff.diff(expected_response, response.json)
        assert checkdiff == {}

    def test_refresh_scto_form_definition(
        self, client, login_test_user, csrf_token, create_form
    ):
        """
        Test that refreshing the scto form definition from SCTO gives the same result
        """

        expected_response = load_reference_data("scto-questions-refresh.json")

        # Ingest the SCTO variables from SCTO into the database
        response = client.post(
            "/api/forms/1/scto-form-definition/refresh",
            headers={"X-CSRF-Token": csrf_token},
        )
        assert response.status_code == 200

        # Ingest the SCTO variables from SCTO into the database
        response = client.post(
            "/api/forms/1/scto-form-definition/refresh",
            headers={"X-CSRF-Token": csrf_token},
        )
        assert response.status_code == 200

        # Get the SCTO questions from the database
        response = client.get(
            "/api/forms/1/scto-form-definition/scto-questions",
        )
        assert response.status_code == 200

        checkdiff = jsondiff.diff(expected_response, response.json)
        assert checkdiff == {}

    def test_delete_parent_form_cascade_to_scto_form_definition(
        self, client, login_test_user, csrf_token, create_form
    ):
        """
        Test that deleting the parent form deletes the scto form definition
        """

        # Ingest the SCTO variables from SCTO into the database
        response = client.post(
            "/api/forms/1/scto-form-definition/refresh",
            headers={"X-CSRF-Token": csrf_token},
        )
        assert response.status_code == 200

        # Delete the parent form
        response = client.delete(
            "/api/forms/1",
            headers={"X-CSRF-Token": csrf_token},
        )
        assert response.status_code == 204

        # Get the SCTO questions from the database
        response = client.get(
            "/api/forms/1/scto-form-definition/scto-questions",
        )
        assert response.status_code == 404
