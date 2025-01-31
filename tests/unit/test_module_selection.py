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
            "target_mapping_criteria": ["Gender"],
            "surveyor_mapping_criteria": ["Gender"],
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
        self, client, login_test_user, csrf_token, test_user_credentials, create_survey
    ):
        """
        Insert new module_selection as a setup step for the module_selection tests
        Inserts hiring module (13) which has no dependencies
        """

        payload = {
            "survey_uid": 1,
            "modules": ["13"],
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
    def create_module_selection_with_dependencies(
        self, client, login_test_user, csrf_token, test_user_credentials, create_survey
    ):
        """
        Insert new module_selection as a setup step for the module_selection tests
        Inserts Media Audits (12) which has dependencies

        """

        payload = {
            "survey_uid": 1,
            "modules": ["12"],
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
        Only mandatory module and optional module 13 are inserted
        """

        # Test the survey was inserted correctly
        response = client.get("/api/module-status/1")
        assert response.status_code == 200

        expected_response = {
            "data": [
                {"survey_uid": 1, "module_id": 1, "config_status": "In Progress"},
                {"survey_uid": 1, "module_id": 2, "config_status": "Done"},
                {"survey_uid": 1, "module_id": 3, "config_status": "Not Started"},
                {"survey_uid": 1, "module_id": 4, "config_status": "Done"},
                {"survey_uid": 1, "module_id": 13, "config_status": "Not Started"},
            ],
            "success": True,
        }

        print(response.json)
        checkdiff = jsondiff.diff(expected_response, response.json)
        assert checkdiff == {}

    def test_module_selection_with_dependencies(
        self,
        client,
        login_test_user,
        create_module_selection_with_dependencies,
        test_user_credentials,
    ):
        """
        Test that the update_module_selection is update correctly
        All the dependencies of the module are also inserted
        """

        # Test the survey was inserted correctly
        response = client.get("/api/module-status/1")
        assert response.status_code == 200

        expected_response = {
            "data": [
                {"config_status": "In Progress", "module_id": 1, "survey_uid": 1},
                {"config_status": "Done", "module_id": 2, "survey_uid": 1},
                {"config_status": "Not Started", "module_id": 3, "survey_uid": 1},
                {"config_status": "Done", "module_id": 4, "survey_uid": 1},
                {"config_status": "Not Started", "module_id": 12, "survey_uid": 1},
                {"config_status": "Not Started", "module_id": 5, "survey_uid": 1},
                {"config_status": "Not Started", "module_id": 8, "survey_uid": 1},
            ],
            "success": True,
        }

        print(response.json)
        checkdiff = jsondiff.diff(expected_response, response.json)
        assert checkdiff == {}

    def test_module_selection_location_dependencies(
        self,
        client,
        csrf_token,
        test_user_credentials,
        create_module_questionnaire,
    ):
        """
        Test that the assignments module addition - which has location based dependencies
        Here location is not in the mapping criteria, so the modules should be optional
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

        # Test the survey was inserted correctly
        response = client.get("/api/module-status/1")
        assert response.status_code == 200

        expected_response = {
            "data": [
                {"config_status": "Done", "module_id": 1, "survey_uid": 1},
                {"config_status": "Done", "module_id": 2, "survey_uid": 1},
                {"config_status": "Not Started", "module_id": 3, "survey_uid": 1},
                {"config_status": "In Progress", "module_id": 4, "survey_uid": 1},
                {"config_status": "Not Started", "module_id": 9, "survey_uid": 1},
                {"config_status": "Not Started", "module_id": 14, "survey_uid": 1},
                {"config_status": "Not Started", "module_id": 17, "survey_uid": 1},
                {"config_status": "Not Started", "module_id": 7, "survey_uid": 1},
                {"config_status": "Not Started", "module_id": 5, "survey_uid": 1},
                {"config_status": "Not Started", "module_id": 16, "survey_uid": 1},
                {"config_status": "Not Started", "module_id": 8, "survey_uid": 1},
            ],
            "success": True,
        }

        print(response.json)
        checkdiff = jsondiff.diff(expected_response, response.json)
        assert checkdiff == {}

        # Test the config-status has been correct optional/mandatory flag
        response = client.get("/api/surveys/1/config-status")
        assert response.status_code == 200

        expected_response = {
            "data": {
                "Basic information": {"status": "Done", "optional": False},
                "Module selection": {"status": "Done", "optional": False},
                "Survey information": [
                    {
                        "name": "SurveyCTO information",
                        "status": "Not Started",
                        "optional": False,
                    },
                    {
                        "name": "User and role management",
                        "status": "In Progress",
                        "optional": False,
                    },
                    {
                        "name": "Survey locations",
                        "status": "Not Started",
                        "optional": True,
                    },
                    {"name": "Enumerators", "status": "Not Started", "optional": False},
                    {"name": "Targets", "status": "Not Started", "optional": False},
                    {
                        "name": "Target status mapping",
                        "status": "Not Started",
                        "optional": False,
                    },
                    {"name": "Mapping", "status": "Not Started", "optional": False},
                ],
                "Module configuration": [
                    {
                        "module_id": 9,
                        "name": "Assignments",
                        "status": "Not Started",
                        "optional": False,
                    },
                    {
                        "module_id": 16,
                        "name": "Assignments column configuration",
                        "status": "Not Started",
                        "optional": True,
                    },
                ],
                "overall_status": "In Progress - Configuration",
                "completion_percentage": 22.22
            },
            "success": True,
        }

        print(response.json)
        checkdiff = jsondiff.diff(expected_response, response.json)
        assert checkdiff == {}

    def test_module_deselection(
        self,
        client,
        csrf_token,
        test_user_credentials,
        create_module_selection,
    ):
        """
        Test that the module deselection works correctly
        13 is in selected modules, so it should be removed
        18 is added
        """

        payload = {
            "survey_uid": 1,
            "modules": ["18"],
        }

        response = client.post(
            "/api/module-status",
            json=payload,
            content_type="application/json",
            headers={"X-CSRF-Token": csrf_token},
        )
        assert response.status_code == 200

        # Test the survey was inserted correctly
        response = client.get("/api/module-status/1")
        assert response.status_code == 200

        expected_response = {
            "data": [
                {"config_status": "In Progress", "module_id": 1, "survey_uid": 1},
                {"config_status": "Done", "module_id": 2, "survey_uid": 1},
                {"config_status": "Not Started", "module_id": 3, "survey_uid": 1},
                {"config_status": "Done", "module_id": 4, "survey_uid": 1},
                {"config_status": "Not Started", "module_id": 18, "survey_uid": 1},
            ],
            "success": True,
        }

        print(response.json)
        checkdiff = jsondiff.diff(expected_response, response.json)
        assert checkdiff == {}
