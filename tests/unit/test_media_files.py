import jsondiff
import pytest
from datetime import datetime, timedelta
from utils import (
    update_logged_in_user_roles,
    login_user,
    create_new_survey_role_with_permissions,
)


@pytest.mark.media_files
class TestMedaiFiles:
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
    def user_with_media_files_permissions(self, client, test_user_credentials):
        # Assign new roles and permissions
        new_role = create_new_survey_role_with_permissions(
            # 11 - WRITE Media Files Config
            client,
            test_user_credentials,
            "Media Files Role",
            [11],
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
            ("user_with_media_files_permissions", True),
            ("user_with_no_permissions", False),
        ],
        ids=[
            "super_admin_permissions",
            "survey_admin_permissions",
            "media_files_permissions",
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

    @pytest.fixture
    def create_media_files_config(
        self, client, login_test_user, csrf_token, test_user_credentials, create_form
    ):
        """
        Insert an media file config as a setup step for media file tests

        """
        payload = {
            "form_uid": 1,
            "file_type": "audio",
            "source": "SurveyCTO",
            "scto_fields": [
                "SubmissionDate",
                "instanceID",
                "enum_id",
                "district_id",
                "status",
            ],
        }
        response = client.post(
            "/api/media-files",
            json=payload,
            content_type="application/json",
            headers={"X-CSRF-Token": csrf_token},
        )

        assert response.status_code == 201
        return response.json["data"]

    def test_media_files_get_config(
        self,
        client,
        csrf_token,
        create_media_files_config,
        user_permissions,
        request,
    ):
        """
        Test getting a specific media files config, with the different permissions
        Expect the media files config list or permissions denied
        """
        user_fixture, expected_permission = user_permissions
        request.getfixturevalue(user_fixture)

        response = client.get(
            "/api/media-files/1",
            content_type="application/json",
            headers={"X-CSRF-Token": csrf_token},
        )

        if expected_permission:
            assert response.status_code == 200
            expected_response = {
                "data": {
                    "media_files_config_uid": 1,
                    "form_uid": 1,
                    "file_type": "audio",
                    "source": "SurveyCTO",
                    "scto_fields": [
                        "SubmissionDate",
                        "instanceID",
                        "enum_id",
                        "district_id",
                        "status",
                    ],
                    "mapping_criteria": None,
                },
                "success": True,
            }
            checkdiff = jsondiff.diff(expected_response, response.json)
            assert checkdiff == {}
        else:
            assert response.status_code == 403

            expected_response = {
                "error": "User does not have the required permission: READ Media Files Config",
                "success": False,
            }

            checkdiff = jsondiff.diff(expected_response, response.json)
            assert checkdiff == {}

    def test_media_files_get_configs(
        self,
        client,
        csrf_token,
        create_media_files_config,
        user_permissions,
        request,
    ):
        """
        Test getting a specific form media files configs, with the different permissions
        Expect the media files configs list or permissions denied
        """
        user_fixture, expected_permission = user_permissions
        request.getfixturevalue(user_fixture)

        response = client.get(
            "api/media-files?survey_uid=1",
            content_type="application/json",
            headers={"X-CSRF-Token": csrf_token},
        )

        if expected_permission:
            assert response.status_code == 200
            expected_response = {
                "data": [
                    {
                        "media_files_config_uid": 1,
                        "form_uid": 1,
                        "scto_form_id": "test_scto_input_output",
                        "file_type": "audio",
                        "source": "SurveyCTO",
                        "scto_fields": [
                            "SubmissionDate",
                            "instanceID",
                            "enum_id",
                            "district_id",
                            "status",
                        ],
                        "mapping_criteria": None,
                    }
                ],
                "success": True,
            }
            checkdiff = jsondiff.diff(expected_response, response.json)
            assert checkdiff == {}
        else:
            assert response.status_code == 403

            expected_response = {
                "error": "User does not have the required permission: READ Media Files Config",
                "success": False,
            }

            checkdiff = jsondiff.diff(expected_response, response.json)
            assert checkdiff == {}

    def test_media_files_update_config(
        self, client, csrf_token, create_media_files_config, user_permissions, request
    ):
        """
        Test updating media_files config for different roles
        Expect newly created media files config to be updated
        """
        user_fixture, expected_permission = user_permissions
        request.getfixturevalue(user_fixture)

        payload = {
            "file_type": "audio",
            "source": "Exotel",
            "scto_fields": [
                "SubmissionDate",
                "instanceID",
                "enum_id",
                "district_id",
                "status",
            ],
            "mapping_criteria": "location",
        }

        response = client.put(
            f"api/media-files/1",
            json=payload,
            content_type="application/json",
            headers={"X-CSRF-Token": csrf_token},
        )

        if expected_permission:
            assert response.status_code == 200

            get_response = client.get(
                f"api/media-files/1",
                content_type="application/json",
                headers={"X-CSRF-Token": csrf_token},
            )

            assert get_response.status_code == 200

            checkdiff = jsondiff.diff(
                {
                    "data": {
                        "media_files_config_uid": 1,
                        "form_uid": 1,
                        **payload,
                    },
                    "success": True,
                },
                get_response.json,
            )

            assert checkdiff == {}
        else:
            assert response.status_code == 403
            expected_response = {
                "error": "User does not have the required permission: WRITE Media Files Config",
                "success": False,
            }

            checkdiff = jsondiff.diff(expected_response, response.json)
            assert checkdiff == {}

    def test_media_files_delete_config(
        self,
        client,
        csrf_token,
        user_permissions,
        create_media_files_config,
        request,
    ):
        """
        Test deleting media files config for different roles
        Expect config to be missing on fetch
        """
        user_fixture, expected_permission = user_permissions
        request.getfixturevalue(user_fixture)

        response = client.delete(
            "api/media-files/1",
            headers={"X-CSRF-Token": csrf_token},
        )

        if expected_permission:
            assert response.status_code == 200

            expected_response = {
                "data": {"message": "Media files config deleted successfully"},
                "success": True,
            }

            checkdiff = jsondiff.diff(expected_response, response.json)
            assert checkdiff == {}
        else:
            assert response.status_code == 403
            expected_response = {
                "error": "User does not have the required permission: WRITE Media Files Config",
                "success": False,
            }

            checkdiff = jsondiff.diff(expected_response, response.json)
            assert checkdiff == {}
