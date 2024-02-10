import jsondiff
import pytest
from utils import (
    login_user,
    update_logged_in_user_roles,
)


@pytest.mark.module_questionnaire
class TestModuleQuestionnaire:
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
    def create_module_questionnaire(
        self, client, login_test_user, csrf_token, test_user_credentials, create_survey
    ):
        """
        Insert new module_questionnaire as a setup step for the module_questionnaire tests
        """

        payload = {
            "assignment_process": "Manual",
            "language_location_mapping": False,
            "reassignment_required": False,
            "supervisor_assignment_criteria": ["Gender"],
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

    def test_create_module_questionnaire_for_super_admin_user(
        self,
        client,
        login_test_user,
        create_module_questionnaire,
        test_user_credentials,
    ):
        """
        Test that the module_questionnaire is inserted correctly by a super admin_user
        """

        # Test the survey was inserted correctly
        response = client.get("/api/module-questionnaire/1")
        assert response.status_code == 200

        expected_response = {
            "data": {
                "assignment_process": "Manual",
                "language_location_mapping": False,
                "reassignment_required": False,
                "supervisor_assignment_criteria": ["Gender"],
                "supervisor_hierarchy_exists": False,
                "supervisor_surveyor_relation": "1:many",
                "survey_uid": 1,
                "target_assignment_criteria": ["Location of surveyors"],
            },
            "success": True,
        }

        checkdiff = jsondiff.diff(expected_response, response.json)
        assert checkdiff == {}

    def test_create_module_questionnaire_for_survey_admin_user(
        self, client, login_test_user, create_survey, test_user_credentials, csrf_token
    ):
        """
        Test that the module_questionnaire is inserted correctly by a survey admin_user
        """
        updated_user = update_logged_in_user_roles(
            client,
            test_user_credentials,
            is_survey_admin=True,
            survey_uid=1,
            is_super_admin=False,
        )

        login_user(client, test_user_credentials)

        payload = {
            "assignment_process": "Manual",
            "language_location_mapping": False,
            "reassignment_required": False,
            "supervisor_assignment_criteria": ["Gender"],
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

        # Test the survey was inserted correctly
        response = client.get("/api/module-questionnaire/1")
        assert response.status_code == 200

        expected_response = {
            "data": {
                "assignment_process": "Manual",
                "language_location_mapping": False,
                "reassignment_required": False,
                "supervisor_assignment_criteria": ["Gender"],
                "supervisor_hierarchy_exists": False,
                "supervisor_surveyor_relation": "1:many",
                "survey_uid": 1,
                "target_assignment_criteria": ["Location of surveyors"],
            },
            "success": True,
        }

        checkdiff = jsondiff.diff(expected_response, response.json)
        assert checkdiff == {}

        revert_user = update_logged_in_user_roles(
            client,
            test_user_credentials,
            is_survey_admin=False,
            survey_uid=1,
            is_super_admin=True,
        )

        login_user(client, test_user_credentials)

    def test_create_module_questionnaire_for_non_admin_user(
        self, client, login_test_user, create_survey, test_user_credentials, csrf_token
    ):
        """
        Test that the module_questionnaire cannot be inserted by a non_admin user
        Expect 403 Fail

        """
        updated_user = update_logged_in_user_roles(
            client,
            test_user_credentials,
            is_survey_admin=False,
            survey_uid=1,
            is_super_admin=False,
        )

        login_user(client, test_user_credentials)

        payload = {
            "assignment_process": "Manual",
            "language_location_mapping": False,
            "reassignment_required": False,
            "supervisor_assignment_criteria": ["Gender"],
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
        assert response.status_code == 403

        expected_response = {
            "success": False,
            "error": f"User does not have the required permission: ADMIN",
        }
        checkdiff = jsondiff.diff(expected_response, response.json)
        assert checkdiff == {}

        revert_user = update_logged_in_user_roles(
            client,
            test_user_credentials,
            is_survey_admin=False,
            survey_uid=1,
            is_super_admin=True,
        )

        login_user(client, test_user_credentials)
