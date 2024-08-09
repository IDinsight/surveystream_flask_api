import jsondiff
import pytest

from utils import (
    load_reference_data,
    create_new_survey_role_with_permissions,
    login_user,
    set_target_assignable_status,
    update_logged_in_user_roles,
)


@pytest.mark.forms
class TestForms:
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
    def user_with_dq_forms_permissions(self, client, test_user_credentials):
        # Assign new roles and permissions
        new_role = create_new_survey_role_with_permissions(
            # 23 - WRITE Data Quality Forms
            client,
            test_user_credentials,
            "Data Quality Forms Role",
            [23],
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
            ("user_with_no_permissions", False),
        ],
        ids=[
            "super_admin_permissions",
            "survey_admin_permissions",
            "no_permissions",
        ],
    )
    def user_permissions(self, request):
        return request.param

    @pytest.fixture(
        params=[
            ("user_with_super_admin_permissions", True),
            ("user_with_survey_admin_permissions", True),
            ("user_with_dq_forms_permissions", True),
            ("user_with_no_permissions", False),
        ],
        ids=[
            "super_admin_permissions",
            "survey_admin_permissions",
            "dq_forms_permissions",
            "no_permissions",
        ],
    )
    def user_with_dq_forms_permissions(self, request):
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
    def create_parent_form(self, client, login_test_user, csrf_token, create_survey):
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
    def create_dq_form(
        self, client, login_test_user, csrf_token, create_survey, create_parent_form
    ):
        """
        Insert new dq form as a setup step for the form tests
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

    def test_create_parent_form(self, client, login_test_user, create_parent_form):
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
                    "last_ingested_at": None,
                    "form_type": "parent",
                    "parent_form_uid": None,
                    "dq_form_type": None,
                    "parent_scto_form_id": None,
                }
            ],
            "success": True,
        }

        checkdiff = jsondiff.diff(expected_response, response.json)
        assert checkdiff == {}

    def test_get_forms(
        self, client, login_test_user, create_parent_form, test_user_credentials
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
                    "last_ingested_at": None,
                    "form_type": "parent",
                    "parent_form_uid": None,
                    "dq_form_type": None,
                    "parent_scto_form_id": None,
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
        print(response.json)
        assert response.status_code == 200

        checkdiff = jsondiff.diff(expected_response, response.json)
        assert checkdiff == {}

        # Get the form using the form_uid
        response = client.get("/api/forms/1")
        assert response.status_code == 200

        expected_response["data"] = expected_response["data"][0]

        checkdiff = jsondiff.diff(expected_response, response.json)
        assert checkdiff == {}

    def test_update_form(self, client, login_test_user, create_parent_form, csrf_token):
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
            "form_type": "parent",
            "parent_form_uid": None,
            "dq_form_type": None,
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
                "last_ingested_at": None,
                "form_type": "parent",
                "parent_form_uid": None,
                "dq_form_type": None,
                "parent_scto_form_id": None,
            },
            "success": True,
        }

        checkdiff = jsondiff.diff(expected_response, response.json)
        assert checkdiff == {}

    def test_delete_form(self, client, login_test_user, create_parent_form, csrf_token):
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
        self, client, login_test_user, create_parent_form, csrf_token
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

    def test_create_scto_question_mapping(
        self, client, csrf_token, login_test_user, create_parent_form
    ):
        """
        Test that the SCTO question mapping is inserted correctly
        """

        # Insert the SCTO question mapping
        payload = {
            "form_uid": 1,
            "survey_status": "test_survey_status",
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

        # Test the SCTO question mapping was inserted correctly
        response = client.get("/api/forms/1/scto-question-mapping")
        assert response.status_code == 200

        expected_response = {
            "data": {
                "form_uid": 1,
                "survey_status": "test_survey_status",
                "revisit_section": "test_revisit_section",
                "target_id": "test_target_id",
                "enumerator_id": "test_enumerator_id",
                "dq_enumerator_id": None,
                "locations": {
                    "location_1": "test_location_1",
                },
            },
            "success": True,
        }

        checkdiff = jsondiff.diff(expected_response, response.json)
        assert checkdiff == {}

    def test_update_scto_question_mapping(self, client, csrf_token, create_parent_form):
        """
        Test that the SCTO question mapping is updated correctly
        """

        # Insert the SCTO question mapping
        payload = {
            "form_uid": 1,
            "survey_status": "test_survey_status",
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

        # Update the SCTO question mapping
        payload = {
            "form_uid": 1,
            "survey_status": "test_survey_status_updated",
            "revisit_section": "test_revisit_section_updated",
            "target_id": "test_target_id_updated",
            "enumerator_id": "test_enumerator_id_updated",
            "locations": {
                "location_1": "test_location_1_updated",
                "location_2": "test_location_2_updated",
            },
        }

        response = client.put(
            "/api/forms/1/scto-question-mapping",
            json=payload,
            content_type="application/json",
            headers={"X-CSRF-Token": csrf_token},
        )
        assert response.status_code == 200

        # Test the SCTO question mapping was updated correctly
        response = client.get("/api/forms/1/scto-question-mapping")
        assert response.status_code == 200

        expected_response = {
            "data": {
                "form_uid": 1,
                "survey_status": "test_survey_status_updated",
                "revisit_section": "test_revisit_section_updated",
                "target_id": "test_target_id_updated",
                "enumerator_id": "test_enumerator_id_updated",
                "dq_enumerator_id": None,
                "locations": {
                    "location_1": "test_location_1_updated",
                    "location_2": "test_location_2_updated",
                },
            },
            "success": True,
        }

        checkdiff = jsondiff.diff(expected_response, response.json)
        assert checkdiff == {}

    def test_delete_form_cascade_to_scto_question_mapping(
        self, client, csrf_token, create_parent_form
    ):
        """
        Test that deleting the form deletes the SCTO question mapping
        """

        # Insert the SCTO question mapping
        payload = {
            "form_uid": 1,
            "survey_status": "test_survey_status",
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

        # Delete the form
        response = client.delete(
            "/api/forms/1",
            headers={"X-CSRF-Token": csrf_token},
        )
        assert response.status_code == 204

        # Test the SCTO question mapping was deleted correctly
        response = client.get("/api/forms/1/scto-question-mapping")
        assert response.status_code == 404

    def test_delete_scto_question_mapping(
        self, client, login_test_user, create_parent_form, csrf_token
    ):
        """
        Test that a question mapping can be deleted
        """

        # Insert the question mapping
        payload = {
            "form_uid": 1,
            "survey_status": "test_survey_status",
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

        # Delete the question mapping

        response = client.delete(
            "/api/forms/1/scto-question-mapping",
            headers={"X-CSRF-Token": csrf_token},
        )
        assert response.status_code == 204

        # Check the response
        response = client.get("/api/forms/1/scto-question-mapping")

        assert response.status_code == 404

    @pytest.mark.run_only
    def test_scto_form_duplicate_choice_error(
        self, client, login_test_user, csrf_token, create_parent_form
    ):
        """
        Test that an SCTO form with duplicate choices raises an error
        """

        # Update the parent form with the scto form id test_choice_list_duplicate_values

        payload = {
            "scto_form_id": "test_choice_list_duplicate_values",
            "form_name": "Agrifieldnet Main Form",
            "tz_name": "Asia/Kolkata",
            "scto_server_name": "dod",
            "encryption_key_shared": False,
            "server_access_role_granted": False,
            "server_access_allowed": False,
            "form_type": "parent",
            "parent_form_uid": None,
            "dq_form_type": None,
        }

        response = client.put(
            "/api/forms/1",
            json=payload,
            content_type="application/json",
            headers={"X-CSRF-Token": csrf_token},
        )
        assert response.status_code == 200

        # Ingest the SCTO variables from SCTO into the database
        response = client.post(
            "/api/forms/1/scto-form-definition/refresh",
            headers={"X-CSRF-Token": csrf_token},
        )
        print(response.json)
        assert response.status_code == 422

        expected_response = {
            "success": False,
            "errors": [
                "Duplicate choice values found for list_name=state and value=10 on the choices tab of the SurveyCTO form definition"
            ],
        }

    @pytest.mark.run_only
    def test_scto_form_definition(
        self, client, login_test_user, csrf_token, create_parent_form
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
        print(response.json)
        assert response.status_code == 200

        # Get the SCTO questions from the database
        response = client.get(
            "/api/forms/1/scto-form-definition",
        )
        assert response.status_code == 200

        checkdiff = jsondiff.diff(expected_response, response.json)
        assert checkdiff == {}

    def test_refresh_scto_form_definition(
        self, client, login_test_user, csrf_token, create_parent_form
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
            "/api/forms/1/scto-form-definition",
        )
        assert response.status_code == 200

        checkdiff = jsondiff.diff(expected_response, response.json)
        assert checkdiff == {}

    def test_delete_parent_form_cascade_to_scto_form_definition(
        self, client, login_test_user, csrf_token, create_parent_form
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
            "/api/forms/1/scto-form-definition",
        )
        assert response.status_code == 404

    def test_delete_scto_form_definition(
        self, client, login_test_user, create_parent_form, csrf_token
    ):
        """
        Test that a form definition can be deleted
        """

        # Ingest the SCTO variables from SCTO into the database
        response = client.post(
            "/api/forms/1/scto-form-definition/refresh",
            headers={"X-CSRF-Token": csrf_token},
        )
        assert response.status_code == 200

        # Delete the form definition

        response = client.delete(
            "/api/forms/1/scto-form-definition",
            headers={"X-CSRF-Token": csrf_token},
        )
        assert response.status_code == 204

        # Check the response
        response = client.get("/api/forms/1/scto-form-definition")

        assert response.status_code == 200
        assert response.json == {"data": None, "success": True}

    def test_create_dq_form(
        self,
        client,
        login_test_user,
        create_parent_form,
        csrf_token,
        user_with_dq_forms_permissions,
        request,
    ):
        """
        Test that the dq form is inserted correctly
        """

        user_fixture, expected_permission = user_with_dq_forms_permissions
        request.getfixturevalue(user_fixture)

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

        if expected_permission:
            assert response.status_code == 201

            # Test the form was inserted correctly
            response = client.get("/api/forms?survey_uid=1&form_type=dq")
            assert response.status_code == 200

            expected_response = {
                "data": [
                    {
                        "form_uid": 2,
                        "survey_uid": 1,
                        "scto_form_id": "test_scto_dq",
                        "form_name": "Agrifieldnet AA Form",
                        "tz_name": "Asia/Kolkata",
                        "scto_server_name": "dod",
                        "encryption_key_shared": True,
                        "server_access_role_granted": True,
                        "server_access_allowed": True,
                        "last_ingested_at": None,
                        "form_type": "dq",
                        "parent_form_uid": 1,
                        "dq_form_type": "audioaudit",
                        "parent_scto_form_id": "test_scto_input_output",
                    }
                ],
                "success": True,
            }

            checkdiff = jsondiff.diff(expected_response, response.json)
            assert checkdiff == {}

        else:
            response.status_code = 403

            expected_response = {
                "success": False,
                "error": f"User does not have the required permission: WRITE Data Quality Forms",
            }
            print(response.json)
            print(expected_response)
            checkdiff = jsondiff.diff(expected_response, response.json)
            assert checkdiff == {}

    def test_create_dq_scto_question_mapping(
        self,
        client,
        csrf_token,
        login_test_user,
        create_dq_form,
        user_with_dq_forms_permissions,
        request,
    ):
        """
        Test that the SCTO question mapping is inserted correctly for a DQ form
        """

        user_fixture, expected_permission = user_with_dq_forms_permissions
        request.getfixturevalue(user_fixture)

        # Insert the SCTO question mapping
        payload = {
            "form_uid": 2,
            "target_id": "test_target_id",
            "enumerator_id": "test_enumerator_id",
            "dq_enumerator_id": "test_dq_enumerator_id",
            "locations": {
                "location_1": "test_location_1",
            },
        }

        response = client.post(
            "/api/forms/2/scto-question-mapping",
            json=payload,
            content_type="application/json",
            headers={"X-CSRF-Token": csrf_token},
        )

        if expected_permission:
            assert response.status_code == 201

            # Test the SCTO question mapping was inserted correctly
            response = client.get("/api/forms/2/scto-question-mapping")
            assert response.status_code == 200

            expected_response = {
                "data": {
                    "form_uid": 2,
                    "survey_status": None,
                    "revisit_section": None,
                    "target_id": "test_target_id",
                    "enumerator_id": "test_enumerator_id",
                    "dq_enumerator_id": "test_dq_enumerator_id",
                    "locations": {
                        "location_1": "test_location_1",
                    },
                },
                "success": True,
            }

            checkdiff = jsondiff.diff(expected_response, response.json)
            assert checkdiff == {}

        else:
            response.status_code = 403

            expected_response = {
                "success": False,
                "error": f"User does not have the required permission: WRITE Data Quality Forms",
            }
            checkdiff = jsondiff.diff(expected_response, response.json)
            assert checkdiff == {}

    def test_create_dq_scto_question_mapping_without_dq_enum_id(
        self, client, csrf_token, login_test_user, create_dq_form
    ):
        """
        Test that create SCTO question mapping returns error if no dq enumerator id is provided
        """

        # Insert the SCTO question mapping
        payload = {
            "form_uid": 2,
            "target_id": "test_target_id",
            "enumerator_id": "test_enumerator_id",
            "locations": {
                "location_1": "test_location_1",
            },
        }

        response = client.post(
            "/api/forms/2/scto-question-mapping",
            json=payload,
            content_type="application/json",
            headers={"X-CSRF-Token": csrf_token},
        )
        assert response.status_code == 422

    def test_update_dq_scto_question_mapping_without_dq_enum_id(
        self, client, csrf_token, login_test_user, create_dq_form
    ):
        """
        Test that update SCTO question mapping returns error if no dq enumerator id is provided
        """

        # Insert the SCTO question mapping
        payload = {
            "form_uid": 2,
            "target_id": "test_target_id",
            "enumerator_id": "test_enumerator_id",
            "locations": {
                "location_1": "test_location_1",
            },
        }

        response = client.put(
            "/api/forms/2/scto-question-mapping",
            json=payload,
            content_type="application/json",
            headers={"X-CSRF-Token": csrf_token},
        )
        assert response.status_code == 422
