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
    def create_module_selection_hiring(
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
    def create_module_selection_media_audits(
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

    def test_module_selection_hiring(
        self,
        client,
        login_test_user,
        create_module_selection_hiring,
        test_user_credentials,
    ):
        """
        Test that the create_module_selection is inserted correctly
        Only mandatory modules and optional module 13 - hiring are inserted
        """

        # Test the survey was inserted correctly
        response = client.get("/api/module-status/1")
        assert response.status_code == 200

        expected_response = {
            "data": [
                {"survey_uid": 1, "module_id": 1, "config_status": "In Progress - Incomplete"},
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

        # Test the config-status has correct optional/mandatory flag
        response = client.get("/api/surveys/1/config-status")
        assert response.status_code == 200

        expected_response = {
            "data": {
                "Background Details": {"status": "In Progress - Incomplete", "optional": False},
                "Feature Selection": {"status": "Done", "optional": False},
                "Survey Information": [
                    {
                        "name": "SurveyCTO Integration",
                        "status": "Not Started",
                        "optional": False,
                    },
                    {
                        "name": "User and Role Management",
                        "status": "Done",
                        "optional": False,
                    },
                ],
                "Module Configuration": [
                    {
                        "module_id": 13,
                        "name": "Surveyor Hiring",
                        "status": "Not Started",
                        "optional": False,
                    },
                ],
                "overall_status": "In Progress - Configuration",
                "completion_stats": {
                    "num_modules": 4,
                    "num_completed": 2,
                    "num_in_progress": 0,
                    "num_in_progress_incomplete": 1,
                    "num_not_started": 1,
                    "num_error": 0,
                    "num_optional": 0,
                },
            },
            "success": True,
        }

        print(response.json)
        checkdiff = jsondiff.diff(expected_response, response.json)
        assert checkdiff == {}

    def test_module_selection_media_audits(
        self,
        client,
        login_test_user,
        create_module_selection_media_audits,
        test_user_credentials,
    ):
        """
        Test that the update_module_selection is update correctly
        All the dependencies of the module media audits are also inserted.
        Dependencies are optional
        """

        # Test the survey was inserted correctly
        response = client.get("/api/module-status/1")
        assert response.status_code == 200

        expected_response = {
            "data": [
                {"config_status": "In Progress - Incomplete", "module_id": 1, "survey_uid": 1},
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

        # Test the config-status has correct optional/mandatory flag
        response = client.get("/api/surveys/1/config-status")
        assert response.status_code == 200

        expected_response = {
            "data": {
                "Background Details": {"status": "In Progress - Incomplete", "optional": False},
                "Feature Selection": {"status": "Done", "optional": False},
                "Survey Information": [
                    {
                        "name": "SurveyCTO Integration",
                        "status": "Not Started",
                        "optional": False,
                    },
                    {
                        "name": "User and Role Management",
                        "status": "Done",
                        "optional": False,
                    },
                    {
                        "name": "Locations",
                        "status": "Not Started",
                        "optional": True,
                    },
                    {"name": "Targets", "status": "Not Started", "optional": True},
                ],
                "Module Configuration": [
                    {
                        "module_id": 12,
                        "name": "Media Audits",
                        "status": "Not Started",
                        "optional": False,
                    },
                ],
                "overall_status": "In Progress - Configuration",
                "completion_stats": {
                    "num_modules": 5,
                    "num_completed": 2,
                    "num_in_progress": 0,
                    "num_in_progress_incomplete": 1,
                    "num_not_started": 2,
                    "num_error": 0,
                    "num_optional": 2,
                }
            },
            "success": True,
        }

        print(response.json)
        checkdiff = jsondiff.diff(expected_response, response.json)
        assert checkdiff == {}

    def test_module_selection_assignments(
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
                {"config_status": "In Progress - Incomplete", "module_id": 4, "survey_uid": 1},
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
                "Background Details": {"status": "Done", "optional": False},
                "Feature Selection": {"status": "Done", "optional": False},
                "Survey Information": [
                    {
                        "name": "SurveyCTO Integration",
                        "status": "Not Started",
                        "optional": False,
                    },
                    {
                        "name": "User and Role Management",
                        "status": "In Progress - Incomplete",
                        "optional": False,
                    },
                    {
                        "name": "Locations",
                        "status": "Not Started",
                        "optional": True,
                    },
                    {"name": "Enumerators", "status": "Not Started", "optional": False},
                    {"name": "Targets", "status": "Not Started", "optional": False},
                    {
                        "name": "Survey Status for Targets",
                        "status": "Not Started",
                        "optional": True,
                    },
                    {"name": "Supervisor Mapping", "status": "Not Started", "optional": False},
                ],
                "Module Configuration": [
                    {
                        "module_id": 9,
                        "name": "Assignments",
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
                "overall_status": "In Progress - Configuration",
                "completion_stats": {
                    "num_modules": 8,
                    "num_completed": 2,
                    "num_in_progress": 0,
                    "num_in_progress_incomplete": 1,
                    "num_not_started": 5,
                    "num_error": 0,
                    "num_optional": 3,
                }
            },
            "success": True,
        }

        print(response.json)
        checkdiff = jsondiff.diff(expected_response, response.json)
        assert checkdiff == {}

    def test_module_selection_assignments_non_optional(
        self,
        client,
        csrf_token,
        test_user_credentials,
        create_module_questionnaire,
    ):
        """
        Test that the assignments module addition - which has location based dependencies
        Here location is added in the mapping criteria, so the modules should be mandatory
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

        # update the module questionnaire to include location in the mapping criteria
        payload = {
            "assignment_process": "Manual",
            "language_location_mapping": False,
            "reassignment_required": False,
            "target_mapping_criteria": ["Location"],
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

        # Test the config-status has been correct optional/mandatory flag
        response = client.get("/api/surveys/1/config-status")
        assert response.status_code == 200

        expected_response = {
            "data": {
                "Background Details": {"status": "Done", "optional": False},
                "Feature Selection": {"status": "Done", "optional": False},
                "Survey Information": [
                    {
                        "name": "SurveyCTO Integration",
                        "status": "Not Started",
                        "optional": False,
                    },
                    {
                        "name": "User and Role Management",
                        "status": "In Progress - Incomplete",
                        "optional": False,
                    },
                    {
                        "name": "Locations",
                        "status": "Not Started",
                        "optional": False,
                    },
                    {"name": "Enumerators", "status": "Not Started", "optional": False},
                    {"name": "Targets", "status": "Not Started", "optional": False},
                    {
                        "name": "Survey Status for Targets",
                        "status": "Not Started",
                        "optional": True,
                    },
                    {"name": "Supervisor Mapping", "status": "Not Started", "optional": False},
                ],
                "Module Configuration": [
                    {
                        "module_id": 9,
                        "name": "Assignments",
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
                "overall_status": "In Progress - Configuration",
                "completion_stats": {
                    "num_modules": 9,
                    "num_completed": 2,
                    "num_in_progress": 0,
                    "num_in_progress_incomplete": 1,
                    "num_not_started": 6,
                    "num_error": 0,
                    "num_optional": 2,
                }
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
        create_module_selection_hiring,
    ):
        """
        Test that the module deselection works correctly
        13 is in selected modules, so it should be removed
        Admin forms - 18 is added
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
                {"config_status": "In Progress - Incomplete", "module_id": 1, "survey_uid": 1},
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

    def test_module_selection_emails(
        self,
        client,
        csrf_token,
        test_user_credentials,
        create_module_questionnaire,
    ):
        """
        Test that the emails module addition
        """

        payload = {
            "survey_uid": 1,
            "modules": ["15"],
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
                {"config_status": "In Progress - Incomplete", "module_id": 4, "survey_uid": 1},
                {"config_status": "Not Started", "module_id": 15, "survey_uid": 1},
                {"config_status": "Not Started", "module_id": 17, "survey_uid": 1},
                {"config_status": "Not Started", "module_id": 7, "survey_uid": 1},
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
                "Background Details": {"status": "Done", "optional": False},
                "Feature Selection": {"status": "Done", "optional": False},
                "Survey Information": [
                    {
                        "name": "SurveyCTO Integration",
                        "status": "Not Started",
                        "optional": False,
                    },
                    {
                        "name": "User and Role Management",
                        "status": "In Progress - Incomplete",
                        "optional": False,
                    },
                    {"name": "Enumerators", "status": "Not Started", "optional": False},
                    {"name": "Supervisor Mapping", "status": "Not Started", "optional": False},
                ],
                "Module Configuration": [
                    {
                        "module_id": 15,
                        "name": "Emails",
                        "status": "Not Started",
                        "optional": False,
                    },
                ],
                "overall_status": "In Progress - Configuration",
                "completion_stats": {
                    "num_modules": 7,
                    "num_completed": 2,
                    "num_in_progress": 0,
                    "num_in_progress_incomplete": 1,
                    "num_not_started": 4,
                    "num_error": 0,
                    "num_optional": 0,
                }
            },
            "success": True,
        }

        print(response.json)
        checkdiff = jsondiff.diff(expected_response, response.json)
        assert checkdiff == {}

    def test_module_selection_data_quality(
        self,
        client,
        csrf_token,
        test_user_credentials,
        create_module_questionnaire,
    ):
        """
        Test that the emails module addition
        """

        payload = {
            "survey_uid": 1,
            "modules": ["11"],
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
                {"config_status": "Done", "module_id": 4, "survey_uid": 1},
                {"config_status": "Not Started", "module_id": 11, "survey_uid": 1},
                {"config_status": "Not Started", "module_id": 14, "survey_uid": 1},
                {"config_status": "Not Started", "module_id": 7, "survey_uid": 1},
                {"config_status": "Not Started", "module_id": 5, "survey_uid": 1},
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
                "Background Details": {"status": "Done", "optional": False},
                "Feature Selection": {"status": "Done", "optional": False},
                "Survey Information": [
                    {
                        "name": "SurveyCTO Integration",
                        "status": "Not Started",
                        "optional": False,
                    },
                    {
                        "name": "User and Role Management",
                        "status": "Done",
                        "optional": False,
                    },
                    {
                        "name": "Locations",
                        "status": "Not Started",
                        "optional": True,
                    },
                    {"name": "Enumerators", "status": "Not Started", "optional": True},
                    {"name": "Targets", "status": "Not Started", "optional": True},
                    {
                        "name": "Survey Status for Targets",
                        "status": "Not Started",
                        "optional": True,
                    },
                ],
                "Module Configuration": [
                    {
                        "module_id": 11,
                        "name": "Data Quality",
                        "status": "Not Started",
                        "optional": False,
                    },
                ],
                "overall_status": "In Progress - Configuration",
                "completion_stats": {
                    "num_modules": 5,
                    "num_completed": 3,
                    "num_in_progress": 0,
                    "num_in_progress_incomplete": 0,
                    "num_not_started": 2,
                    "num_error": 0,
                    "num_optional": 4,
                }
            },
            "success": True,
        }

        print(response.json)
        checkdiff = jsondiff.diff(expected_response, response.json)
        assert checkdiff == {}
