import pytest
import json
import jsondiff

@pytest.mark.user_hierarchy
class TestUserHierarchy:
    @pytest.fixture
    def created_users(self, client, login_test_user, csrf_token):
        users = []
        for i in range(3):  # Create three users for testing
            response = client.post(
                "/api/users",
                json={
                    "email": f"newuser{i + 1}@example.com",
                    "first_name": f"John{i + 1}",
                    "last_name": f"Doe{i + 1}",
                    "roles": [],
                },
                content_type="application/json",
                headers={"X-CSRF-Token": csrf_token}
            )

            assert response.status_code == 200
            assert b"Success: user invited" in response.data
            response_data = json.loads(response.data)
            user_object = response_data.get("user")
            invite_object = response_data.get("invite")
            users.append({"user": user_object, "invite": invite_object})

        print("users")
        print(users)
        return users

    # Fixture to create a survey
    @pytest.fixture()
    def create_survey(self, client, login_test_user, csrf_token):
        """
        Insert new survey as a setup step for the survey tests
        """
        payload = {
            "survey_id": "test_survey",
            "survey_name": "Test Survey",
            "survey_description": "A test survey",
            "project_name": "Test Project",
            "surveying_method": "mixed-mode",
            "irb_approval": "Yes",
            "planned_start_date": "2021-01-01",
            "planned_end_date": "2021-12-31",
            "state": "Draft",
            "config_status": "In Progress - Configuration",
        }

        response = client.post(
            "/api/surveys",
            query_string={"user_uid": 3},
            json=payload,
            content_type="application/json",
            headers={"X-CSRF-Token": csrf_token},
        )

        print("surveys")
        print(response.json)

        assert response.status_code == 201
        return response.json

    # Fixture to create a role
    @pytest.fixture()
    def create_roles(self, client, login_test_user, csrf_token, create_survey):
        """
        Insert new roles as a setup step for the roles tests
        """
        survey_uid = create_survey.get('data', {}).get('survey', {}).get('survey_uid', None)

        print("survey_uid")
        print(survey_uid)

        payload = {
            "roles": [
                {
                    "role_uid": None,
                    "role_name": "Core User",
                    "reporting_role_uid": None,
                    "permissions": []
                },
                {
                    "role_uid": None,
                    "role_name": "Regional Coordinator",
                    "reporting_role_uid": 1,
                    "permissions": []
                },
            ]
        }

        response = client.put(
            "/api/roles",
            query_string={"survey_uid": survey_uid},
            json=payload,
            content_type="application/json",
            headers={"X-CSRF-Token": csrf_token},
        )
        assert response.status_code == 200

        response = client.get("/api/roles", query_string={"survey_uid": survey_uid})

        print(response.json)

        return response.json


    @pytest.fixture
    def create_user_hierarchy(self, client, login_test_user, csrf_token, create_survey, create_roles, created_users):
        survey_uid = create_survey.get('data', {}).get('survey', {}).get('survey_uid')
        role_uid = create_roles.get('data', [{}])[0].get('role_uid')
        user_uid = created_users[0]["user"].get("user_uid")
        parent_user_uid = created_users[1]["user"].get("user_uid")

        payload = {
            "survey_uid": survey_uid,
            "role_uid": role_uid,
            "user_uid": user_uid,
            "parent_user_uid": parent_user_uid
        }

        response = client.put(
            "/api/user-hierarchy",
            json = payload,
            content_type="application/json",
            headers={"X-CSRF-Token": csrf_token}
        )

        assert response.status_code == 200
        user_hierarchy_data = response.json
        expected_response = {
            "message": "User hierarchy created successfully",
            "user_hierarchy": {"parent_user_uid": parent_user_uid, "user_uid": user_uid, "role_uid": role_uid,
                               "survey_uid": survey_uid},
        }

        checkdiff = jsondiff.diff(expected_response, user_hierarchy_data)
        assert checkdiff == {}
        return user_hierarchy_data.get("user_hierarchy")

    def test_get_user_hierarchy(self, client, login_test_user, csrf_token, create_user_hierarchy):
        user_uid = create_user_hierarchy.get("user_uid")
        survey_uid = create_user_hierarchy.get("survey_uid")
        parent_user_uid = create_user_hierarchy.get("parent_user_uid")
        role_uid = create_user_hierarchy.get("role_uid")

        response = client.get(
            f"/api/user-hierarchy?user_uid={user_uid}&survey_uid={survey_uid}",
            headers={"X-CSRF-Token": csrf_token}
        )

        print("test_get_user_hierarchy")
        print(response.json)

        assert response.status_code == 200
        user_hierarchy_data = response.json
        expected_response = {
            "success": True,
            "data": {"parent_user_uid":parent_user_uid, "user_uid":user_uid,"role_uid":role_uid,"survey_uid":survey_uid },
        }

        checkdiff = jsondiff.diff(expected_response, user_hierarchy_data)
        assert checkdiff == {}

    # Test updating a user hierarchy entry
    def test_update_user_hierarchy(self, client, login_test_user, csrf_token, create_user_hierarchy, created_users, create_roles):
        survey_uid = create_user_hierarchy.get("survey_uid")
        user_uid = created_users[0]["user"].get("user_uid")
        parent_user_uid = created_users[2]["user"].get("user_uid")
        role_uid = create_roles.get('data', [{}])[1].get('role_uid')

        response = client.put(
            f"/api/user-hierarchy",
            json={
                "survey_uid": survey_uid,
                "role_uid": role_uid,
                "user_uid": user_uid,
                "parent_user_uid": parent_user_uid
            },
            content_type="application/json",
            headers={"X-CSRF-Token": csrf_token}
        )

        assert response.status_code == 200
        user_hierarchy_data = response.json
        expected_response = {
            "message": "User hierarchy updated successfully",
            "user_hierarchy": {"parent_user_uid": parent_user_uid, "user_uid": user_uid, "role_uid": role_uid,
                               "survey_uid": survey_uid},
        }

        checkdiff = jsondiff.diff(expected_response, user_hierarchy_data)
        assert checkdiff == {}

    # Test deleting a user hierarchy entry
    def test_delete_user_hierarchy(self, client, login_test_user, csrf_token, create_user_hierarchy):
        user_uid = create_user_hierarchy.get("user_uid")
        survey_uid = create_user_hierarchy.get("survey_uid")

        response = client.delete(
            f"/api/user-hierarchy?user_uid={user_uid}&survey_uid={survey_uid}",
            headers={"X-CSRF-Token": csrf_token}
        )

        assert response.status_code == 200
        assert b"User hierarchy deleted successfully" in response.data

        # Check if the user hierarchy entry is deleted
        response_get_user_hierarchy = client.get(
            f"/api/user-hierarchy?user_uid={user_uid}&survey_uid={survey_uid}",
            headers={"X-CSRF-Token": csrf_token}
        )
        assert response_get_user_hierarchy.status_code == 404
        assert b"User hierarchy not found" in response_get_user_hierarchy.data
