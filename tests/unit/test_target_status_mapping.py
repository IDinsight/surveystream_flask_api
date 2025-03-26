import jsondiff
import pytest
import base64
import pandas as pd
from pathlib import Path
from utils import (
    create_new_survey_role_with_permissions,
    login_user,
    update_logged_in_user_roles,
)


@pytest.mark.target_status_mapping
class TestTargetStatusMapping:
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

    def test_fetch_default_target_status_mapping(
        self, client, login_test_user, create_form, csrf_token
    ):
        """
        Test fetching default target status mapping data
        """

        expected_response = {
            "success": True,
            "data": [
                {
                    "survey_status": 1,
                    "survey_status_label": "Fully complete",
                    "completed_flag": True,
                    "refusal_flag": False,
                    "target_assignable": False,
                    "webapp_tag_color": "green",
                },
                {
                    "survey_status": 2,
                    "survey_status_label": "Partially complete - revisit",
                    "completed_flag": False,
                    "refusal_flag": False,
                    "target_assignable": True,
                    "webapp_tag_color": "gold",
                },
                {
                    "survey_status": 3,
                    "survey_status_label": "Partially complete - no revisit",
                    "completed_flag": False,
                    "refusal_flag": False,
                    "target_assignable": False,
                    "webapp_tag_color": "green",
                },
                {
                    "survey_status": 4,
                    "survey_status_label": "Appointment",
                    "completed_flag": False,
                    "refusal_flag": False,
                    "target_assignable": True,
                    "webapp_tag_color": "blue",
                },
                {
                    "survey_status": 5,
                    "survey_status_label": "Refusal",
                    "completed_flag": False,
                    "refusal_flag": True,
                    "target_assignable": False,
                    "webapp_tag_color": "red",
                },
                {
                    "survey_status": 6,
                    "survey_status_label": "Not found - revisit",
                    "completed_flag": False,
                    "refusal_flag": False,
                    "target_assignable": True,
                    "webapp_tag_color": "gold",
                },
                {
                    "survey_status": 7,
                    "survey_status_label": "Not found - no revisit",
                    "completed_flag": False,
                    "refusal_flag": False,
                    "target_assignable": False,
                    "webapp_tag_color": "red",
                },
                {
                    "survey_status": 8,
                    "survey_status_label": "Not attempted",
                    "completed_flag": False,
                    "refusal_flag": False,
                    "target_assignable": True,
                    "webapp_tag_color": "gold",
                },
                {
                    "survey_status": 9,
                    "survey_status_label": "Ineligible household",
                    "completed_flag": False,
                    "refusal_flag": False,
                    "target_assignable": False,
                    "webapp_tag_color": "cyan",
                },
            ],
        }

        # Check the response
        response = client.get(
            "/api/target-status-mapping",
            query_string={"form_uid": 1},
            content_type="application/json",
        )

        assert response.status_code == 200
        checkdiff = jsondiff.diff(expected_response, response.json)
        assert checkdiff == {}

    def test_upload_target_status_mapping(
        self, client, login_test_user, create_form, csrf_token
    ):
        """
        Insert data for target status mapping for the survey

        """
        payload = {
            "form_uid": 1,
            "target_status_mapping": [
                {
                    "survey_status": 1,
                    "survey_status_label": "Fully complete",
                    "completed_flag": True,
                    "refusal_flag": False,
                    "target_assignable": False,
                    "webapp_tag_color": "green",
                },
                {
                    "survey_status": 2,
                    "survey_status_label": "Not complete",
                    "completed_flag": False,
                    "refusal_flag": False,
                    "target_assignable": True,
                    "webapp_tag_color": "gold",
                },
            ],
        }

        response = client.put(
            "/api/target-status-mapping",
            json=payload,
            content_type="application/json",
            headers={"X-CSRF-Token": csrf_token},
        )
        print(response.json)
        assert response.status_code == 200

    def test_upload_target_status_mapping_for_super_admin_user(
        self, client, login_test_user, create_form, csrf_token
    ):
        """
        Test uploading the target status mapping for super_admin users
        """

        payload = {
            "form_uid": 1,
            "target_status_mapping": [
                {
                    "survey_status": 1,
                    "survey_status_label": "Fully complete",
                    "completed_flag": True,
                    "refusal_flag": False,
                    "target_assignable": False,
                    "webapp_tag_color": "green",
                },
                {
                    "survey_status": 2,
                    "survey_status_label": "Not complete",
                    "completed_flag": False,
                    "refusal_flag": False,
                    "target_assignable": True,
                    "webapp_tag_color": "gold",
                },
                {
                    "survey_status": 3,
                    "survey_status_label": "Refusal",
                    "completed_flag": False,
                    "refusal_flag": True,
                    "target_assignable": False,
                    "webapp_tag_color": "red",
                },
            ],
        }

        response = client.put(
            "/api/target-status-mapping",
            json=payload,
            content_type="application/json",
            headers={"X-CSRF-Token": csrf_token},
        )
        assert response.status_code == 200

        expected_response = {
            "success": True,
            "data": [
                {
                    "survey_status": 1,
                    "survey_status_label": "Fully complete",
                    "completed_flag": True,
                    "refusal_flag": False,
                    "target_assignable": False,
                    "webapp_tag_color": "green",
                },
                {
                    "survey_status": 2,
                    "survey_status_label": "Not complete",
                    "completed_flag": False,
                    "refusal_flag": False,
                    "target_assignable": True,
                    "webapp_tag_color": "gold",
                },
                {
                    "survey_status": 3,
                    "survey_status_label": "Refusal",
                    "completed_flag": False,
                    "refusal_flag": True,
                    "target_assignable": False,
                    "webapp_tag_color": "red",
                },
            ],
        }

        # Check the response
        response = client.get(
            "/api/target-status-mapping",
            query_string={"form_uid": 1},
            content_type="application/json",
        )

        assert response.status_code == 200
        checkdiff = jsondiff.diff(expected_response, response.json)
        assert checkdiff == {}

    def test_upload_target_status_mapping_for_survey_admin_user(
        self,
        client,
        login_test_user,
        create_form,
        csrf_token,
        test_user_credentials,
    ):
        """
        Test uploading the target status mapping for survey_admin users
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
            "form_uid": 1,
            "target_status_mapping": [
                {
                    "survey_status": 1,
                    "survey_status_label": "Fully complete",
                    "completed_flag": True,
                    "refusal_flag": False,
                    "target_assignable": False,
                    "webapp_tag_color": "green",
                },
                {
                    "survey_status": 2,
                    "survey_status_label": "Not complete",
                    "completed_flag": False,
                    "refusal_flag": False,
                    "target_assignable": True,
                    "webapp_tag_color": "gold",
                },
                {
                    "survey_status": 3,
                    "survey_status_label": "Refusal",
                    "completed_flag": False,
                    "refusal_flag": True,
                    "target_assignable": False,
                    "webapp_tag_color": "red",
                },
            ],
        }

        response = client.put(
            "/api/target-status-mapping",
            json=payload,
            content_type="application/json",
            headers={"X-CSRF-Token": csrf_token},
        )
        assert response.status_code == 200

        expected_response = {
            "success": True,
            "data": [
                {
                    "survey_status": 1,
                    "survey_status_label": "Fully complete",
                    "completed_flag": True,
                    "refusal_flag": False,
                    "target_assignable": False,
                    "webapp_tag_color": "green",
                },
                {
                    "survey_status": 2,
                    "survey_status_label": "Not complete",
                    "completed_flag": False,
                    "refusal_flag": False,
                    "target_assignable": True,
                    "webapp_tag_color": "gold",
                },
                {
                    "survey_status": 3,
                    "survey_status_label": "Refusal",
                    "completed_flag": False,
                    "refusal_flag": True,
                    "target_assignable": False,
                    "webapp_tag_color": "red",
                },
            ],
        }

        # Check the response
        response = client.get(
            "/api/target-status-mapping",
            query_string={"form_uid": 1},
            content_type="application/json",
        )

        assert response.status_code == 200
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

    def test_upload_target_status_mapping_for_non_admin_user_roles(
        self,
        client,
        login_test_user,
        create_form,
        csrf_token,
        test_user_credentials,
    ):
        """
        Test uploading the target status mapping for non_admin users with roles
        """
        new_role = create_new_survey_role_with_permissions(
            # 21 - WRITE Target Status Mapping
            client,
            test_user_credentials,
            "Survey Role",
            [21],
            1,
        )
        updated_user = update_logged_in_user_roles(
            client,
            test_user_credentials,
            is_survey_admin=False,
            survey_uid=1,
            is_super_admin=False,
            roles=[1],
        )

        login_user(client, test_user_credentials)

        payload = {
            "form_uid": 1,
            "target_status_mapping": [
                {
                    "survey_status": 1,
                    "survey_status_label": "Fully complete",
                    "completed_flag": True,
                    "refusal_flag": False,
                    "target_assignable": False,
                    "webapp_tag_color": "green",
                },
                {
                    "survey_status": 2,
                    "survey_status_label": "Not complete",
                    "completed_flag": False,
                    "refusal_flag": False,
                    "target_assignable": True,
                    "webapp_tag_color": "gold",
                },
                {
                    "survey_status": 3,
                    "survey_status_label": "Refusal",
                    "completed_flag": False,
                    "refusal_flag": True,
                    "target_assignable": False,
                    "webapp_tag_color": "red",
                },
            ],
        }

        response = client.put(
            "/api/target-status-mapping",
            json=payload,
            content_type="application/json",
            headers={"X-CSRF-Token": csrf_token},
        )
        assert response.status_code == 200

        expected_response = {
            "success": True,
            "data": [
                {
                    "survey_status": 1,
                    "survey_status_label": "Fully complete",
                    "completed_flag": True,
                    "refusal_flag": False,
                    "target_assignable": False,
                    "webapp_tag_color": "green",
                },
                {
                    "survey_status": 2,
                    "survey_status_label": "Not complete",
                    "completed_flag": False,
                    "refusal_flag": False,
                    "target_assignable": True,
                    "webapp_tag_color": "gold",
                },
                {
                    "survey_status": 3,
                    "survey_status_label": "Refusal",
                    "completed_flag": False,
                    "refusal_flag": True,
                    "target_assignable": False,
                    "webapp_tag_color": "red",
                },
            ],
        }

        # Check the response
        response = client.get(
            "/api/target-status-mapping",
            query_string={"form_uid": 1},
            content_type="application/json",
        )

        assert response.status_code == 200
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

    def test_upload_target_status_mapping_for_non_admin_user_no_roles(
        self,
        client,
        login_test_user,
        create_form,
        csrf_token,
        test_user_credentials,
    ):
        """
        Test uploading the target status mapping for non_admin users without roles
        Expect Fail 403
        """
        updated_user = update_logged_in_user_roles(
            client,
            test_user_credentials,
            is_survey_admin=False,
            survey_uid=1,
            is_super_admin=False,
            roles=[],
        )

        login_user(client, test_user_credentials)

        payload = {
            "form_uid": 1,
            "target_status_mapping": [
                {
                    "survey_status": 1,
                    "survey_status_label": "Fully complete",
                    "completed_flag": True,
                    "refusal_flag": False,
                    "target_assignable": False,
                    "webapp_tag_color": "green",
                },
                {
                    "survey_status": 2,
                    "survey_status_label": "Not complete",
                    "completed_flag": False,
                    "refusal_flag": False,
                    "target_assignable": True,
                    "webapp_tag_color": "gold",
                },
                {
                    "survey_status": 3,
                    "survey_status_label": "Refusal",
                    "completed_flag": False,
                    "refusal_flag": True,
                    "target_assignable": False,
                    "webapp_tag_color": "red",
                },
            ],
        }

        response = client.put(
            "/api/target-status-mapping",
            json=payload,
            content_type="application/json",
            headers={"X-CSRF-Token": csrf_token},
        )
        assert response.status_code == 403

        expected_response = {
            "success": False,
            "error": f"User does not have the required permission: WRITE Target Status Mapping",
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
