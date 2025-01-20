import jsondiff
import pytest
from utils import (
    create_new_survey_role_with_permissions,
    login_user,
    update_logged_in_user_roles,
)


@pytest.mark.notifications
class TestNotifications:
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
        update_logged_in_user_roles(
            client,
            test_user_credentials,
            is_survey_admin=False,
            survey_uid=2,
            is_super_admin=False,
            roles=[],
        )
        login_user(client, test_user_credentials)

    @pytest.fixture
    def user_with_assignments_permissions(self, client, test_user_credentials):
        # Assign new roles and permissions
        new_role = create_new_survey_role_with_permissions(
            client,
            test_user_credentials,
            "Assignments Role",
            [9],
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
            survey_uid=2,
            is_super_admin=False,
            roles=[],
        )
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
            ("user_with_assignments_permissions", True),
            ("user_with_no_permissions", False),
        ],
        ids=[
            "super_admin_permissions",
            "survey_admin_permissions",
            "assignment_permissions",
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
    def create_second_survey(
        self, client, login_test_user, csrf_token, test_user_credentials, create_survey
    ):
        """
        Insert new survey as a setup step for the form tests
        """

        payload = {
            "survey_id": "test_survey2",
            "survey_name": "Test Survey2",
            "survey_description": "A test survey",
            "project_name": "Test Project",
            "surveying_method": "in-person",
            "irb_approval": "Yes",
            "planned_start_date": "2021-01-01",
            "planned_end_date": "2021-12-31",
            "state": "Draft",
            "config_status": "In Progress - Configuration",
            "created_by_user_uid": 1,
        }

        response = client.post(
            "/api/surveys",
            query_string={"user_uid": 1},
            json=payload,
            content_type="application/json",
            headers={"X-CSRF-Token": csrf_token},
        )
        assert response.status_code == 201

        yield

    @pytest.fixture()
    def update_module_selection(
        self, client, login_test_user, csrf_token, test_user_credentials, create_survey
    ):
        """
        Update new module_selection as a setup step for the module_selection tests
        """

        payload = {
            "survey_uid": 1,
            "modules": ["1", "2", "3", "4", "5", "6", "7", "8", "9", "13", "14"],
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
    def create_module_questionnaire(
        self,
        client,
        login_test_user,
        csrf_token,
        test_user_credentials,
        create_survey,
        update_module_selection,
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
    def create_survey_notification(
        self, client, login_test_user, csrf_token, create_form
    ):
        """
        Create Survey Notification
        """

        payload = {
            "survey_uid": 1,
            "module_id": 1,
            "resolution_status": "in progress",
            "message": "Your survey end date is approaching",
            "severity": "warning",
            "type": "survey",
        }
        response = client.post(
            "/api/notifications",
            json=payload,
            content_type="application/json",
            headers={"X-CSRF-Token": csrf_token},
        )
        print(response.json)
        assert response.status_code == 200

        yield

    @pytest.fixture()
    def create_survey_notification_for_assignments(
        self, client, login_test_user, csrf_token, create_survey_notification
    ):
        """
        Create Survey Notification
        """

        payload = {
            "survey_uid": 1,
            "module_id": 9,
            "resolution_status": "in progress",
            "message": "No user mappings found",
            "severity": "error",
            "type": "survey",
        }
        response = client.post(
            "/api/notifications",
            json=payload,
            content_type="application/json",
            headers={"X-CSRF-Token": csrf_token},
        )
        print(response.json)
        assert response.status_code == 200

        yield

    @pytest.fixture()
    def create_second_survey_notification_for_assignments(
        self,
        client,
        login_test_user,
        csrf_token,
        create_survey_notification_for_assignments,
        create_second_survey,
    ):
        """
        Create Survey Notification
        """

        payload = {
            "survey_uid": 2,
            "module_id": 9,
            "resolution_status": "in progress",
            "message": "No user mappings found",
            "severity": "error",
            "type": "survey",
        }
        response = client.post(
            "/api/notifications",
            json=payload,
            content_type="application/json",
            headers={"X-CSRF-Token": csrf_token},
        )
        print(response.json)
        assert response.status_code == 200

        yield

    @pytest.fixture()
    def create_second_survey_notification_for_DQ(
        self,
        client,
        login_test_user,
        csrf_token,
        create_second_survey_notification_for_assignments,
        create_second_survey,
    ):
        """
        Create Survey Notification
        """

        payload = {
            "survey_uid": 2,
            "module_id": 11,
            "resolution_status": "in progress",
            "message": "DQ: Survey status variable missing",
            "severity": "error",
            "type": "survey",
        }
        response = client.post(
            "/api/notifications",
            json=payload,
            content_type="application/json",
            headers={"X-CSRF-Token": csrf_token},
        )
        print(response.json)
        assert response.status_code == 200

        yield

    @pytest.fixture()
    def create_user_notification(
        self, client, login_test_user, csrf_token, create_form
    ):
        """
        Create User Notifications
        """

        payload = {
            "user_uid": 1,
            "resolution_status": "in progress",
            "message": "Your password has been reset",
            "severity": "alert",
            "type": "user",
        }

        # add a delay to ensure the notification is created after the survey notification
        response = client.post(
            "/api/notifications",
            json=payload,
            content_type="application/json",
            headers={"X-CSRF-Token": csrf_token},
        )
        print(response.json)
        assert response.status_code == 200

        yield

    def test_notifications_create_user_notifications(
        self,
        client,
        login_test_user,
        create_form,
        csrf_token,
    ):
        payload = {
            "user_uid": 1,
            "resolution_status": "in progress",
            "message": "End date reached",
            "severity": "alert",
            "type": "user",
        }
        response = client.post(
            "/api/notifications",
            json=payload,
            content_type="application/json",
            headers={"X-CSRF-Token": csrf_token},
        )

        print(response.json)
        assert response.status_code == 200
        expected_response = {
            "success": True,
            "message": "Notification created successfully",
            "data": {
                "notification_uid": 1,
                "severity": "alert",
                "resolution_status": "in progress",
                "message": "End date reached",
            },
        }

        response_json = response.json
        # Remove the created_at from the response for comparison
        if "data" in response_json and "created_at" in response_json["data"]:
            del response_json["data"]["created_at"]

        checkdiff = jsondiff.diff(expected_response, response_json)
        assert checkdiff == {}

    def test_notifications_create_user_notifications_user_not_found(
        self,
        client,
        login_test_user,
        create_form,
        csrf_token,
    ):
        payload = {
            "user_uid": 1717166,
            "resolution_status": "in progress",
            "message": "Password changed",
            "severity": "alert",
            "type": "user",
        }
        response = client.post(
            "/api/notifications",
            json=payload,
            content_type="application/json",
            headers={"X-CSRF-Token": csrf_token},
        )

        print(response.json)
        assert response.status_code == 404
        expected_response = {"error": "User not found", "success": False}

        checkdiff = jsondiff.diff(expected_response, response.json)
        assert checkdiff == {}

    def test_notifications_create_user_notifications_with_error(
        self,
        client,
        login_test_user,
        create_form,
        csrf_token,
    ):
        payload = {
            "user_uid": 1,
            "resolution_status": "in progressss",
            "severity": "alerttt",
        }
        response = client.post(
            "/api/notifications",
            json=payload,
            content_type="application/json",
            headers={"X-CSRF-Token": csrf_token},
        )

        print(response.json)
        assert response.status_code == 422
        expected_response = {
            "message": {
                "severity": [
                    "Invalid Notification severity, valid values are alert, warning, error"
                ],
                "resolution_status": [
                    "Invalid Resolution Status valid values are in progress, done"
                ],
                "message": ["This field is required."],
                "type": ["This field is required."],
            },
            "success": False,
        }

        checkdiff = jsondiff.diff(expected_response, response.json)
        assert checkdiff == {}

    def test_notifications_create_notification_error_no_survey_or_user(
        self,
        client,
        login_test_user,
        create_form,
        csrf_token,
    ):
        payload = {
            "resolution_status": "in progress",
            "message": "End date reached",
            "severity": "alert",
        }
        response = client.post(
            "/api/notifications",
            json=payload,
            content_type="application/json",
            headers={"X-CSRF-Token": csrf_token},
        )

        print(response.json)
        assert response.status_code == 422
        expected_response = {
            "message": {
                "type": ["This field is required."],
            },
            "success": False,
        }

        checkdiff = jsondiff.diff(expected_response, response.json)
        assert checkdiff == {}

    def test_notifications_create_survey_notifications(
        self,
        client,
        login_test_user,
        create_survey_notification,
        csrf_token,
    ):
        payload = {
            "survey_uid": 1,
            "module_id": 4,
            "resolution_status": "in progress",
            "message": "End date reached",
            "severity": "error",
            "type": "survey",
        }
        response = client.post(
            "/api/notifications",
            json=payload,
            content_type="application/json",
            headers={"X-CSRF-Token": csrf_token},
        )

        print(response.json)
        assert response.status_code == 200
        expected_response = {
            "success": True,
            "message": "Notification created successfully",
            "data": {
                "notification_uid": 2,
                "severity": "error",
                "resolution_status": "in progress",
                "message": "End date reached",
            },
        }

        response_json = response.json
        # Remove the created_at from the response for comparison
        if "data" in response_json and "created_at" in response_json["data"]:
            del response_json["data"]["created_at"]

        checkdiff = jsondiff.diff(expected_response, response_json)
        assert checkdiff == {}

        get_module_response = client.get(
            "/api/module-status/1",
            content_type="application/json",
            headers={"X-CSRF-Token": csrf_token},
        )
        print(get_module_response.json)

        expected_response = {
            "success": True,
            "data": [
                {"survey_uid": 1, "module_id": 1, "config_status": "In Progress"},
                {"survey_uid": 1, "module_id": 2, "config_status": "Not Started"},
                {"survey_uid": 1, "module_id": 3, "config_status": "Not Started"},
                {"survey_uid": 1, "module_id": 4, "config_status": "Error"},
                {"survey_uid": 1, "module_id": 5, "config_status": "Not Started"},
                {"survey_uid": 1, "module_id": 6, "config_status": "Not Started"},
                {"survey_uid": 1, "module_id": 7, "config_status": "Not Started"},
                {"survey_uid": 1, "module_id": 8, "config_status": "Not Started"},
                {"survey_uid": 1, "module_id": 9, "config_status": "Not Started"},
                {"survey_uid": 1, "module_id": 13, "config_status": "Not Started"},
                {"survey_uid": 1, "module_id": 14, "config_status": "Not Started"},
            ],
        }

        assert get_module_response.json == expected_response

    def test_notifications_create_survey_notifications_error_no_survey(
        self,
        client,
        login_test_user,
        create_form,
        csrf_token,
    ):
        payload = {
            "survey_uid": 1234563634356789045677,
            "module_id": 4,
            "resolution_status": "in progress",
            "message": "End date reached",
            "severity": "alert",
            "type": "survey",
        }
        response = client.post(
            "/api/notifications",
            json=payload,
            content_type="application/json",
            headers={"X-CSRF-Token": csrf_token},
        )

        print(response.json)
        assert response.status_code == 404
        expected_response = {"error": "Survey not found", "success": False}

        checkdiff = jsondiff.diff(expected_response, response.json)
        assert checkdiff == {}

    def test_notifications_create_survey_notifications_error_no_module(
        self,
        client,
        login_test_user,
        create_form,
        csrf_token,
    ):
        payload = {
            "survey_uid": 1,
            "module_id": 4123450,
            "resolution_status": "in progress",
            "message": "End date reached",
            "severity": "alert",
            "type": "survey",
        }
        response = client.post(
            "/api/notifications",
            json=payload,
            content_type="application/json",
            headers={"X-CSRF-Token": csrf_token},
        )

        print(response.json)
        assert response.status_code == 404
        expected_response = {"error": "Module not found", "success": False}

        checkdiff = jsondiff.diff(expected_response, response.json)
        assert checkdiff == {}

    def test_notifications_get_user_notifications_blank_notifications(
        self,
        client,
        login_test_user,
        create_form,
        csrf_token,
    ):

        response = client.get(
            "/api/notifications",
            content_type="application/json",
            headers={"X-CSRF-Token": csrf_token},
        )

        print(response.json)
        assert response.status_code == 200
        expected_response = {
            "success": True,
            "data": [],
        }

        checkdiff = jsondiff.diff(expected_response, response.json)
        assert checkdiff == {}

    def test_notifications_get_user_notifications_all_notifications(
        self,
        client,
        create_user_notification,
        create_second_survey_notification_for_DQ,
        csrf_token,
        user_permissions,
        request,
    ):
        """
        TEST Get user notifications based on multiple roles
        Expect:
            Super Admin: All notifications
            Survey Admin: Only 1st survey's notification
            No permission: Only user notification
            Assignment Role user :
                1st Survey Assignment Notifications
                2nd Survey Admin - All notifications
                User notifications
        """
        user_fixture, expected_permission = user_permissions
        request.getfixturevalue(user_fixture)

        response = client.get(
            "/api/notifications",
            content_type="application/json",
            headers={"X-CSRF-Token": csrf_token},
        )

        print(response.json)
        assert response.status_code == 200
        if user_fixture == "user_with_super_admin_permissions":
            expected_response = {
                "success": True,
                "data": [
                    {
                        "survey_id": "test_survey2",
                        "survey_uid": 2,
                        "module_name": "Data quality",
                        "module_id": 11,
                        "notification_uid": 4,
                        "severity": "error",
                        "resolution_status": "in progress",
                        "message": "DQ: Survey status variable missing",
                        "type": "survey",
                    },
                    {
                        "survey_id": "test_survey2",
                        "survey_uid": 2,
                        "module_name": "Assignments",
                        "module_id": 9,
                        "notification_uid": 3,
                        "severity": "error",
                        "resolution_status": "in progress",
                        "message": "No user mappings found",
                        "type": "survey",
                    },
                    {
                        "survey_id": "test_survey",
                        "survey_uid": 1,
                        "module_name": "Assignments",
                        "module_id": 9,
                        "notification_uid": 2,
                        "severity": "error",
                        "resolution_status": "in progress",
                        "message": "No user mappings found",
                        "type": "survey",
                    },
                    {
                        "survey_id": "test_survey",
                        "survey_uid": 1,
                        "module_name": "Basic information",
                        "module_id": 1,
                        "notification_uid": 1,
                        "severity": "warning",
                        "resolution_status": "in progress",
                        "message": "Your survey end date is approaching",
                        "type": "survey",
                    },
                    {
                        "type": "user",
                        "notification_uid": 1,
                        "severity": "alert",
                        "resolution_status": "in progress",
                        "message": "Your password has been reset",
                    },
                ],
            }
        elif user_fixture == "user_with_survey_admin_permissions":
            expected_response = {
                "success": True,
                "data": [
                    {
                        "survey_id": "test_survey",
                        "survey_uid": 1,
                        "module_name": "Assignments",
                        "module_id": 9,
                        "notification_uid": 2,
                        "severity": "error",
                        "resolution_status": "in progress",
                        "message": "No user mappings found",
                        "type": "survey",
                    },
                    {
                        "survey_id": "test_survey",
                        "survey_uid": 1,
                        "module_name": "Basic information",
                        "module_id": 1,
                        "notification_uid": 1,
                        "severity": "warning",
                        "resolution_status": "in progress",
                        "message": "Your survey end date is approaching",
                        "type": "survey",
                    },
                    {
                        "type": "user",
                        "notification_uid": 1,
                        "severity": "alert",
                        "resolution_status": "in progress",
                        "message": "Your password has been reset",
                    },
                ],
            }
        elif user_fixture == "user_with_assignments_permissions":

            expected_response = {
                "success": True,
                "data": [
                    {
                        "survey_id": "test_survey2",
                        "survey_uid": 2,
                        "module_name": "Data quality",
                        "module_id": 11,
                        "notification_uid": 4,
                        "severity": "error",
                        "resolution_status": "in progress",
                        "message": "DQ: Survey status variable missing",
                        "type": "survey",
                    },
                    {
                        "survey_id": "test_survey2",
                        "survey_uid": 2,
                        "module_name": "Assignments",
                        "module_id": 9,
                        "notification_uid": 3,
                        "severity": "error",
                        "resolution_status": "in progress",
                        "message": "No user mappings found",
                        "type": "survey",
                    },
                    {
                        "survey_id": "test_survey",
                        "survey_uid": 1,
                        "module_name": "Assignments",
                        "module_id": 9,
                        "notification_uid": 2,
                        "severity": "error",
                        "resolution_status": "in progress",
                        "message": "No user mappings found",
                        "type": "survey",
                    },
                    {
                        "type": "user",
                        "notification_uid": 1,
                        "severity": "alert",
                        "resolution_status": "in progress",
                        "message": "Your password has been reset",
                    },
                ],
            }
        else:
            expected_response = {
                "success": True,
                "data": [
                    {
                        "notification_uid": 1,
                        "severity": "alert",
                        "resolution_status": "in progress",
                        "message": "Your password has been reset",
                        "type": "user",
                    }
                ],
            }
        response_json = response.json

        # Remove the created_at from the response for comparison
        for notification in response_json.get("data", []):
            if "created_at" in notification:
                del notification["created_at"]
            else:
                print("Created_at missing in notification", notification)
                assert False

        checkdiff = jsondiff.diff(expected_response, response_json)
        assert checkdiff == {}

    def test_notifications_update_user_notification(
        self,
        client,
        login_test_user,
        create_user_notification,
        csrf_token,
    ):

        payload = {
            "type": "user",
            "notification_uid": 1,
            "resolution_status": "done",
            "message": "Your password has been reset",
            "severity": "alert",
        }
        response = client.put(
            "/api/notifications",
            json=payload,
            content_type="application/json",
            headers={"X-CSRF-Token": csrf_token},
        )
        print(response.json)
        assert response.status_code == 200

        expected_response = {
            "success": True,
            "message": "Notification updated successfully",
            "data": {
                "notification_uid": 1,
                "severity": "alert",
                "resolution_status": "done",
                "message": "Your password has been reset",
            },
        }

        response_json = response.json

        # Remove the created_at from the response for comparison
        if "data" in response_json and "created_at" in response_json["data"]:
            del response_json["data"]["created_at"]

        checkdiff = jsondiff.diff(expected_response, response_json)
        assert checkdiff == {}

    def test_notifications_update_survey_notification(
        self,
        client,
        login_test_user,
        create_survey_notification,
        csrf_token,
    ):

        payload = {
            "type": "survey",
            "notification_uid": 1,
            "severity": "alert",
            "resolution_status": "done",
            "message": "Your survey ended yesterday",
        }

        response = client.put(
            "/api/notifications",
            json=payload,
            content_type="application/json",
            headers={"X-CSRF-Token": csrf_token},
        )
        print(response.json)
        assert response.status_code == 200

        expected_response = {
            "success": True,
            "message": "Notification updated successfully",
            "data": {
                "notification_uid": 1,
                "severity": "alert",
                "resolution_status": "done",
                "message": "Your survey ended yesterday",
            },
        }

        response_json = response.json

        # Remove the created_at from the response for comparison
        if "data" in response_json and "created_at" in response_json["data"]:
            del response_json["data"]["created_at"]

        checkdiff = jsondiff.diff(expected_response, response_json)
        assert checkdiff == {}

    def test_notifications_update_survey_notification_error_no_notification_exists(
        self,
        client,
        login_test_user,
        create_user_notification,
        csrf_token,
    ):

        payload = {
            "type": "survey",
            "notification_uid": 1,
            "severity": "alert",
            "resolution_status": "done",
            "message": "Your survey ended yesterday",
        }

        response = client.put(
            "/api/notifications",
            json=payload,
            content_type="application/json",
            headers={"X-CSRF-Token": csrf_token},
        )
        print(response.json)
        assert response.status_code == 404

        expected_response = {"error": "Notification not found", "success": False}

        checkdiff = jsondiff.diff(expected_response, response.json)
        assert checkdiff == {}

    def test_notifications_update_notification_error_no_notification_uid(
        self,
        client,
        login_test_user,
        create_user_notification,
        csrf_token,
    ):

        payload = {
            "type": "survey",
            "severity": "alert",
            "resolution_status": "done",
            "message": "Your survey ended yesterday",
        }
        response = client.put(
            "/api/notifications",
            json=payload,
            content_type="application/json",
            headers={"X-CSRF-Token": csrf_token},
        )
        print(response.json)
        assert response.status_code == 422
        expected_response = {
            "message": {"notification_uid": ["This field is required."]},
            "success": False,
        }

        checkdiff = jsondiff.diff(expected_response, response.json)
        assert checkdiff == {}

    def test_notifications_resolve_notification(
        self,
        client,
        login_test_user,
        create_survey_notification_for_assignments,
        csrf_token,
    ):
        payload = {
            "survey_uid": 1,
            "module_id": 9,
            "resolution_status": "done",
        }
        response = client.patch(
            "/api/notifications",
            json=payload,
            content_type="application/json",
            headers={"X-CSRF-Token": csrf_token},
        )
        print(response.json)
        assert response.status_code == 200

        get_response = client.get(
            "/api/notifications",
            content_type="application/json",
            headers={"X-CSRF-Token": csrf_token},
        )
        assert get_response.status_code == 200

        print(get_response.json)

        expected_response = {
            "success": True,
            "data": [
                {
                    "survey_id": "test_survey",
                    "survey_uid": 1,
                    "module_name": "Assignments",
                    "module_id": 9,
                    "type": "survey",
                    "notification_uid": 2,
                    "severity": "error",
                    "resolution_status": "done",
                    "message": "No user mappings found",
                },
                {
                    "survey_id": "test_survey",
                    "survey_uid": 1,
                    "module_name": "Basic information",
                    "module_id": 1,
                    "type": "survey",
                    "notification_uid": 1,
                    "severity": "warning",
                    "resolution_status": "in progress",
                    "message": "Your survey end date is approaching",
                },
            ],
        }

        response_json = get_response.json

        # Remove the created_at from the response for comparison
        for notification in response_json.get("data", []):
            if "created_at" in notification:
                del notification["created_at"]
            else:
                print("Created_at missing in notification", notification)
                assert False

        checkdiff = jsondiff.diff(expected_response, response_json)
        assert checkdiff == {}

        get_module_response = client.get(
            "/api/module-status/1",
            content_type="application/json",
            headers={"X-CSRF-Token": csrf_token},
        )
        print(get_module_response.json)

        assert get_module_response.status_code == 200

        expected_get_module_response = {
            "success": True,
            "data": [
                {"survey_uid": 1, "module_id": 1, "config_status": "In Progress"},
                {"survey_uid": 1, "module_id": 2, "config_status": "Not Started"},
                {"survey_uid": 1, "module_id": 3, "config_status": "Not Started"},
                {"survey_uid": 1, "module_id": 4, "config_status": "Not Started"},
                {"survey_uid": 1, "module_id": 5, "config_status": "Not Started"},
                {"survey_uid": 1, "module_id": 6, "config_status": "Not Started"},
                {"survey_uid": 1, "module_id": 7, "config_status": "Not Started"},
                {"survey_uid": 1, "module_id": 8, "config_status": "Not Started"},
                {"survey_uid": 1, "module_id": 9, "config_status": "Done"},
                {"survey_uid": 1, "module_id": 13, "config_status": "Not Started"},
                {"survey_uid": 1, "module_id": 14, "config_status": "Not Started"},
            ],
        }
        checkdiff = jsondiff.diff(
            get_module_response.json, expected_get_module_response
        )

        assert checkdiff == {}
