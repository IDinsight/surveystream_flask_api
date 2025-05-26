import jsondiff
import pytest
from utils import (
    create_new_survey_role_with_permissions,
    delete_scto_question,
    load_reference_data,
    load_scto_questions,
    login_user,
    update_logged_in_user_roles,
)

from app import db


@pytest.mark.dq
class TestDQ:
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
        login_user(client, test_user_credentials)

    @pytest.fixture
    def user_with_dq_permissions(self, client, test_user_credentials):
        # Assign new roles and permissions
        new_role = create_new_survey_role_with_permissions(
            # 17 - WRITE Data Quality
            client,
            test_user_credentials,
            "Data Quality Role",
            [17],
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
            survey_uid=1,
            is_super_admin=False,
            roles=[],
        )

        login_user(client, test_user_credentials)

    @pytest.fixture(
        params=[
            ("user_with_super_admin_permissions", True),
            ("user_with_survey_admin_permissions", True),
            ("user_with_dq_permissions", True),
            ("user_with_no_permissions", False),
        ],
        ids=[
            "super_admin_permissions",
            "survey_admin_permissions",
            "dq_permissions",
            "no_permissions",
        ],
    )
    def user_permissions(self, request):
        return request.param

    @pytest.fixture()
    def create_survey(self, client, login_test_user, csrf_token, test_user_credentials):
        """
        Insert new survey as a setup step for the tests
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
        Insert new module_questionnaire as a setup step for the tests
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
    def create_parent_form(
        self, client, login_test_user, csrf_token, create_module_questionnaire
    ):
        """
        Insert new form as a setup step for the tests
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
    def load_scto_form_definition(
        self, client, login_test_user, csrf_token, create_parent_form, app
    ):
        """
        Load the scto form definition from a static file for the tests

        Not using /api/forms/1/scto-form-definition/refresh endpoint as it takes time
        and we don't need the entire form definition for these tests
        """

        data = load_reference_data("scto-questions.json")
        repeat_group_questions = load_reference_data("scto-questions-repeatgroups.json")

        load_scto_questions(
            app,
            db,
            data["data"]["questions"] + repeat_group_questions["data"]["questions"],
        )

        yield

    @pytest.fixture()
    def create_dq_form(
        self,
        client,
        login_test_user,
        csrf_token,
        create_parent_form,
    ):
        """
        Insert new dq form as a setup step for the tests
        """

        payload = {
            "survey_uid": 1,
            "scto_form_id": "test_scto_dq",
            "form_name": "Agrifieldnet AA Form",
            "tz_name": "Asia/Kolkata",
            "scto_server_name": "dod",
            "encryption_key_shared": True,
            "server_access_role_granted": True,
            "server_access_allowed": True,
            "form_type": "dq",
            "parent_form_uid": 1,
            "dq_form_type": "audioaudit",
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
    def load_dq_scto_form_definition(
        self, client, login_test_user, csrf_token, create_dq_form, app
    ):
        """
        Load the scto form definition from a static file for the tests
        """
        data = load_reference_data("scto-questions-dq.json")
        load_scto_questions(app, db, data["data"]["questions"])

        yield

    @pytest.fixture()
    def create_dq_config(
        self,
        client,
        login_test_user,
        csrf_token,
        create_dq_form,
    ):
        """
        Insert new dq config as a setup step for the tests
        """

        payload = {"form_uid": 1, "survey_status_filter": [1, 3]}

        response = client.put(
            "/api/dq/config",
            json=payload,
            content_type="application/json",
            headers={"X-CSRF-Token": csrf_token},
        )

        assert response.status_code == 200

        yield

    @pytest.fixture()
    def create_dq_check(
        self,
        client,
        login_test_user,
        csrf_token,
        create_dq_config,
        load_scto_form_definition,
    ):
        """
        Insert new dq check (missing value check) as a setup step for the tests
        """

        payload = {
            "form_uid": 1,
            "type_id": 4,
            "all_questions": True,
            "module_name": "test_module",
            "flag_description": "test_flag",
            "filters": [],
            "active": True,
            "check_components": {"value": ["Is empty", "is NA"]},
        }

        response = client.post(
            "/api/dq/checks",
            json=payload,
            content_type="application/json",
            headers={"X-CSRF-Token": csrf_token},
        )
        print(response.json)
        assert response.status_code == 200

        yield

    @pytest.fixture()
    def create_dq_check_inactive(
        self,
        client,
        login_test_user,
        csrf_token,
        create_dq_config,
        load_scto_form_definition,
    ):
        """
        Insert new dq check (missing value check) as a setup step for the tests
        """

        payload = {
            "form_uid": 1,
            "type_id": 4,
            "all_questions": True,
            "module_name": "test_module",
            "flag_description": "test_flag",
            "filters": [],
            "active": False,
            "check_components": {"value": ["Is empty", "is NA"]},
        }

        response = client.post(
            "/api/dq/checks",
            json=payload,
            content_type="application/json",
            headers={"X-CSRF-Token": csrf_token},
        )
        print(response.json)
        assert response.status_code == 200

        yield

    @pytest.fixture()
    def create_another_dq_check(
        self,
        client,
        login_test_user,
        csrf_token,
        create_dq_config,
        load_scto_form_definition,
    ):
        """
        Insert new dq check (don't know check) as a setup step for the tests
        """

        payload = {
            "form_uid": 1,
            "type_id": 5,
            "all_questions": False,
            "module_name": "test_module_1",
            "question_name": "fac_anc_reg_1_trim",
            "flag_description": "test_dont_know_flag",
            "filters": [],
            "active": True,
            "check_components": {"value": ["-888"]},
        }

        response = client.post(
            "/api/dq/checks",
            json=payload,
            content_type="application/json",
            headers={"X-CSRF-Token": csrf_token},
        )
        print(response.json)
        assert response.status_code == 200

        yield

    ####################################################
    ## FIXTURES END HERE
    ####################################################

    def test_get_dq_check_types(
        self,
        client,
        login_test_user,
        csrf_token,
    ):
        """
        Test the endpoint to get the DQ check types
        """

        response = client.get(
            "/api/dq/check-types",
            headers={"X-CSRF-Token": csrf_token},
        )

        assert response.status_code == 200

        expected_response = {
            "data": [
                {"abbr": ["L"], "name": "Logic", "type_id": 1},
                {"abbr": ["HC", "SC"], "name": "Constraint", "type_id": 2},
                {"abbr": ["OU", "OL"], "name": "Outlier", "type_id": 3},
                {"abbr": ["M"], "name": "Missing", "type_id": 4},
                {"abbr": ["DK"], "name": "Don't know", "type_id": 5},
                {"abbr": ["R"], "name": "Refusal", "type_id": 6},
                {"abbr": ["B"], "name": "Mismatch", "type_id": 7},
                {"abbr": ["P"], "name": "Protocol violation", "type_id": 8},
                {"abbr": ["SS"], "name": "Spotcheck score", "type_id": 9},
                {"abbr": ["P2P", "P2S"], "name": "GPS", "type_id": 10},
            ],
            "success": True,
        }

        print(response.json)
        checkdiff = jsondiff.diff(expected_response, response.json)
        assert checkdiff == {}

    def test_get_dq_config_no_config(
        self,
        client,
        login_test_user,
        csrf_token,
        create_dq_form,
        user_permissions,
        request,
    ):
        """
        Test the endpoint to get the DQ config when no config is present
        """
        user_fixture, expected_permission = user_permissions
        request.getfixturevalue(user_fixture)

        response = client.get(
            "/api/dq/config",
            query_string={"form_uid": 1},
            headers={"X-CSRF-Token": csrf_token},
        )

        if expected_permission:
            assert response.status_code == 404

            expected_response = {
                "success": False,
                "data": None,
                "message": "DQ configs not found",
            }
            print(response.json)

            checkdiff = jsondiff.diff(expected_response, response.json)
            assert checkdiff == {}
        else:
            assert response.status_code == 403

            expected_response = {
                "error": "User does not have the required permission: READ Data Quality",
                "success": False,
            }

            checkdiff = jsondiff.diff(expected_response, response.json)
            assert checkdiff == {}

    def test_get_dq_config(
        self,
        client,
        login_test_user,
        csrf_token,
        create_dq_config,
        user_permissions,
        request,
    ):
        """
        Test the endpoint to get the DQ config
        """
        user_fixture, expected_permission = user_permissions
        request.getfixturevalue(user_fixture)

        response = client.get(
            "/api/dq/config",
            query_string={"form_uid": 1},
            headers={"X-CSRF-Token": csrf_token},
        )
        print(response.json)

        if expected_permission:
            assert response.status_code == 200

            expected_response = {
                "data": {
                    "form_uid": 1,
                    "survey_status_filter": [1, 3],
                    "group_by_module_name": False,
                    "drop_duplicates": False,
                    "dq_checks": None,
                },
                "success": True,
            }

            checkdiff = jsondiff.diff(expected_response, response.json)
            assert checkdiff == {}
        else:
            assert response.status_code == 403

            expected_response = {
                "error": "User does not have the required permission: READ Data Quality",
                "success": False,
            }

            checkdiff = jsondiff.diff(expected_response, response.json)
            assert checkdiff == {}

    def test_get_dq_config_with_checks(
        self,
        client,
        login_test_user,
        csrf_token,
        create_dq_check,
        user_permissions,
        request,
    ):
        """
        Test the endpoint to get the DQ config
        """
        user_fixture, expected_permission = user_permissions
        request.getfixturevalue(user_fixture)

        response = client.get(
            "/api/dq/config",
            query_string={"form_uid": 1},
            headers={"X-CSRF-Token": csrf_token},
        )
        print(response.json)

        if expected_permission:
            assert response.status_code == 200

            expected_response = {
                "data": {
                    "form_uid": 1,
                    "survey_status_filter": [1, 3],
                    "group_by_module_name": False,
                    "drop_duplicates": False,
                    "dq_checks": [
                        {"type_id": 4, "num_configured": "All", "num_active": "All"}
                    ],
                },
                "success": True,
            }

            checkdiff = jsondiff.diff(expected_response, response.json)
            assert checkdiff == {}
        else:
            assert response.status_code == 403

            expected_response = {
                "error": "User does not have the required permission: READ Data Quality",
                "success": False,
            }

            checkdiff = jsondiff.diff(expected_response, response.json)
            assert checkdiff == {}

    def test_update_dq_config(
        self,
        client,
        login_test_user,
        csrf_token,
        create_dq_config,
        user_permissions,
        request,
    ):
        """
        Test the endpoint to update the DQ config
        """
        user_fixture, expected_permission = user_permissions
        request.getfixturevalue(user_fixture)

        payload = {
            "form_uid": 1,
            "survey_status_filter": [1],
            "group_by_module_name": True,
            "drop_duplicates": True,
        }

        response = client.put(
            "/api/dq/config",
            json=payload,
            content_type="application/json",
            headers={"X-CSRF-Token": csrf_token},
        )

        if expected_permission:
            assert response.status_code == 200

            expected_response = {
                "success": True,
                "message": "Success",
            }

            checkdiff = jsondiff.diff(expected_response, response.json)
            assert checkdiff == {}

            # Check if the config was updated
            response = client.get(
                "/api/dq/config",
                query_string={"form_uid": 1},
                headers={"X-CSRF-Token": csrf_token},
            )
            assert response.status_code == 200
            print(response.json)

            expected_response = {
                "data": {
                    "form_uid": 1,
                    "survey_status_filter": [1],
                    "group_by_module_name": True,
                    "drop_duplicates": True,
                    "dq_checks": None,
                },
                "success": True,
            }

            checkdiff = jsondiff.diff(expected_response, response.json)
            assert checkdiff == {}

        else:
            assert response.status_code == 403

            expected_response = {
                "error": "User does not have the required permission: WRITE Data Quality",
                "success": False,
            }

            checkdiff = jsondiff.diff(expected_response, response.json)
            assert checkdiff == {}

    def test_add_dq_missing_value_check_all_variables(
        self,
        client,
        login_test_user,
        csrf_token,
        create_dq_config,
        user_permissions,
        request,
    ):
        """
        Test the endpoint to add a DQ missing value check
        """
        user_fixture, expected_permission = user_permissions
        request.getfixturevalue(user_fixture)

        payload = {
            "form_uid": 1,
            "type_id": 4,
            "all_questions": True,
            "module_name": "test_module",
            "flag_description": "test_flag",
            "filters": [],
            "active": True,
            "check_components": {"value": ["Is empty", "is NA"]},
        }

        response = client.post(
            "/api/dq/checks",
            json=payload,
            content_type="application/json",
            headers={"X-CSRF-Token": csrf_token},
        )
        print(response.json)

        if expected_permission:
            assert response.status_code == 200

            expected_response = {
                "success": True,
                "message": "Success",
            }

            checkdiff = jsondiff.diff(expected_response, response.json)
            assert checkdiff == {}

            # Check if the check was added
            response = client.get(
                "/api/dq/checks",
                query_string={"form_uid": 1, "type_id": 4},
                headers={"X-CSRF-Token": csrf_token},
            )
            assert response.status_code == 200
            print(response.json)

            expected_response = {
                "data": [
                    {
                        "active": True,
                        "all_questions": True,
                        "dq_check_uid": 1,
                        "filters": [],
                        "flag_description": "test_flag",
                        "form_uid": 1,
                        "module_name": "test_module",
                        "question_name": None,
                        "type_id": 4,
                        "dq_scto_form_uid": None,
                        "is_repeat_group": False,
                        "note": None,
                        "check_components": {
                            "value": ["Is empty", "is NA"],
                            "hard_min": None,
                            "hard_max": None,
                            "soft_min": None,
                            "soft_max": None,
                            "outlier_metric": None,
                            "outlier_value": None,
                            "spotcheck_score_name": None,
                            "gps_type": None,
                            "threshold": None,
                            "gps_variable": None,
                            "grid_id": None,
                        },
                    }
                ],
                "success": True,
            }

            checkdiff = jsondiff.diff(expected_response, response.json)
            assert checkdiff == {}

        else:
            assert response.status_code == 403

            expected_response = {
                "error": "User does not have the required permission: WRITE Data Quality",
                "success": False,
            }

            checkdiff = jsondiff.diff(expected_response, response.json)
            assert checkdiff == {}

    def test_add_dq_refusal_check_no_question_error(
        self,
        client,
        login_test_user,
        csrf_token,
        create_dq_config,
        load_scto_form_definition,
    ):
        """
        Test the endpoint to add a DQ missing value check
        """

        payload = {
            "form_uid": 1,
            "type_id": 6,
            "all_questions": False,
            "module_name": "test_module",
            "flag_description": "test_flag",
            "filters": [
                {
                    "filter_group": [
                        {
                            "question_name": "invalid_question",
                            "filter_operator": "Is",
                            "filter_value": "1",
                        }
                    ]
                }
            ],
            "active": True,
            "check_components": {"value": ["Is empty", "is NA"]},
        }

        response = client.post(
            "/api/dq/checks",
            json=payload,
            content_type="application/json",
            headers={"X-CSRF-Token": csrf_token},
        )
        print(response.json)

        assert response.status_code == 404
        expected_response = {
            "message": "Question name is required if check is not applied on all questions.",
            "success": False,
        }

        checkdiff = jsondiff.diff(expected_response, response.json)
        assert checkdiff == {}

    def test_add_dq_dont_know_check_all_and_question_error(
        self,
        client,
        login_test_user,
        csrf_token,
        create_dq_config,
        load_scto_form_definition,
    ):
        """
        Test the endpoint to add a DQ missing value check
        """

        payload = {
            "form_uid": 1,
            "type_id": 5,
            "all_questions": True,
            "question_name": "fac_anc_reg_1_trim",
            "module_name": "test_module",
            "flag_description": "test_flag",
            "filters": [
                {
                    "filter_group": [
                        {
                            "question_name": "invalid_question",
                            "filter_operator": "Is",
                            "filter_value": "1",
                        }
                    ]
                }
            ],
            "active": True,
            "check_components": {"value": ["Is empty", "is NA"]},
        }

        response = client.post(
            "/api/dq/checks",
            json=payload,
            content_type="application/json",
            headers={"X-CSRF-Token": csrf_token},
        )
        print(response.json)

        assert response.status_code == 404
        expected_response = {
            "message": "Question name cannot be provided if all questions is selected.",
            "success": False,
        }

        checkdiff = jsondiff.diff(expected_response, response.json)
        assert checkdiff == {}

    def test_add_dq_missing_value_check(
        self,
        client,
        login_test_user,
        csrf_token,
        create_dq_config,
        load_scto_form_definition,
        user_permissions,
        request,
    ):
        """
        Test the endpoint to add a DQ missing value check
        """
        user_fixture, expected_permission = user_permissions
        request.getfixturevalue(user_fixture)

        payload = {
            "form_uid": 1,
            "type_id": 4,
            "all_questions": False,
            "question_name": "fac_anc_reg_1_trim",
            "module_name": "test_module",
            "flag_description": "test_flag",
            "filters": [],
            "active": True,
            "check_components": {"value": ["Is empty", "is NA"]},
        }

        response = client.post(
            "/api/dq/checks",
            json=payload,
            content_type="application/json",
            headers={"X-CSRF-Token": csrf_token},
        )
        print(response.json)

        if expected_permission:
            assert response.status_code == 200

            expected_response = {
                "success": True,
                "message": "Success",
            }

            checkdiff = jsondiff.diff(expected_response, response.json)
            assert checkdiff == {}

            # Check if the check was added
            response = client.get(
                "/api/dq/checks",
                query_string={"form_uid": 1, "type_id": 4},
                headers={"X-CSRF-Token": csrf_token},
            )
            assert response.status_code == 200
            print(response.json)

            expected_response = {
                "data": [
                    {
                        "active": True,
                        "all_questions": False,
                        "dq_check_uid": 1,
                        "filters": [],
                        "flag_description": "test_flag",
                        "form_uid": 1,
                        "module_name": "test_module",
                        "question_name": "fac_anc_reg_1_trim",
                        "type_id": 4,
                        "dq_scto_form_uid": None,
                        "is_repeat_group": False,
                        "note": None,
                        "check_components": {
                            "value": ["Is empty", "is NA"],
                            "hard_min": None,
                            "hard_max": None,
                            "soft_min": None,
                            "soft_max": None,
                            "outlier_metric": None,
                            "outlier_value": None,
                            "spotcheck_score_name": None,
                            "gps_type": None,
                            "threshold": None,
                            "gps_variable": None,
                            "grid_id": None,
                        },
                    }
                ],
                "success": True,
            }

            checkdiff = jsondiff.diff(expected_response, response.json)
            assert checkdiff == {}

        else:
            assert response.status_code == 403

            expected_response = {
                "error": "User does not have the required permission: WRITE Data Quality",
                "success": False,
            }

            checkdiff = jsondiff.diff(expected_response, response.json)
            assert checkdiff == {}

    def test_add_dq_missing_value_check_invalid_question(
        self,
        client,
        login_test_user,
        csrf_token,
        create_dq_config,
        load_scto_form_definition,
    ):
        """
        Test the endpoint to add a DQ missing value check
        """

        payload = {
            "form_uid": 1,
            "type_id": 4,
            "all_questions": False,
            "question_name": "fac_anc_reg_1_trim_invalid",
            "module_name": "test_module",
            "flag_description": "test_flag",
            "filters": [],
            "active": True,
            "check_components": {"value": ["Is empty", "is NA"]},
        }

        response = client.post(
            "/api/dq/checks",
            json=payload,
            content_type="application/json",
            headers={"X-CSRF-Token": csrf_token},
        )
        print(response.json)

        assert response.status_code == 404
        expected_response = {
            "message": "Question name 'fac_anc_reg_1_trim_invalid' not found in form definition. Active checks must have a valid question name.",
            "success": False,
        }

        checkdiff = jsondiff.diff(expected_response, response.json)
        assert checkdiff == {}

    def test_update_dq_missing_value_check(
        self,
        client,
        login_test_user,
        csrf_token,
        create_dq_check,
        user_permissions,
        request,
    ):
        """
        Test the endpoint to update the DQ check

        """
        user_fixture, expected_permission = user_permissions
        request.getfixturevalue(user_fixture)

        payload = {
            "form_uid": 1,
            "type_id": 4,
            "all_questions": False,
            "question_name": "fac_anc_reg_1_trim",
            "module_name": "test_module",
            "flag_description": "test_flag_updated",
            "filters": [
                {
                    "filter_group": [
                        {
                            "question_name": "fac_4anc",
                            "filter_operator": "Is",
                            "filter_value": "1",
                        },
                        {
                            "question_name": "fac_4hb",
                            "filter_operator": "Is",
                            "filter_value": "3",
                        },
                    ]
                },
                {
                    "filter_group": [
                        {
                            "question_name": "fac_sev_anem_treat",
                            "filter_operator": "Greater than",
                            "filter_value": "0",
                        }
                    ]
                },
            ],
            "active": True,
            "check_components": {"value": ["Is empty", "is NA"]},
        }

        response = client.put(
            "/api/dq/checks/1",
            json=payload,
            content_type="application/json",
            headers={"X-CSRF-Token": csrf_token},
        )
        print(response.json)

        if expected_permission:
            assert response.status_code == 200

            expected_response = {
                "success": True,
                "message": "Success",
            }

            checkdiff = jsondiff.diff(expected_response, response.json)
            assert checkdiff == {}

            # Check if the check was updated
            response = client.get(
                "/api/dq/checks",
                query_string={"form_uid": 1, "type_id": 4},
                headers={"X-CSRF-Token": csrf_token},
            )
            assert response.status_code == 200
            print(response.json)

            expected_response = {
                "data": [
                    {
                        "active": True,
                        "all_questions": False,
                        "dq_check_uid": 1,
                        "dq_scto_form_uid": None,
                        "filters": [
                            {
                                "filter_group": [
                                    {
                                        "filter_group_id": 1,
                                        "filter_operator": "Is",
                                        "filter_value": "1",
                                        "question_name": "fac_4anc",
                                        "is_repeat_group": False,
                                    },
                                    {
                                        "filter_group_id": 1,
                                        "filter_operator": "Is",
                                        "filter_value": "3",
                                        "question_name": "fac_4hb",
                                        "is_repeat_group": False,
                                    },
                                ]
                            },
                            {
                                "filter_group": [
                                    {
                                        "filter_group_id": 2,
                                        "filter_operator": "Greater than",
                                        "filter_value": "0",
                                        "question_name": "fac_sev_anem_treat",
                                        "is_repeat_group": False,
                                    }
                                ]
                            },
                        ],
                        "flag_description": "test_flag_updated",
                        "form_uid": 1,
                        "is_repeat_group": False,
                        "module_name": "test_module",
                        "note": None,
                        "question_name": "fac_anc_reg_1_trim",
                        "type_id": 4,
                        "check_components": {
                            "value": ["Is empty", "is NA"],
                            "hard_min": None,
                            "hard_max": None,
                            "soft_min": None,
                            "soft_max": None,
                            "outlier_metric": None,
                            "outlier_value": None,
                            "spotcheck_score_name": None,
                            "gps_type": None,
                            "threshold": None,
                            "gps_variable": None,
                            "grid_id": None,
                        },
                    }
                ],
                "success": True,
            }

            checkdiff = jsondiff.diff(expected_response, response.json)
            assert checkdiff == {}

        else:
            assert response.status_code == 403

            expected_response = {
                "error": "User does not have the required permission: WRITE Data Quality",
                "success": False,
            }

            checkdiff = jsondiff.diff(expected_response, response.json)
            assert checkdiff == {}

    def test_add_dq_missing_value_check_invalid_filter_question(
        self,
        client,
        login_test_user,
        csrf_token,
        create_dq_config,
        load_scto_form_definition,
    ):
        """
        Test the endpoint to add a DQ missing value check
        """

        payload = {
            "form_uid": 1,
            "type_id": 4,
            "all_questions": False,
            "question_name": "fac_anc_reg_1_trim",
            "module_name": "test_module",
            "flag_description": "test_flag",
            "filters": [
                {
                    "filter_group": [
                        {
                            "question_name": "invalid_question",
                            "filter_operator": "Is",
                            "filter_value": "1",
                        }
                    ]
                }
            ],
            "active": True,
            "check_components": {"value": ["Is empty", "is NA"]},
        }

        response = client.post(
            "/api/dq/checks",
            json=payload,
            content_type="application/json",
            headers={"X-CSRF-Token": csrf_token},
        )
        print(response.json)

        assert response.status_code == 404
        expected_response = {
            "message": "Question name 'invalid_question' used in filters not found in form definition. Active checks must have valid question names in filters.",
            "success": False,
        }

        checkdiff = jsondiff.diff(expected_response, response.json)
        assert checkdiff == {}

    def test_get_missing_value_check_inactive(
        self,
        app,
        client,
        login_test_user,
        csrf_token,
        create_dq_check,
        request,
    ):
        """
        Test the endpoint to update the DQ check

        """
        payload = {
            "form_uid": 1,
            "type_id": 4,
            "all_questions": False,
            "question_name": "fac_anc_reg_1_trim",
            "module_name": "test_module",
            "flag_description": "test_flag_updated",
            "filters": [
                {
                    "filter_group": [
                        {
                            "question_name": "fac_4anc",
                            "filter_operator": "Is",
                            "filter_value": "1",
                        },
                    ]
                },
            ],
            "active": True,
            "check_components": {"value": ["Is empty", "is NA"]},
        }

        response = client.put(
            "/api/dq/checks/1",
            json=payload,
            content_type="application/json",
            headers={"X-CSRF-Token": csrf_token},
        )
        print(response.json)

        # Delete the question from the form definition
        delete_scto_question(app, db, 1, "fac_anc_reg_1_trim")

        # Check if the check is marked as inactive
        response = client.get(
            "/api/dq/checks",
            query_string={"form_uid": 1, "type_id": 4},
            headers={"X-CSRF-Token": csrf_token},
        )
        assert response.status_code == 200
        print(response.json)

        expected_response = {
            "data": [
                {
                    "active": False,
                    "all_questions": False,
                    "check_components": {},
                    "dq_check_uid": 1,
                    "dq_scto_form_uid": None,
                    "filters": [
                        {
                            "filter_group": [
                                {
                                    "filter_group_id": 1,
                                    "filter_operator": "Is",
                                    "filter_value": "1",
                                    "question_name": "fac_4anc",
                                    "is_repeat_group": False,
                                },
                            ]
                        }
                    ],
                    "flag_description": "test_flag_updated",
                    "form_uid": 1,
                    "is_repeat_group": False,
                    "module_name": "test_module",
                    "note": "Question not found in form definition",
                    "question_name": "fac_anc_reg_1_trim",
                    "type_id": 4,
                    "check_components": {
                        "value": ["Is empty", "is NA"],
                        "hard_min": None,
                        "hard_max": None,
                        "soft_min": None,
                        "soft_max": None,
                        "outlier_metric": None,
                        "outlier_value": None,
                        "spotcheck_score_name": None,
                        "gps_type": None,
                        "threshold": None,
                        "gps_variable": None,
                        "grid_id": None,
                    },
                }
            ],
            "success": True,
        }

        checkdiff = jsondiff.diff(expected_response, response.json)
        assert checkdiff == {}

    def test_get_dq_config_inactive(
        self,
        app,
        client,
        login_test_user,
        csrf_token,
        create_dq_check,
        request,
    ):
        """
        Test the endpoint to update the DQ check

        """
        payload = {
            "form_uid": 1,
            "type_id": 4,
            "all_questions": False,
            "question_name": "fac_anc_reg_1_trim",
            "module_name": "test_module",
            "flag_description": "test_flag_updated",
            "filters": [
                {
                    "filter_group": [
                        {
                            "question_name": "fac_4anc",
                            "filter_operator": "Is",
                            "filter_value": "1",
                        },
                    ]
                },
            ],
            "active": True,
            "check_components": {"value": ["Is empty", "is NA"]},
        }

        response = client.put(
            "/api/dq/checks/1",
            json=payload,
            content_type="application/json",
            headers={"X-CSRF-Token": csrf_token},
        )
        print(response.json)

        # Delete the question from the form definition
        delete_scto_question(app, db, 1, "fac_anc_reg_1_trim")

        # Check if the check is marked as inactive in the dq config
        response = client.get(
            "/api/dq/config",
            query_string={"form_uid": 1},
            headers={"X-CSRF-Token": csrf_token},
        )
        assert response.status_code == 200
        print(response.json)

        expected_response = {
            "data": {
                "form_uid": 1,
                "survey_status_filter": [1, 3],
                "group_by_module_name": False,
                "drop_duplicates": False,
                "dq_checks": [{"type_id": 4, "num_configured": "1", "num_active": "0"}],
            },
            "success": True,
        }

        checkdiff = jsondiff.diff(expected_response, response.json)
        assert checkdiff == {}

    def test_delete_check(
        self,
        client,
        login_test_user,
        csrf_token,
        create_dq_check,
        user_permissions,
        request,
    ):
        """
        Test the endpoint to delete the DQ check

        """
        user_fixture, expected_permission = user_permissions
        request.getfixturevalue(user_fixture)

        response = client.delete(
            "/api/dq/checks",
            json={
                "form_uid": 1,
                "type_id": 4,
                "check_uids": [1],
            },
            headers={"X-CSRF-Token": csrf_token},
        )

        if expected_permission:
            assert response.status_code == 200

            expected_response = {
                "success": True,
                "message": "Success",
            }

            checkdiff = jsondiff.diff(expected_response, response.json)
            assert checkdiff == {}

            # Check if the check was deleted
            response = client.get(
                "/api/dq/checks",
                query_string={"form_uid": 1, "type_id": 4},
                headers={"X-CSRF-Token": csrf_token},
            )
            assert response.status_code == 404
            print(response.json)

            expected_response = {
                "success": False,
                "data": None,
                "message": "DQ checks not found",
            }

            checkdiff = jsondiff.diff(expected_response, response.json)
            assert checkdiff == {}

        else:
            assert response.status_code == 403

            expected_response = {
                "error": "User does not have the required permission: WRITE Data Quality",
                "success": False,
            }

            checkdiff = jsondiff.diff(expected_response, response.json)
            assert checkdiff == {}

    def test_deactivate_checks(
        self,
        client,
        login_test_user,
        csrf_token,
        create_dq_check,
        user_permissions,
        request,
    ):
        """
        Test the endpoint to deactivate the DQ check

        """
        user_fixture, expected_permission = user_permissions
        request.getfixturevalue(user_fixture)

        response = client.put(
            "/api/dq/checks/deactivate",
            json={
                "form_uid": 1,
                "type_id": 4,
                "check_uids": [1],
            },
            headers={"X-CSRF-Token": csrf_token},
        )

        if expected_permission:
            assert response.status_code == 200

            expected_response = {
                "success": True,
                "message": "Success",
            }

            checkdiff = jsondiff.diff(expected_response, response.json)
            assert checkdiff == {}

            # Check if the check was deleted
            response = client.get(
                "/api/dq/checks",
                query_string={"form_uid": 1, "type_id": 4},
                headers={"X-CSRF-Token": csrf_token},
            )
            assert response.status_code == 200
            print(response.json)

            expected_response = {
                "data": [
                    {
                        "active": False,
                        "all_questions": True,
                        "dq_check_uid": 1,
                        "filters": [],
                        "flag_description": "test_flag",
                        "form_uid": 1,
                        "module_name": "test_module",
                        "question_name": None,
                        "type_id": 4,
                        "dq_scto_form_uid": None,
                        "is_repeat_group": False,
                        "note": None,
                        "check_components": {
                            "value": ["Is empty", "is NA"],
                            "hard_min": None,
                            "hard_max": None,
                            "soft_min": None,
                            "soft_max": None,
                            "outlier_metric": None,
                            "outlier_value": None,
                            "spotcheck_score_name": None,
                            "gps_type": None,
                            "threshold": None,
                            "gps_variable": None,
                            "grid_id": None,
                        },
                    }
                ],
                "success": True,
            }

            checkdiff = jsondiff.diff(expected_response, response.json)
            assert checkdiff == {}

            # Check if dq config is updated to reflect the change
            response = client.get(
                "/api/dq/config",
                query_string={"form_uid": 1},
                headers={"X-CSRF-Token": csrf_token},
            )
            print(response.json)
            assert response.status_code == 200

            expected_response = {
                "data": {
                    "form_uid": 1,
                    "survey_status_filter": [1, 3],
                    "group_by_module_name": False,
                    "drop_duplicates": False,
                    "dq_checks": [
                        {
                            "type_id": 4,
                            "num_configured": "All",
                            "num_active": "0",
                        }
                    ],
                },
                "success": True,
            }

            checkdiff = jsondiff.diff(expected_response, response.json)
            assert checkdiff == {}

        else:
            assert response.status_code == 403

            expected_response = {
                "error": "User does not have the required permission: WRITE Data Quality",
                "success": False,
            }

            checkdiff = jsondiff.diff(expected_response, response.json)
            assert checkdiff == {}

    def test_activate_checks(
        self,
        client,
        login_test_user,
        csrf_token,
        create_dq_check_inactive,
        user_permissions,
        request,
    ):
        """
        Test the endpoint to deactivate the DQ check

        """

        user_fixture, expected_permission = user_permissions
        request.getfixturevalue(user_fixture)

        response = client.put(
            "/api/dq/checks/activate",
            json={
                "form_uid": 1,
                "type_id": 4,
                "check_uids": [1],
            },
            headers={"X-CSRF-Token": csrf_token},
        )
        print(response.json)

        if expected_permission:
            assert response.status_code == 200

            expected_response = {
                "success": True,
                "message": "Success",
            }

            checkdiff = jsondiff.diff(expected_response, response.json)
            assert checkdiff == {}

            # Check if the check was deleted
            response = client.get(
                "/api/dq/checks",
                query_string={"form_uid": 1, "type_id": 4},
                headers={"X-CSRF-Token": csrf_token},
            )
            assert response.status_code == 200
            print(response.json)

            expected_response = {
                "data": [
                    {
                        "active": True,
                        "all_questions": True,
                        "dq_check_uid": 1,
                        "filters": [],
                        "flag_description": "test_flag",
                        "form_uid": 1,
                        "module_name": "test_module",
                        "question_name": None,
                        "type_id": 4,
                        "dq_scto_form_uid": None,
                        "is_repeat_group": False,
                        "note": None,
                        "check_components": {
                            "value": ["Is empty", "is NA"],
                            "hard_min": None,
                            "hard_max": None,
                            "soft_min": None,
                            "soft_max": None,
                            "outlier_metric": None,
                            "outlier_value": None,
                            "spotcheck_score_name": None,
                            "gps_type": None,
                            "threshold": None,
                            "gps_variable": None,
                            "grid_id": None,
                        },
                    }
                ],
                "success": True,
            }

            checkdiff = jsondiff.diff(expected_response, response.json)
            assert checkdiff == {}

            # Check if dq config is updated to reflect the change
            response = client.get(
                "/api/dq/config",
                query_string={"form_uid": 1},
                headers={"X-CSRF-Token": csrf_token},
            )

            assert response.status_code == 200

            expected_response = {
                "data": {
                    "form_uid": 1,
                    "survey_status_filter": [1, 3],
                    "group_by_module_name": False,
                    "drop_duplicates": False,
                    "dq_checks": [
                        {
                            "type_id": 4,
                            "num_configured": "All",
                            "num_active": "All",
                        }
                    ],
                },
                "success": True,
            }

            checkdiff = jsondiff.diff(expected_response, response.json)
            assert checkdiff == {}

        else:
            assert response.status_code == 403

            expected_response = {
                "error": "User does not have the required permission: WRITE Data Quality",
                "success": False,
            }

            checkdiff = jsondiff.diff(expected_response, response.json)
            assert checkdiff == {}

    def test_get_dq_module_names(
        self,
        client,
        login_test_user,
        csrf_token,
        create_dq_check,
        create_another_dq_check,
        user_permissions,
        request,
    ):
        """
        Test the endpoint to get the DQ config
        """
        user_fixture, expected_permission = user_permissions
        request.getfixturevalue(user_fixture)

        response = client.get(
            "/api/dq/checks/module-names",
            query_string={"form_uid": 1},
            headers={"X-CSRF-Token": csrf_token},
        )
        print(response.json)

        if expected_permission:
            assert response.status_code == 200

            expected_response = {
                "data": [
                    "test_module",
                    "test_module_1",
                ],
                "success": True,
            }

            checkdiff = jsondiff.diff(expected_response, response.json)
            assert checkdiff == {}
        else:
            assert response.status_code == 403

            expected_response = {
                "error": "User does not have the required permission: READ Data Quality",
                "success": False,
            }

            checkdiff = jsondiff.diff(expected_response, response.json)
            assert checkdiff == {}

    def test_add_dq_mismatch_check(
        self,
        client,
        login_test_user,
        csrf_token,
        create_dq_config,
        load_scto_form_definition,
        load_dq_scto_form_definition,
        user_permissions,
        request,
    ):
        """
        Test the endpoint to add a DQ mismatch check
        """
        user_fixture, expected_permission = user_permissions
        request.getfixturevalue(user_fixture)

        payload = {
            "form_uid": 1,
            "type_id": 7,
            "all_questions": False,
            "question_name": "fac_4hb",
            "module_name": "test_module",
            "dq_scto_form_uid": 2,
            "flag_description": "test_mismatch_flag",
            "filters": [],
            "active": True,
        }

        response = client.post(
            "/api/dq/checks",
            json=payload,
            content_type="application/json",
            headers={"X-CSRF-Token": csrf_token},
        )
        print(response.json)

        if expected_permission:
            assert response.status_code == 200

            expected_response = {
                "success": True,
                "message": "Success",
            }

            checkdiff = jsondiff.diff(expected_response, response.json)
            assert checkdiff == {}

            # Check if the check was added
            response = client.get(
                "/api/dq/checks",
                query_string={"form_uid": 1, "type_id": 7},
                headers={"X-CSRF-Token": csrf_token},
            )
            assert response.status_code == 200
            print(response.json)

            expected_response = {
                "data": [
                    {
                        "active": True,
                        "all_questions": False,
                        "dq_check_uid": 1,
                        "filters": [],
                        "flag_description": "test_mismatch_flag",
                        "form_uid": 1,
                        "module_name": "test_module",
                        "question_name": "fac_4hb",
                        "type_id": 7,
                        "dq_scto_form_uid": 2,
                        "is_repeat_group": False,
                        "note": None,
                        "check_components": {
                            "value": [],
                            "hard_min": None,
                            "hard_max": None,
                            "soft_min": None,
                            "soft_max": None,
                            "outlier_metric": None,
                            "outlier_value": None,
                            "spotcheck_score_name": None,
                            "gps_type": None,
                            "threshold": None,
                            "gps_variable": None,
                            "grid_id": None,
                        },
                    }
                ],
                "success": True,
            }

            checkdiff = jsondiff.diff(expected_response, response.json)
            assert checkdiff == {}

        else:
            assert response.status_code == 403

            expected_response = {
                "error": "User does not have the required permission: WRITE Data Quality",
                "success": False,
            }

            checkdiff = jsondiff.diff(expected_response, response.json)
            assert checkdiff == {}

    def test_add_dq_mismatch_check_all_questions_error(
        self,
        client,
        login_test_user,
        csrf_token,
        create_dq_config,
        load_scto_form_definition,
        load_dq_scto_form_definition,
    ):
        """
        Test the endpoint to add a DQ mismatch check with all questions gives error
        """

        payload = {
            "form_uid": 1,
            "type_id": 7,
            "all_questions": True,
            "module_name": "test_module",
            "dq_scto_form_uid": 2,
            "flag_description": "test_mismatch_flag",
            "filters": [],
            "active": True,
        }

        response = client.post(
            "/api/dq/checks",
            json=payload,
            content_type="application/json",
            headers={"X-CSRF-Token": csrf_token},
        )
        print(response.json)

        assert response.status_code == 404

        expected_response = {
            "message": "All questions is only allowed for missing, don't knows and refusals checks",
            "success": False,
        }

        checkdiff = jsondiff.diff(expected_response, response.json)
        assert checkdiff == {}

    def test_add_dq_protocol_violation_check(
        self,
        client,
        login_test_user,
        csrf_token,
        create_dq_config,
        load_dq_scto_form_definition,
        user_permissions,
        request,
    ):
        """
        Test the endpoint to add a DQ protocol violation check
        """
        user_fixture, expected_permission = user_permissions
        request.getfixturevalue(user_fixture)

        payload = {
            "form_uid": 1,
            "type_id": 8,
            "all_questions": False,
            "question_name": "sc_dc_found",
            "module_name": "test_module",
            "dq_scto_form_uid": 2,
            "flag_description": "test_pv_flag",
            "filters": [],
            "active": True,
        }

        response = client.post(
            "/api/dq/checks",
            json=payload,
            content_type="application/json",
            headers={"X-CSRF-Token": csrf_token},
        )
        print(response.json)

        if expected_permission:
            assert response.status_code == 200

            expected_response = {
                "success": True,
                "message": "Success",
            }

            checkdiff = jsondiff.diff(expected_response, response.json)
            assert checkdiff == {}

            # Check if the check was added
            response = client.get(
                "/api/dq/checks",
                query_string={"form_uid": 1, "type_id": 8},
                headers={"X-CSRF-Token": csrf_token},
            )
            assert response.status_code == 200
            print(response.json)

            expected_response = {
                "data": [
                    {
                        "active": True,
                        "all_questions": False,
                        "dq_check_uid": 1,
                        "filters": [],
                        "flag_description": "test_pv_flag",
                        "form_uid": 1,
                        "module_name": "test_module",
                        "question_name": "sc_dc_found",
                        "type_id": 8,
                        "dq_scto_form_uid": 2,
                        "is_repeat_group": False,
                        "note": None,
                        "check_components": {
                            "value": [],
                            "hard_min": None,
                            "hard_max": None,
                            "soft_min": None,
                            "soft_max": None,
                            "outlier_metric": None,
                            "outlier_value": None,
                            "spotcheck_score_name": None,
                            "gps_type": None,
                            "threshold": None,
                            "gps_variable": None,
                            "grid_id": None,
                        },
                    }
                ],
                "success": True,
            }

            checkdiff = jsondiff.diff(expected_response, response.json)
            assert checkdiff == {}

        else:
            assert response.status_code == 403

            expected_response = {
                "error": "User does not have the required permission: WRITE Data Quality",
                "success": False,
            }

            checkdiff = jsondiff.diff(expected_response, response.json)
            assert checkdiff == {}

    def test_add_dq_protocol_violation_check_invalid_question(
        self,
        client,
        login_test_user,
        csrf_token,
        create_dq_config,
        load_scto_form_definition,
        load_dq_scto_form_definition,
    ):
        """
        Test the endpoint to add a DQ protocol violation check with invalid question name
        """

        payload = {
            "form_uid": 1,
            "type_id": 8,
            "all_questions": False,
            "question_name": "pr_invalid",
            "module_name": "test_module",
            "flag_description": "test_flag",
            "dq_scto_form_uid": 2,
            "filters": [],
            "active": True,
            "check_components": {"value": ["Is empty", "is NA"]},
        }

        response = client.post(
            "/api/dq/checks",
            json=payload,
            content_type="application/json",
            headers={"X-CSRF-Token": csrf_token},
        )
        print(response.json)

        assert response.status_code == 404
        expected_response = {
            "message": "Question name 'pr_invalid' not found in DQ form definition. Active checks must have a valid question name.",
            "success": False,
        }

        checkdiff = jsondiff.diff(expected_response, response.json)
        assert checkdiff == {}

    def test_add_dq_spotcheck_score_check(
        self,
        client,
        login_test_user,
        csrf_token,
        create_dq_config,
        load_scto_form_definition,
        load_dq_scto_form_definition,
        user_permissions,
        request,
    ):
        """
        Test the endpoint to add a DQ spotcheck score check
        """
        user_fixture, expected_permission = user_permissions
        request.getfixturevalue(user_fixture)

        payload = {
            "form_uid": 1,
            "type_id": 9,
            "all_questions": False,
            "question_name": "sc_probing_rate",
            "module_name": "test_module",
            "dq_scto_form_uid": 2,
            "flag_description": "test_ss_flag",
            "filters": [],
            "active": True,
            "check_components": {
                "spotcheck_score_name": "probing_rate",
            },
        }

        response = client.post(
            "/api/dq/checks",
            json=payload,
            content_type="application/json",
            headers={"X-CSRF-Token": csrf_token},
        )
        print(response.json)

        if expected_permission:
            assert response.status_code == 200

            expected_response = {
                "success": True,
                "message": "Success",
            }

            checkdiff = jsondiff.diff(expected_response, response.json)
            assert checkdiff == {}

            # Check if the check was added
            response = client.get(
                "/api/dq/checks",
                query_string={"form_uid": 1, "type_id": 9},
                headers={"X-CSRF-Token": csrf_token},
            )
            assert response.status_code == 200
            print(response.json)

            expected_response = {
                "data": [
                    {
                        "active": True,
                        "all_questions": False,
                        "dq_check_uid": 1,
                        "filters": [],
                        "flag_description": "test_ss_flag",
                        "form_uid": 1,
                        "module_name": "test_module",
                        "question_name": "sc_probing_rate",
                        "type_id": 9,
                        "dq_scto_form_uid": 2,
                        "is_repeat_group": False,
                        "note": None,
                        "check_components": {
                            "value": [],
                            "hard_min": None,
                            "hard_max": None,
                            "soft_min": None,
                            "soft_max": None,
                            "outlier_metric": None,
                            "outlier_value": None,
                            "spotcheck_score_name": "probing_rate",
                            "gps_type": None,
                            "threshold": None,
                            "gps_variable": None,
                            "grid_id": None,
                        },
                    }
                ],
                "success": True,
            }

            checkdiff = jsondiff.diff(expected_response, response.json)
            assert checkdiff == {}

        else:
            assert response.status_code == 403

            expected_response = {
                "error": "User does not have the required permission: WRITE Data Quality",
                "success": False,
            }

            checkdiff = jsondiff.diff(expected_response, response.json)
            assert checkdiff == {}

    def test_get_spotcheck_score_check_inactive(
        self,
        app,
        client,
        login_test_user,
        csrf_token,
        create_dq_config,
        load_dq_scto_form_definition,
        request,
    ):
        """
        Test the endpoint to update the DQ check

        """
        payload = {
            "form_uid": 1,
            "type_id": 9,
            "all_questions": False,
            "question_name": "sc_probing_rate",
            "module_name": "test_module",
            "dq_scto_form_uid": 2,
            "flag_description": "test_ss_flag",
            "filters": [],
            "active": True,
            "check_components": {
                "spotcheck_score_name": "probing_rate",
            },
        }

        response = client.post(
            "/api/dq/checks",
            json=payload,
            content_type="application/json",
            headers={"X-CSRF-Token": csrf_token},
        )
        print(response.json)

        # Delete the question from the form definition
        delete_scto_question(app, db, 2, "sc_probing_rate")

        # Check if the check is marked as inactive
        response = client.get(
            "/api/dq/checks",
            query_string={"form_uid": 1, "type_id": 9},
            headers={"X-CSRF-Token": csrf_token},
        )
        assert response.status_code == 200
        print(response.json)

        expected_response = {
            "data": [
                {
                    "active": False,
                    "all_questions": False,
                    "check_components": {},
                    "dq_check_uid": 1,
                    "dq_scto_form_uid": 2,
                    "filters": [],
                    "flag_description": "test_ss_flag",
                    "form_uid": 1,
                    "is_repeat_group": False,
                    "module_name": "test_module",
                    "note": "Question not found in DQ form definition",
                    "question_name": "sc_probing_rate",
                    "type_id": 9,
                    "check_components": {
                        "value": [],
                        "hard_min": None,
                        "hard_max": None,
                        "soft_min": None,
                        "soft_max": None,
                        "outlier_metric": None,
                        "outlier_value": None,
                        "spotcheck_score_name": "probing_rate",
                        "gps_type": None,
                        "threshold": None,
                        "gps_variable": None,
                        "grid_id": None,
                    },
                }
            ],
            "success": True,
        }

        checkdiff = jsondiff.diff(expected_response, response.json)
        assert checkdiff == {}

    def test_get_dq_config_spotcheck_score_check_inactive(
        self,
        app,
        client,
        login_test_user,
        csrf_token,
        create_dq_config,
        create_dq_check,
        load_dq_scto_form_definition,
        request,
    ):
        """
        Test the endpoint to update the DQ check

        """
        payload = {
            "form_uid": 1,
            "type_id": 9,
            "all_questions": False,
            "question_name": "sc_probing_rate",
            "module_name": "test_module",
            "dq_scto_form_uid": 2,
            "flag_description": "test_ss_flag",
            "filters": [],
            "active": True,
            "check_components": {
                "spotcheck_score_name": "probing_rate",
            },
        }

        response = client.post(
            "/api/dq/checks",
            json=payload,
            content_type="application/json",
            headers={"X-CSRF-Token": csrf_token},
        )
        print(response.json)

        # Delete the question from the form definition
        delete_scto_question(app, db, 2, "sc_probing_rate")

        # Check if the check is marked as inactive in the dq config
        response = client.get(
            "/api/dq/config",
            query_string={"form_uid": 1},
            headers={"X-CSRF-Token": csrf_token},
        )
        assert response.status_code == 200
        print(response.json)

        expected_response = {
            "data": {
                "form_uid": 1,
                "survey_status_filter": [1, 3],
                "group_by_module_name": False,
                "drop_duplicates": False,
                "dq_checks": [
                    {
                        "type_id": 4,
                        "num_configured": "All",
                        "num_active": "All",
                    },
                    {"type_id": 9, "num_configured": "1", "num_active": "0"},
                ],
            },
            "success": True,
        }

        checkdiff = jsondiff.diff(expected_response, response.json)
        assert checkdiff == {}

    def test_add_dq_constraint_check(
        self,
        client,
        login_test_user,
        csrf_token,
        create_dq_config,
        load_scto_form_definition,
        user_permissions,
        request,
    ):
        """
        Test the endpoint to add a DQ constraint check
        """
        user_fixture, expected_permission = user_permissions
        request.getfixturevalue(user_fixture)

        payload = {
            "form_uid": 1,
            "type_id": 2,
            "all_questions": False,
            "question_name": "fac_4hb",
            "module_name": "test_module",
            "flag_description": "test_constraint_flag",
            "filters": [],
            "active": True,
            "check_components": {
                "hard_min": 0.1,
                "hard_max": 100,
                "soft_min": 10,
                "soft_max": 90,
            },
        }

        response = client.post(
            "/api/dq/checks",
            json=payload,
            content_type="application/json",
            headers={"X-CSRF-Token": csrf_token},
        )
        print(response.json)

        if expected_permission:
            assert response.status_code == 200

            expected_response = {
                "success": True,
                "message": "Success",
            }

            checkdiff = jsondiff.diff(expected_response, response.json)
            assert checkdiff == {}

            # Check if the check was added
            response = client.get(
                "/api/dq/checks",
                query_string={"form_uid": 1, "type_id": 2},
                headers={"X-CSRF-Token": csrf_token},
            )
            assert response.status_code == 200
            print(response.json)

            expected_response = {
                "data": [
                    {
                        "active": True,
                        "all_questions": False,
                        "dq_check_uid": 1,
                        "filters": [],
                        "flag_description": "test_constraint_flag",
                        "form_uid": 1,
                        "module_name": "test_module",
                        "question_name": "fac_4hb",
                        "type_id": 2,
                        "dq_scto_form_uid": None,
                        "is_repeat_group": False,
                        "note": None,
                        "check_components": {
                            "value": [],
                            "hard_min": "0.1",
                            "hard_max": "100",
                            "soft_min": "10",
                            "soft_max": "90",
                            "outlier_metric": None,
                            "outlier_value": None,
                            "spotcheck_score_name": None,
                            "gps_type": None,
                            "threshold": None,
                            "gps_variable": None,
                            "grid_id": None,
                        },
                    }
                ],
                "success": True,
            }

            checkdiff = jsondiff.diff(expected_response, response.json)
            assert checkdiff == {}

        else:
            assert response.status_code == 403

            expected_response = {
                "error": "User does not have the required permission: WRITE Data Quality",
                "success": False,
            }

            checkdiff = jsondiff.diff(expected_response, response.json)
            assert checkdiff == {}

    def test_add_dq_constraint_check_error(
        self,
        client,
        login_test_user,
        csrf_token,
        create_dq_config,
        load_scto_form_definition,
    ):
        """
        Test the endpoint to add a DQ constraint check

        """
        payload = {
            "form_uid": 1,
            "type_id": 2,
            "all_questions": False,
            "question_name": "fac_4hb",
            "module_name": "test_module",
            "flag_description": "test_constraint_flag",
            "filters": [],
            "active": True,
        }

        response = client.post(
            "/api/dq/checks",
            json=payload,
            content_type="application/json",
            headers={"X-CSRF-Token": csrf_token},
        )
        print(response.json)

        assert response.status_code == 404

        expected_response = {
            "message": "At least one of hard_min, hard_max, soft_min, soft_max fields is required for constraint checks",
            "success": False,
        }

        checkdiff = jsondiff.diff(expected_response, response.json)
        assert checkdiff == {}

    def test_add_dq_outlier_check(
        self,
        client,
        login_test_user,
        csrf_token,
        create_dq_config,
        load_scto_form_definition,
        user_permissions,
        request,
    ):
        """
        Test the endpoint to add a DQ constraint check
        """
        user_fixture, expected_permission = user_permissions
        request.getfixturevalue(user_fixture)

        payload = {
            "form_uid": 1,
            "type_id": 3,
            "all_questions": False,
            "question_name": "fac_4hb",
            "module_name": "test_module",
            "flag_description": "test_outlier_flag",
            "filters": [],
            "active": True,
            "check_components": {
                "outlier_metric": "interquartile_range",
                "outlier_value": 1.5,
            },
        }

        response = client.post(
            "/api/dq/checks",
            json=payload,
            content_type="application/json",
            headers={"X-CSRF-Token": csrf_token},
        )
        print(response.json)

        if expected_permission:
            assert response.status_code == 200

            expected_response = {
                "success": True,
                "message": "Success",
            }

            checkdiff = jsondiff.diff(expected_response, response.json)
            assert checkdiff == {}

            # Check if the check was added
            response = client.get(
                "/api/dq/checks",
                query_string={"form_uid": 1, "type_id": 3},
                headers={"X-CSRF-Token": csrf_token},
            )
            assert response.status_code == 200
            print(response.json)

            expected_response = {
                "data": [
                    {
                        "active": True,
                        "all_questions": False,
                        "dq_check_uid": 1,
                        "filters": [],
                        "flag_description": "test_outlier_flag",
                        "form_uid": 1,
                        "module_name": "test_module",
                        "question_name": "fac_4hb",
                        "type_id": 3,
                        "dq_scto_form_uid": None,
                        "is_repeat_group": False,
                        "note": None,
                        "check_components": {
                            "value": [],
                            "hard_min": None,
                            "hard_max": None,
                            "soft_min": None,
                            "soft_max": None,
                            "outlier_metric": "interquartile_range",
                            "outlier_value": "1.5",
                            "spotcheck_score_name": None,
                            "gps_type": None,
                            "threshold": None,
                            "gps_variable": None,
                            "grid_id": None,
                        },
                    }
                ],
                "success": True,
            }

            checkdiff = jsondiff.diff(expected_response, response.json)
            assert checkdiff == {}

        else:
            assert response.status_code == 403

            expected_response = {
                "error": "User does not have the required permission: WRITE Data Quality",
                "success": False,
            }

            checkdiff = jsondiff.diff(expected_response, response.json)
            assert checkdiff == {}

    def test_add_dq_gps_check(
        self,
        client,
        login_test_user,
        csrf_token,
        create_dq_config,
        load_scto_form_definition,
        user_permissions,
        request,
    ):
        """
        Test the endpoint to add a DQ GPS check
        """
        user_fixture, expected_permission = user_permissions
        request.getfixturevalue(user_fixture)

        payload = {
            "form_uid": 1,
            "type_id": 10,
            "all_questions": False,
            "question_name": "fac_4hb",
            "module_name": "test_module",
            "flag_description": "test_gps_flag",
            "filters": [],
            "active": True,
            "check_components": {
                "gps_type": "point2point",
                "threshold": "50",
                "gps_variable": "fac_4anc",
            },
        }

        response = client.post(
            "/api/dq/checks",
            json=payload,
            content_type="application/json",
            headers={"X-CSRF-Token": csrf_token},
        )
        print(response.json)

        if expected_permission:
            assert response.status_code == 200

            expected_response = {
                "success": True,
                "message": "Success",
            }

            checkdiff = jsondiff.diff(expected_response, response.json)
            assert checkdiff == {}

            # Check if the GPS check was added
            response = client.get(
                "/api/dq/checks",
                query_string={"form_uid": 1, "type_id": 10},
                headers={"X-CSRF-Token": csrf_token},
            )
            assert response.status_code == 200
            print(response.json)

            expected_response = {
                "data": [
                    {
                        "active": True,
                        "all_questions": False,
                        "dq_check_uid": 1,
                        "filters": [],
                        "flag_description": "test_gps_flag",
                        "form_uid": 1,
                        "module_name": "test_module",
                        "question_name": "fac_4hb",
                        "type_id": 10,
                        "dq_scto_form_uid": None,
                        "is_repeat_group": False,
                        "note": None,
                        "check_components": {
                            "value": [],
                            "hard_min": None,
                            "hard_max": None,
                            "soft_min": None,
                            "soft_max": None,
                            "outlier_metric": None,
                            "outlier_value": None,
                            "spotcheck_score_name": None,
                            "gps_type": "point2point",
                            "threshold": "50",
                            "gps_variable": {
                                "question_name": "fac_4anc",
                                "is_repeat_group": False,
                            },
                            "grid_id": None,
                        },
                    }
                ],
                "success": True,
            }

            checkdiff = jsondiff.diff(expected_response, response.json)
            assert checkdiff == {}

        else:
            assert response.status_code == 403

            expected_response = {
                "error": "User does not have the required permission: WRITE Data Quality",
                "success": False,
            }

            checkdiff = jsondiff.diff(expected_response, response.json)
            assert checkdiff == {}

    def test_add_dq_gps_check_invalid_question(
        self,
        client,
        login_test_user,
        csrf_token,
        create_dq_config,
        load_scto_form_definition,
        load_dq_scto_form_definition,
    ):
        """
        Test the endpoint to add a DQ GPS check with invalid question name
        """

        payload = {
            "form_uid": 1,
            "type_id": 10,
            "all_questions": False,
            "question_name": "randome_question",
            "module_name": "test_module",
            "flag_description": "test_gps_flag",
            "filters": [],
            "active": True,
            "check_components": {
                "gps_type": "point2point",
                "threshold": "50",
                "gps_variable": "fac_4anc",
            },
        }

        response = client.post(
            "/api/dq/checks",
            json=payload,
            content_type="application/json",
            headers={"X-CSRF-Token": csrf_token},
        )
        print(response.json)

        assert response.status_code == 404
        expected_response = {
            "message": "Question name 'randome_question' not found in form definition. Active checks must have a valid question name.",
            "success": False,
        }

        checkdiff = jsondiff.diff(expected_response, response.json)
        assert checkdiff == {}

    def test_add_dq_gps_check_invalid_gps_variable(
        self,
        client,
        login_test_user,
        csrf_token,
        create_dq_config,
        load_scto_form_definition,
        load_dq_scto_form_definition,
    ):
        """
        Test the endpoint to add a DQ GPS check with invalid gps_variable question
        """

        payload = {
            "form_uid": 1,
            "type_id": 10,
            "all_questions": False,
            "question_name": "fac_4hb",
            "module_name": "",
            "flag_description": "",
            "filters": [],
            "active": True,
            "check_components": {
                "gps_type": "point2point",
                "threshold": "50",
                "gps_variable": "randome_question",
            },
        }

        response = client.post(
            "/api/dq/checks",
            json=payload,
            content_type="application/json",
            headers={"X-CSRF-Token": csrf_token},
        )
        print(response.json)

        assert response.status_code == 404
        expected_response = {
            "message": "Question name 'randome_question' not found in form definition. Active checks must have a valid question name for GPS checks.",
            "success": False,
        }

        checkdiff = jsondiff.diff(expected_response, response.json)
        assert checkdiff == {}

    def test_get_gps_check_inactive(
        self,
        app,
        client,
        login_test_user,
        csrf_token,
        create_dq_config,
        load_scto_form_definition,
        request,
    ):
        """
        Test the get checks endpoint correctly marks logic checks as inactive

        """
        payload = {
            "form_uid": 1,
            "type_id": 10,
            "all_questions": False,
            "question_name": "fac_4hb",
            "module_name": "test_module",
            "flag_description": "test_gps_flag",
            "filters": [],
            "active": True,
            "check_components": {
                "gps_type": "point2point",
                "threshold": "50",
                "gps_variable": "fac_4anc",
            },
        }

        response = client.post(
            "/api/dq/checks",
            json=payload,
            content_type="application/json",
            headers={"X-CSRF-Token": csrf_token},
        )
        print(response.json)

        assert response.status_code == 200

        # Delete the question from the form definition
        delete_scto_question(app, db, 1, "fac_4anc")

        # Check if the check is marked as inactive
        response = client.get(
            "/api/dq/checks",
            query_string={"form_uid": 1, "type_id": 10},
            headers={"X-CSRF-Token": csrf_token},
        )
        assert response.status_code == 200
        print(response.json)

        expected_response = {
            "data": [
                {
                    "active": False,
                    "all_questions": False,
                    "dq_check_uid": 1,
                    "filters": [],
                    "flag_description": "test_gps_flag",
                    "form_uid": 1,
                    "module_name": "test_module",
                    "question_name": "fac_4hb",
                    "type_id": 10,
                    "dq_scto_form_uid": None,
                    "is_repeat_group": False,
                    "note": "GPS variable not found in form definition",
                    "check_components": {
                        "value": [],
                        "hard_min": None,
                        "hard_max": None,
                        "soft_min": None,
                        "soft_max": None,
                        "outlier_metric": None,
                        "outlier_value": None,
                        "spotcheck_score_name": None,
                        "gps_type": "point2point",
                        "threshold": "50",
                        "gps_variable": {
                            "question_name": "fac_4anc",
                            "is_repeat_group": False,
                        },
                        "grid_id": None,
                    },
                }
            ],
            "success": True,
        }

        checkdiff = jsondiff.diff(expected_response, response.json)
        assert checkdiff == {}

    def test_get_dq_config_gps_check_inactive(
        self,
        app,
        client,
        login_test_user,
        csrf_token,
        create_dq_config,
        load_scto_form_definition,
        request,
    ):
        """
        Test the get checks endpoint correctly marks logic checks as inactive

        """
        payload = {
            "form_uid": 1,
            "type_id": 10,
            "all_questions": False,
            "question_name": "fac_4hb",
            "module_name": "test_module",
            "flag_description": "test_gps_flag",
            "filters": [],
            "active": True,
            "check_components": {
                "gps_type": "point2point",
                "threshold": "50",
                "gps_variable": "fac_4anc",
            },
        }

        response = client.post(
            "/api/dq/checks",
            json=payload,
            content_type="application/json",
            headers={"X-CSRF-Token": csrf_token},
        )
        print(response.json)

        assert response.status_code == 200

        # Delete the question from the form definition
        delete_scto_question(app, db, 1, "fac_4hb")

        # Check if the check is marked as inactive in the dq config
        response = client.get(
            "/api/dq/config",
            query_string={"form_uid": 1},
            headers={"X-CSRF-Token": csrf_token},
        )
        assert response.status_code == 200
        print(response.json)

        expected_response = {
            "data": {
                "form_uid": 1,
                "survey_status_filter": [1, 3],
                "group_by_module_name": False,
                "drop_duplicates": False,
                "dq_checks": [
                    {"type_id": 10, "num_configured": "1", "num_active": "0"},
                ],
            },
            "success": True,
        }

        checkdiff = jsondiff.diff(expected_response, response.json)
        assert checkdiff == {}

    def test_add_dq_logic_check(
        self,
        client,
        login_test_user,
        csrf_token,
        create_dq_config,
        load_scto_form_definition,
        user_permissions,
        request,
    ):
        """
        Test the endpoint to add a DQ Logic check
        """
        user_fixture, expected_permission = user_permissions
        request.getfixturevalue(user_fixture)

        payload = {
            "form_uid": 1,
            "type_id": 1,
            "all_questions": False,
            "question_name": "fac_4hb",
            "module_name": "test_module",
            "flag_description": "test_logic_flag",
            "filters": [],
            "active": True,
            "check_components": {
                "logic_check_questions": [
                    {"question_name": "fac_4hb", "alias": "A"},
                    {"question_name": "fac_4anc", "alias": "B"},
                ],
                "logic_check_assertions": [
                    {
                        "assert_group": [
                            {
                                "assertion": "A > B",
                            },
                        ]
                    },
                ],
            },
        }

        response = client.post(
            "/api/dq/checks",
            json=payload,
            content_type="application/json",
            headers={"X-CSRF-Token": csrf_token},
        )
        print(response.json)

        if expected_permission:
            assert response.status_code == 200

            expected_response = {
                "success": True,
                "message": "Success",
            }

            checkdiff = jsondiff.diff(expected_response, response.json)
            assert checkdiff == {}

            # Check if the GPS check was added
            response = client.get(
                "/api/dq/checks",
                query_string={"form_uid": 1, "type_id": 1},
                headers={"X-CSRF-Token": csrf_token},
            )
            assert response.status_code == 200
            print(response.json)

            expected_response = {
                "data": [
                    {
                        "active": True,
                        "all_questions": False,
                        "dq_check_uid": 1,
                        "filters": [],
                        "flag_description": "test_logic_flag",
                        "form_uid": 1,
                        "module_name": "test_module",
                        "question_name": "fac_4hb",
                        "type_id": 1,
                        "dq_scto_form_uid": None,
                        "is_repeat_group": False,
                        "note": None,
                        "check_components": {
                            "value": [],
                            "hard_min": None,
                            "hard_max": None,
                            "soft_min": None,
                            "soft_max": None,
                            "outlier_metric": None,
                            "outlier_value": None,
                            "spotcheck_score_name": None,
                            "gps_type": None,
                            "threshold": None,
                            "gps_variable": None,
                            "grid_id": None,
                            "logic_check_questions": [
                                {
                                    "question_name": "fac_4hb",
                                    "is_repeat_group": False,
                                    "alias": "A",
                                },
                                {
                                    "question_name": "fac_4anc",
                                    "is_repeat_group": False,
                                    "alias": "B",
                                },
                            ],
                            "logic_check_assertions": [
                                {
                                    "assert_group": [
                                        {
                                            "assert_group_id": 1,
                                            "assertion": "A > B",
                                        },
                                    ]
                                },
                            ],
                        },
                    }
                ],
                "success": True,
            }

            checkdiff = jsondiff.diff(expected_response, response.json)
            assert checkdiff == {}

        else:
            assert response.status_code == 403

            expected_response = {
                "error": "User does not have the required permission: WRITE Data Quality",
                "success": False,
            }

            checkdiff = jsondiff.diff(expected_response, response.json)
            assert checkdiff == {}

    def test_add_dq_logic_check_invalid_question_main(
        self,
        client,
        login_test_user,
        csrf_token,
        create_dq_config,
        load_scto_form_definition,
        load_dq_scto_form_definition,
    ):
        """
        Test the endpoint to add a DQ Logic check with invalid question name
        """

        payload = {
            "form_uid": 1,
            "type_id": 1,
            "all_questions": False,
            "question_name": "random_question",
            "module_name": "test_module",
            "flag_description": "test_logic_flag",
            "filters": [],
            "active": True,
            "check_components": {
                "logic_check_questions": [
                    {"question_name": "random_question", "alias": "A"},
                    {"question_name": "fac_4anc", "alias": "B"},
                ],
                "logic_check_assertions": [
                    {
                        "assert_group": [
                            {
                                "assertion": "A > B",
                            },
                        ]
                    },
                ],
            },
        }

        response = client.post(
            "/api/dq/checks",
            json=payload,
            content_type="application/json",
            headers={"X-CSRF-Token": csrf_token},
        )
        print(response.json)

        assert response.status_code == 404
        expected_response = {
            "message": "Question name 'random_question' not found in form definition. Active checks must have a valid question name.",
            "success": False,
        }

        checkdiff = jsondiff.diff(expected_response, response.json)
        assert checkdiff == {}

    def test_add_dq_logic_check_invalid_question_additional(
        self,
        client,
        login_test_user,
        csrf_token,
        create_dq_config,
        load_scto_form_definition,
        load_dq_scto_form_definition,
    ):
        """
        Test the endpoint to add a DQ Logic check with invalid question name
        """

        payload = {
            "form_uid": 1,
            "type_id": 1,
            "all_questions": False,
            "question_name": "fac_4hb",
            "module_name": "test_module",
            "flag_description": "test_logic_flag",
            "filters": [],
            "active": True,
            "check_components": {
                "logic_check_questions": [
                    {"question_name": "fac_4hb", "alias": "A"},
                    {"question_name": "random_question", "alias": "B"},
                ],
                "logic_check_assertions": [
                    {
                        "assert_group": [
                            {
                                "assertion": "A > B",
                            },
                        ]
                    },
                ],
            },
        }

        response = client.post(
            "/api/dq/checks",
            json=payload,
            content_type="application/json",
            headers={"X-CSRF-Token": csrf_token},
        )
        print(response.json)

        assert response.status_code == 404
        expected_response = {
            "message": "Question name 'random_question' not found in form definition. Active checks must have a valid question name.",
            "success": False,
        }

        checkdiff = jsondiff.diff(expected_response, response.json)
        assert checkdiff == {}

    def test_add_dq_logic_check_error(
        self,
        client,
        login_test_user,
        csrf_token,
        create_dq_config,
        load_scto_form_definition,
    ):
        """
        Test the endpoint to add a DQ Logic check
        """
        payload = {
            "form_uid": 1,
            "type_id": 1,
            "all_questions": False,
            "question_name": "fac_4hb",
            "module_name": "test_module",
            "flag_description": "test_logic_flag",
            "filters": [],
            "active": True,
            "check_components": {
                "logic_check_questions": [
                    {"question_name": "fac_4hb", "alias": "A"},
                    {"question_name": "fac_4anc", "alias": "B"},
                ]
            },
        }

        response = client.post(
            "/api/dq/checks",
            json=payload,
            content_type="application/json",
            headers={"X-CSRF-Token": csrf_token},
        )
        print(response.json)

        assert response.status_code == 404

        expected_response = {
            "message": "The field 'logic_check_assertions' is required for logic checks",
            "success": False,
        }

        checkdiff = jsondiff.diff(expected_response, response.json)
        assert checkdiff == {}

    def test_get_logic_check_inactive(
        self,
        app,
        client,
        login_test_user,
        csrf_token,
        create_dq_config,
        load_scto_form_definition,
        request,
    ):
        """
        Test the get checks endpoint correctly marks logic checks as inactive

        """
        payload = {
            "form_uid": 1,
            "type_id": 1,
            "all_questions": False,
            "question_name": "fac_4hb",
            "module_name": "test_module",
            "flag_description": "test_logic_flag",
            "filters": [],
            "active": True,
            "check_components": {
                "logic_check_questions": [
                    {"question_name": "fac_4hb", "alias": "A"},
                    {"question_name": "fac_4anc", "alias": "B"},
                ],
                "logic_check_assertions": [
                    {
                        "assert_group": [
                            {
                                "assertion": "A > B",
                            },
                        ]
                    },
                ],
            },
        }

        response = client.post(
            "/api/dq/checks",
            json=payload,
            content_type="application/json",
            headers={"X-CSRF-Token": csrf_token},
        )
        assert response.status_code == 200
        print(response.json)

        # Delete the question from the form definition
        delete_scto_question(app, db, 1, "fac_4anc")

        # Check if the check is marked as inactive
        response = client.get(
            "/api/dq/checks",
            query_string={"form_uid": 1, "type_id": 1},
            headers={"X-CSRF-Token": csrf_token},
        )
        assert response.status_code == 200
        print(response.json)

        expected_response = {
            "data": [
                {
                    "active": False,
                    "all_questions": False,
                    "dq_check_uid": 1,
                    "filters": [],
                    "flag_description": "test_logic_flag",
                    "form_uid": 1,
                    "module_name": "test_module",
                    "question_name": "fac_4hb",
                    "type_id": 1,
                    "dq_scto_form_uid": None,
                    "is_repeat_group": False,
                    "note": "Logic check question not found in form definition",
                    "check_components": {
                        "value": [],
                        "hard_min": None,
                        "hard_max": None,
                        "soft_min": None,
                        "soft_max": None,
                        "outlier_metric": None,
                        "outlier_value": None,
                        "spotcheck_score_name": None,
                        "gps_type": None,
                        "threshold": None,
                        "gps_variable": None,
                        "grid_id": None,
                        "logic_check_questions": [
                            {
                                "question_name": "fac_4hb",
                                "is_repeat_group": False,
                                "alias": "A",
                            },
                            {
                                "question_name": "fac_4anc",
                                "is_repeat_group": False,
                                "alias": "B",
                            },
                        ],
                        "logic_check_assertions": [
                            {
                                "assert_group": [
                                    {
                                        "assert_group_id": 1,
                                        "assertion": "A > B",
                                    },
                                ]
                            },
                        ],
                    },
                }
            ],
            "success": True,
        }
        checkdiff = jsondiff.diff(expected_response, response.json)
        assert checkdiff == {}

    def test_get_dq_config_logic_check_inactive(
        self,
        app,
        client,
        login_test_user,
        csrf_token,
        create_dq_config,
        load_scto_form_definition,
        request,
    ):
        """
        Test the get config endpoint correctly marks logic checks as inactive

        """
        payload = {
            "form_uid": 1,
            "type_id": 1,
            "all_questions": False,
            "question_name": "fac_4hb",
            "module_name": "test_module",
            "flag_description": "test_logic_flag",
            "filters": [],
            "active": True,
            "check_components": {
                "logic_check_questions": [
                    {"question_name": "fac_4hb", "alias": "A"},
                    {"question_name": "fac_4anc", "alias": "B"},
                ],
                "logic_check_assertions": [
                    {
                        "assert_group": [
                            {
                                "assertion": "A > B",
                            },
                        ]
                    },
                ],
            },
        }

        response = client.post(
            "/api/dq/checks",
            json=payload,
            content_type="application/json",
            headers={"X-CSRF-Token": csrf_token},
        )
        assert response.status_code == 200
        print(response.json)

        # Delete the question from the form definition
        delete_scto_question(app, db, 1, "fac_4anc")

        # Check if the check is marked as inactive in the dq config
        response = client.get(
            "/api/dq/config",
            query_string={"form_uid": 1},
            headers={"X-CSRF-Token": csrf_token},
        )
        assert response.status_code == 200
        print(response.json)

        expected_response = {
            "data": {
                "form_uid": 1,
                "survey_status_filter": [1, 3],
                "group_by_module_name": False,
                "drop_duplicates": False,
                "dq_checks": [
                    {"type_id": 1, "num_configured": "1", "num_active": "0"},
                ],
            },
            "success": True,
        }

        checkdiff = jsondiff.diff(expected_response, response.json)
        assert checkdiff == {}

    def test_update_dq_logic_check(
        self,
        client,
        login_test_user,
        csrf_token,
        create_dq_config,
        load_scto_form_definition,
    ):
        """
        Test the endpoint to update the DQ check

        """

        payload = {
            "form_uid": 1,
            "type_id": 1,
            "all_questions": False,
            "question_name": "fac_4hb",
            "module_name": "test_module",
            "flag_description": "test_logic_flag",
            "filters": [],
            "active": True,
            "check_components": {
                "logic_check_questions": [
                    {"question_name": "fac_4hb", "alias": "A"},
                    {"question_name": "fac_4anc", "alias": "B"},
                ],
                "logic_check_assertions": [
                    {
                        "assert_group": [
                            {
                                "assertion": "A > B",
                            },
                        ]
                    },
                ],
            },
        }

        response = client.post(
            "/api/dq/checks",
            json=payload,
            content_type="application/json",
            headers={"X-CSRF-Token": csrf_token},
        )
        print(response.json)

        payload = {
            "form_uid": 1,
            "type_id": 1,
            "all_questions": False,
            "question_name": "fac_4hb",
            "module_name": "test_module",
            "flag_description": "test_logic_flag_updated",
            "filters": [],
            "active": True,
            "check_components": {
                "logic_check_questions": [
                    {"question_name": "fac_4hb", "alias": "A"},
                    {"question_name": "fac_4anc", "alias": "B"},
                ],
                "logic_check_assertions": [
                    {
                        "assert_group": [
                            {
                                "assertion": "A < B",
                            },
                        ]
                    },
                ],
            },
        }

        response = client.put(
            "/api/dq/checks/1",
            json=payload,
            content_type="application/json",
            headers={"X-CSRF-Token": csrf_token},
        )
        print(response.json)

        assert response.status_code == 200

        expected_response = {
            "success": True,
            "message": "Success",
        }

        checkdiff = jsondiff.diff(expected_response, response.json)
        assert checkdiff == {}

        # Check if the check was updated
        response = client.get(
            "/api/dq/checks",
            query_string={"form_uid": 1, "type_id": 1},
            headers={"X-CSRF-Token": csrf_token},
        )
        assert response.status_code == 200
        print(response.json)

        expected_response = {
            "data": [
                {
                    "active": True,
                    "all_questions": False,
                    "dq_check_uid": 1,
                    "filters": [],
                    "flag_description": "test_logic_flag_updated",
                    "form_uid": 1,
                    "module_name": "test_module",
                    "question_name": "fac_4hb",
                    "type_id": 1,
                    "dq_scto_form_uid": None,
                    "is_repeat_group": False,
                    "note": None,
                    "check_components": {
                        "value": [],
                        "hard_min": None,
                        "hard_max": None,
                        "soft_min": None,
                        "soft_max": None,
                        "outlier_metric": None,
                        "outlier_value": None,
                        "spotcheck_score_name": None,
                        "gps_type": None,
                        "threshold": None,
                        "gps_variable": None,
                        "grid_id": None,
                        "logic_check_questions": [
                            {
                                "question_name": "fac_4hb",
                                "is_repeat_group": False,
                                "alias": "A",
                            },
                            {
                                "question_name": "fac_4anc",
                                "is_repeat_group": False,
                                "alias": "B",
                            },
                        ],
                        "logic_check_assertions": [
                            {
                                "assert_group": [
                                    {
                                        "assert_group_id": 1,
                                        "assertion": "A < B",
                                    },
                                ]
                            },
                        ],
                    },
                }
            ],
            "success": True,
        }

        checkdiff = jsondiff.diff(expected_response, response.json)
        assert checkdiff == {}
