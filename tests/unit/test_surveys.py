import jsondiff
import pytest
import re


@pytest.mark.surveys
class TestSurveys:
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

    def test_create_survey(
        self, client, login_test_user, create_survey, test_user_credentials
    ):
        """
        Test that the survey is inserted correctly
        """

        # Test the survey was inserted correctly
        response = client.get(
            "/api/surveys", query_string={"user_uid": test_user_credentials["user_uid"]}
        )
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
                    "config_status": "In Progress - Configuration",
                    "last_updated_at": "2023-05-30 00:00:00",
                }
            ],
            "success": True,
        }

        # Assert that the last_updated_at field is a valid datetime
        assert re.match(
            r"\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}",
            response.json["data"][0]["last_updated_at"],
        )

        # Replace the last_updated_at field in the expected response with the value from the actual response
        expected_response["data"][0]["last_updated_at"] = response.json["data"][0][
            "last_updated_at"
        ]

        checkdiff = jsondiff.diff(expected_response, response.json)
        assert checkdiff == {}

    def test_update_survey(self, client, login_test_user, create_survey, csrf_token):
        """
        Test that an existing survey can be updated
        """

        # Try to update the existing roles
        payload = {
            "survey_uid": 1,
            "survey_id": "test_survey_1",
            "survey_name": "Test Survey 1",
            "survey_description": "A test survey 1",
            "project_name": "Test Project 1",
            "surveying_method": "phone",
            "irb_approval": "No",
            "planned_start_date": "2021-01-02",
            "planned_end_date": "2021-12-30",
            "state": "Active",
            "config_status": "In Progress - Backend Setup",
        }

        response = client.put(
            "/api/surveys/1/basic-information",
            json=payload,
            content_type="application/json",
            headers={"X-CSRF-Token": csrf_token},
        )
        assert response.status_code == 200

        response = client.get("/api/surveys/1/basic-information")
        assert response.status_code == 200

        expected_response = {
            "survey_uid": 1,
            "survey_id": "test_survey_1",
            "survey_name": "Test Survey 1",
            "survey_description": "A test survey 1",
            "project_name": "Test Project 1",
            "surveying_method": "phone",
            "irb_approval": "No",
            "planned_start_date": "2021-01-02",
            "planned_end_date": "2021-12-30",
            "state": "Active",
            "config_status": "In Progress - Backend Setup",
            "last_updated_at": "2023-05-30 00:00:00",
        }

        # Assert that the last_updated_at field is a valid datetime
        assert re.match(
            r"\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}",
            response.json["last_updated_at"],
        )

        # Replace the last_updated_at field in the expected response with the value from the actual response
        expected_response["last_updated_at"] = response.json["last_updated_at"]

        checkdiff = jsondiff.diff(expected_response, response.json)
        assert checkdiff == {}

    def test_delete_survey(
        self, client, login_test_user, create_survey, csrf_token, test_user_credentials
    ):
        """
        Test that a survey can be deleted
        """

        response = client.delete(
            "/api/surveys/1",
            headers={"X-CSRF-Token": csrf_token},
        )
        assert response.status_code == 204

        # Check the response
        response = client.get(
            "/api/surveys/",
            query_string={"user_uid": test_user_credentials["user_uid"]},
        )

        assert response.status_code == 404

    def test_get_config_status(
        self, client, login_test_user, create_survey, csrf_token, test_user_credentials
    ):
        """
        Test that module config status for the survey can be retreived
        """

        response = client.get(
            "/api/surveys/1/config-status",
            headers={"X-CSRF-Token": csrf_token},
            query_string={"user_uid": test_user_credentials["user_uid"]},
        )
        assert response.status_code == 200

        expected_response = {
            "data": {
                "Basic information": {"status": "In Progress"},
                "Module selection": {"status": "Not Started"},
                "Survey information": [
                    {"name": "SurveyCTO information","status": "Not Started"},
                    {"name": "Field supervisor roles","status": "Not Started"},
                    {"name": "Survey locations","status": "Not Started"},
                    {"name": "SurveyStream users","status": "Not Started"},
                    {"name": "Enumerators","status": "Not Started"},
                    {"name": "Targets","status": "Not Started"}
                ],
                "overall_status": "In Progress - Configuration"
            },
            "success": True,
        }
        checkdiff = jsondiff.diff(expected_response, response.json)
        assert checkdiff == {}