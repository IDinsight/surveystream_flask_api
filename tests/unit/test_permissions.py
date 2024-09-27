import jsondiff
import pytest


@pytest.mark.permissions
class TestPermissions:
    @pytest.fixture
    def create_permission(self, client, login_test_user, csrf_token):
        """
        Tests if we can create a simple WRITE permissions
        The permission is returned by the fixture for subsequent tests
        """
        data = {"name": "WRITE", "description": "Write permission"}
        response = client.post(
            "/api/permissions",
            json=data,
            content_type="application/json",
            headers={"X-CSRF-Token": csrf_token},
        )
        assert response.status_code == 201
        assert response.json["message"] == "Permission created successfully"

        return {
            "permission_uid": response.json["permission_uid"],
            "name": response.json["name"],
            "description": response.json["description"],
        }

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
    def create_module_selection(
        self, client, login_test_user, csrf_token, test_user_credentials, create_survey
    ):
        """
        Insert new module_selection as a setup step for the module_selection tests
        """

        payload = {
            "survey_uid": 1,
            "modules": ["1", "2", "3", "4", "5", "6", "7", "8", "13", "14", "18"],
        }

        response = client.post(
            "/api/module-status",
            json=payload,
            content_type="application/json",
            headers={"X-CSRF-Token": csrf_token},
        )
        assert response.status_code == 200

        yield

    def test_default_data_available(self, client, login_test_user, csrf_token):
        """
        Tests fetch permissions is working, this tests also expects that permissions are
        already seeded to the database by the migrations
        """
        response = client.get(
            "/api/permissions",
            content_type="application/json",
            headers={"X-CSRF-Token": csrf_token},
        )
        assert response.status_code == 200
        # Ensure the default permission is present in the response
        response_data = response.json
        expected_data = [
            {"description": "Admin permission", "name": "ADMIN", "permission_uid": 1},
            {
                "description": "Read Survey Locations permission",
                "name": "READ Survey Locations",
                "permission_uid": 2,
            },
            {
                "description": "Write Survey Locations permission",
                "name": "WRITE Survey Locations",
                "permission_uid": 3,
            },
            {
                "description": "Read Enumerators permission",
                "name": "READ Enumerators",
                "permission_uid": 4,
            },
            {
                "description": "Write Enumerators permission",
                "name": "WRITE Enumerators",
                "permission_uid": 5,
            },
            {
                "description": "Read Targets permission",
                "name": "READ Targets",
                "permission_uid": 6,
            },
            {
                "description": "Write Targets permission",
                "name": "WRITE Targets",
                "permission_uid": 7,
            },
            {
                "description": "Read Assignments permission",
                "name": "READ Assignments",
                "permission_uid": 8,
            },
            {
                "description": "Write Assignments permission",
                "name": "WRITE Assignments",
                "permission_uid": 9,
            },
            {
                "description": "Read Media Files Config permission",
                "name": "READ Media Files Config",
                "permission_uid": 10,
            },
            {
                "description": "Write Media Files Config permission",
                "name": "WRITE Media Files Config",
                "permission_uid": 11,
            },
            {
                "description": "Read Media Files permission",
                "name": "READ Media Files",
                "permission_uid": 12,
            },
            {
                "description": "Write Media Files permission",
                "name": "WRITE Media Files",
                "permission_uid": 13,
            },
            {
                "description": "Read Productivity permission",
                "name": "READ Productivity",
                "permission_uid": 14,
            },
            {
                "description": "Write Productivity permission",
                "name": "WRITE Productivity",
                "permission_uid": 15,
            },
            {
                "description": "Read Data Quality permission",
                "name": "READ Data Quality",
                "permission_uid": 16,
            },
            {
                "description": "Write Data Quality permission",
                "name": "WRITE Data Quality",
                "permission_uid": 17,
            },
            {
                "description": "Read Emails permission",
                "name": "READ Emails",
                "permission_uid": 18,
            },
            {
                "description": "Write Emails permission",
                "name": "WRITE Emails",
                "permission_uid": 19,
            },
            {
                "description": "Read Target Status Mapping permission",
                "name": "READ Target Status Mapping",
                "permission_uid": 20,
            },
            {
                "description": "Write Target Status Mapping permission",
                "name": "WRITE Target Status Mapping",
                "permission_uid": 21,
            },
            {
                "description": "Read Data Quality Forms permission",
                "name": "READ Data Quality Forms",
                "permission_uid": 22,
            },
            {
                "description": "Write Data Quality Forms permission",
                "name": "WRITE Data Quality Forms",
                "permission_uid": 23,
            },
            {
                "description": "Write Assignments Upload permission",
                "name": "WRITE Assignments Upload",
                "permission_uid": 24,
            },
            {
                "description": "Read Assignments Upload permission",
                "name": "READ Assignments Upload",
                "permission_uid": 25,
            },
            {
                "description": "Read Mapping permission",
                "name": "READ Mapping",
                "permission_uid": 26,
            },
            {
                "description": "Write Mapping permission",
                "name": "WRITE Mapping",
                "permission_uid": 27,
            },
            {
                "description": "Read Admin Forms permission",
                "name": "READ Admin Forms",
                "permission_uid": 28,
            },
            {
                "description": "Write Admin Forms permission",
                "name": "WRITE Admin Forms",
                "permission_uid": 29,
            },
        ]

        assert jsondiff.diff(expected_data, response_data) == {}

    def test_create_permission(
        self, client, login_test_user, csrf_token, create_permission
    ):
        """
        Test the create_permission fixture is working
        Using a fetch test confirm that both the default data and the new created permission are both available
        """
        response = client.get(
            "/api/permissions",
            content_type="application/json",
            headers={"X-CSRF-Token": csrf_token},
        )
        assert response.status_code == 200

        response_data = response.json
        expected_data = [
            {"description": "Admin permission", "name": "ADMIN", "permission_uid": 1},
            {
                "description": "Read Survey Locations permission",
                "name": "READ Survey Locations",
                "permission_uid": 2,
            },
            {
                "description": "Write Survey Locations permission",
                "name": "WRITE Survey Locations",
                "permission_uid": 3,
            },
            {
                "description": "Read Enumerators permission",
                "name": "READ Enumerators",
                "permission_uid": 4,
            },
            {
                "description": "Write Enumerators permission",
                "name": "WRITE Enumerators",
                "permission_uid": 5,
            },
            {
                "description": "Read Targets permission",
                "name": "READ Targets",
                "permission_uid": 6,
            },
            {
                "description": "Write Targets permission",
                "name": "WRITE Targets",
                "permission_uid": 7,
            },
            {
                "description": "Read Assignments permission",
                "name": "READ Assignments",
                "permission_uid": 8,
            },
            {
                "description": "Write Assignments permission",
                "name": "WRITE Assignments",
                "permission_uid": 9,
            },
            {
                "description": "Read Media Files Config permission",
                "name": "READ Media Files Config",
                "permission_uid": 10,
            },
            {
                "description": "Write Media Files Config permission",
                "name": "WRITE Media Files Config",
                "permission_uid": 11,
            },
            {
                "description": "Read Media Files permission",
                "name": "READ Media Files",
                "permission_uid": 12,
            },
            {
                "description": "Write Media Files permission",
                "name": "WRITE Media Files",
                "permission_uid": 13,
            },
            {
                "description": "Read Productivity permission",
                "name": "READ Productivity",
                "permission_uid": 14,
            },
            {
                "description": "Write Productivity permission",
                "name": "WRITE Productivity",
                "permission_uid": 15,
            },
            {
                "description": "Read Data Quality permission",
                "name": "READ Data Quality",
                "permission_uid": 16,
            },
            {
                "description": "Write Data Quality permission",
                "name": "WRITE Data Quality",
                "permission_uid": 17,
            },
            {
                "description": "Read Emails permission",
                "name": "READ Emails",
                "permission_uid": 18,
            },
            {
                "description": "Write Emails permission",
                "name": "WRITE Emails",
                "permission_uid": 19,
            },
            {
                "description": "Read Target Status Mapping permission",
                "name": "READ Target Status Mapping",
                "permission_uid": 20,
            },
            {
                "description": "Write Target Status Mapping permission",
                "name": "WRITE Target Status Mapping",
                "permission_uid": 21,
            },
            {
                "description": "Read Data Quality Forms permission",
                "name": "READ Data Quality Forms",
                "permission_uid": 22,
            },
            {
                "description": "Write Data Quality Forms permission",
                "name": "WRITE Data Quality Forms",
                "permission_uid": 23,
            },
            {
                "description": "Write Assignments Upload permission",
                "name": "WRITE Assignments Upload",
                "permission_uid": 24,
            },
            {
                "description": "Read Assignments Upload permission",
                "name": "READ Assignments Upload",
                "permission_uid": 25,
            },
            {
                "description": "Read Mapping permission",
                "name": "READ Mapping",
                "permission_uid": 26,
            },
            {
                "description": "Write Mapping permission",
                "name": "WRITE Mapping",
                "permission_uid": 27,
            },
            {
                "description": "Read Admin Forms permission",
                "name": "READ Admin Forms",
                "permission_uid": 28,
            },
            {
                "description": "Write Admin Forms permission",
                "name": "WRITE Admin Forms",
                "permission_uid": 29,
            },
            {
                "permission_uid": create_permission["permission_uid"],
                "name": create_permission["name"],
                "description": create_permission["description"],
            },
        ]

        assert jsondiff.diff(expected_data, response_data) == {}

    def test_get_permission(
        self, client, login_test_user, csrf_token, create_permission
    ):
        """
        Test single permissions fetch
        Expect data similar to create_permission data
        """
        response = client.get(
            f"/api/permissions/{create_permission['permission_uid']}",
            content_type="application/json",
            headers={"X-CSRF-Token": csrf_token},
        )
        assert response.status_code == 200
        assert response.json == {
            "permission_uid": create_permission["permission_uid"],
            "name": create_permission["name"],
            "description": create_permission["description"],
        }

    def test_update_permission(
        self, client, login_test_user, csrf_token, create_permission
    ):
        """
        Test permissions update endpoint
        Expect data from create_permission to change to new data provided
        """
        permission_id = create_permission["permission_uid"]
        data = {"name": "UPDATED", "description": "Updated permission"}
        response = client.put(
            f"/api/permissions/{permission_id}",
            json=data,
            content_type="application/json",
            headers={"X-CSRF-Token": csrf_token},
        )
        assert response.status_code == 200
        assert response.json["message"] == "Permission updated successfully"

        # Verify the permission is updated in the database
        update_response = client.get(
            f"/api/permissions/{permission_id}",
            content_type="application/json",
            headers={"X-CSRF-Token": csrf_token},
        )
        assert update_response.status_code == 200
        assert update_response.json == {
            "permission_uid": permission_id,
            "name": "UPDATED",
            "description": "Updated permission",
        }

    def test_delete_permission(
        self, client, login_test_user, csrf_token, create_permission
    ):
        """
        Test permissions delete endpoint
        Expect data from create_permission to be deleted
        """
        permission_id = create_permission["permission_uid"]
        response = client.delete(
            f"/api/permissions/{permission_id}",
            content_type="application/json",
            headers={"X-CSRF-Token": csrf_token},
        )
        assert response.status_code == 200
        assert response.json["message"] == "Permission deleted successfully"

        # Verify the permission is deleted from the database
        delete_response = client.get(
            f"/api/permissions/{permission_id}",
            content_type="application/json",
            headers={"X-CSRF-Token": csrf_token},
        )
        assert delete_response.status_code == 404

    def test_get_survey_permissions(
        self, client, login_test_user, csrf_token, create_module_selection
    ):
        """
        Test permissions fetch for a survey
        Expect only permissions that are associated with the survey as per
        modules selected to be returned
        """
        response = client.get(
            "api/permissions?survey_uid=1",
            content_type="application/json",
            headers={"X-CSRF-Token": csrf_token},
        )
        assert response.status_code == 200

        response_data = response.json
        expected_data = [
            {"description": "Admin permission", "name": "ADMIN", "permission_uid": 1},
            {
                "description": "Read Survey Locations permission",
                "name": "READ Survey Locations",
                "permission_uid": 2,
            },
            {
                "description": "Write Survey Locations permission",
                "name": "WRITE Survey Locations",
                "permission_uid": 3,
            },
            {
                "description": "Read Enumerators permission",
                "name": "READ Enumerators",
                "permission_uid": 4,
            },
            {
                "description": "Write Enumerators permission",
                "name": "WRITE Enumerators",
                "permission_uid": 5,
            },
            {
                "description": "Read Targets permission",
                "name": "READ Targets",
                "permission_uid": 6,
            },
            {
                "description": "Write Targets permission",
                "name": "WRITE Targets",
                "permission_uid": 7,
            },
            {
                "description": "Read Target Status Mapping permission",
                "name": "READ Target Status Mapping",
                "permission_uid": 20,
            },
            {
                "description": "Write Target Status Mapping permission",
                "name": "WRITE Target Status Mapping",
                "permission_uid": 21,
            },
            {
                "description": "Read Admin Forms permission",
                "name": "READ Admin Forms",
                "permission_uid": 28,
            },
            {
                "description": "Write Admin Forms permission",
                "name": "WRITE Admin Forms",
                "permission_uid": 29,
            },
        ]
        print(response_data)
        assert jsondiff.diff(expected_data, response_data) == {}
