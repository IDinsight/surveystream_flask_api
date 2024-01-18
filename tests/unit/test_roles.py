import jsondiff
import pytest


@pytest.mark.roles
class TestRoles:
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

    @pytest.fixture
    def create_permission(self, client, login_test_user, csrf_token):
        data = {'name': 'WRITE', 'description': 'Write permission'}
        response = client.post('/api/permissions', json=data, content_type="application/json",
                               headers={"X-CSRF-Token": csrf_token})
        assert response.status_code == 201
        assert response.json['message'] == 'Permission created successfully'

        return {
            'permission_uid': response.json['permission_uid'],
            'name': response.json['name'],
            'description': response.json['description']
        }

    @pytest.fixture()
    def create_roles(self, client, login_test_user, csrf_token, create_survey, create_permission):
        """
        Insert new roles as a setup step for the roles tests
        """

        payload = {
            "roles": [
                {
                    "role_uid": None,
                    "role_name": "Core User",
                    "reporting_role_uid": None,
                    "permissions": [create_permission['permission_uid']]
                },
                {
                    "role_uid": None,
                    "role_name": "Regional Coordinator",
                    "reporting_role_uid": 1,
                    "permissions": [create_permission['permission_uid']]
                },
            ]
        }

        response = client.put(
            "/api/roles",
            query_string={"survey_uid": 1},
            json=payload,
            content_type="application/json",
            headers={"X-CSRF-Token": csrf_token},
        )
        assert response.status_code == 200

        yield

    def test_insert_roles(self, client, login_test_user, create_roles, create_permission):
        """
        Test that the roles are inserted correctly
        The order of the roles in the payload should be reflected in the assignment of the role_uid
        """

        # Test the roles were inserted correctly
        response = client.get("/api/roles", query_string={"survey_uid": 1})
        expected_response = {
            "data": [
                {
                    "role_uid": 1,
                    "role_name": "Core User",
                    "reporting_role_uid": None,
                    "survey_uid": 1,
                    "permissions": [create_permission['permission_uid']]

                },
                {
                    "role_uid": 2,
                    "role_name": "Regional Coordinator",
                    "reporting_role_uid": 1,
                    "survey_uid": 1,
                    "permissions": [create_permission['permission_uid']]
                },
            ],
            "success": True,
        }

        checkdiff = jsondiff.diff(expected_response, response.json)
        assert checkdiff == {}

    def test_update_roles(self, client, login_test_user, create_roles, csrf_token):
        """
        Test that existing roles can be updated
        """

        # Try to update the existing roles
        payload = {
            "roles": [
                {
                    "role_uid": 1,
                    "role_name": "Core User",
                    "reporting_role_uid": None,
                    "permissions": []

                },
                {
                    "role_uid": 2,
                    "role_name": "State Coordinator",
                    "reporting_role_uid": 1,
                    "permissions": []
                },
            ]
        }

        response = client.put(
            "/api/roles",
            query_string={"survey_uid": 1},
            json=payload,
            content_type="application/json",
            headers={"X-CSRF-Token": csrf_token},
        )
        assert response.status_code == 200

        response = client.get("/api/roles", query_string={"survey_uid": 1})

        print(response)

        expected_response = {
            "data": [
                {
                    "role_uid": 1,
                    "role_name": "Core User",
                    "reporting_role_uid": None,
                    "survey_uid": 1,
                    "permissions": []
                },
                {
                    "role_uid": 2,
                    "role_name": "State Coordinator",
                    "reporting_role_uid": 1,
                    "survey_uid": 1,
                    "permissions": []
                },
            ],
            "success": True,
        }

        checkdiff = jsondiff.diff(expected_response, response.json)
        assert checkdiff == {}

    def test_update_roles_deferrable_constraint_violation(
        self, client, login_test_user, create_roles, csrf_token
    ):
        """
        Test that updating roles with a temporary unique constraint violation succeeds
        """

        # Try to update the existing roles
        payload = {
            "roles": [
                {
                    "role_uid": 1,
                    "role_name": "Regional Coordinator",
                    "reporting_role_uid": None,
                    "permissions": []
                },
                {
                    "role_uid": 2,
                    "role_name": "Core User",
                    "reporting_role_uid": 1,
                    "permissions": []
                },
            ]
        }

        response = client.put(
            "/api/roles",
            query_string={"survey_uid": 1},
            json=payload,
            content_type="application/json",
            headers={"X-CSRF-Token": csrf_token},
        )
        assert response.status_code == 200

        # Check the response
        response = client.get("/api/roles", query_string={"survey_uid": 1})

        expected_response = {
            "data": [
                {
                    "role_uid": 1,
                    "role_name": "Regional Coordinator",
                    "reporting_role_uid": None,
                    "survey_uid": 1,
                    "permissions": []

                },
                {
                    "role_uid": 2,
                    "role_name": "Core User",
                    "reporting_role_uid": 1,
                    "survey_uid": 1,
                    "permissions": []

                },
            ],
            "success": True,
        }

        checkdiff = jsondiff.diff(expected_response, response.json)
        assert checkdiff == {}

    def test_update_roles_constraint_violation(
        self, client, login_test_user, create_roles, csrf_token
    ):
        """
        Test that updating roles with a temporary unique constraint violation succeeds
        """

        # Try to update the existing roles with a unique constraint violation on `role_name`
        payload = {
            "roles": [
                {
                    "role_uid": 1,
                    "role_name": "Core User",
                    "reporting_role_uid": None,
                    "permissions": []

                },
                {
                    "role_uid": 2,
                    "role_name": "Core User",
                    "reporting_role_uid": 1,
                    "permissions": []

                },
            ]
        }

        response = client.put(
            "/api/roles",
            query_string={"survey_uid": 1},
            json=payload,
            content_type="application/json",
            headers={"X-CSRF-Token": csrf_token},
        )
        assert response.status_code == 500

    def test_delete_role(self, client, login_test_user, create_roles, csrf_token):
        """
        Test that a role can be deleted
        """

        # Try to delete a role that is not being referenced by another role
        payload = {
            "roles": [
                {
                    "role_uid": 1,
                    "role_name": "Core User",
                    "reporting_role_uid": None,
                },
            ]
        }

        response = client.put(
            "/api/roles",
            query_string={"survey_uid": 1},
            json=payload,
            content_type="application/json",
            headers={"X-CSRF-Token": csrf_token},
        )
        assert response.status_code == 200

        # Check the response
        response = client.get("/api/roles", query_string={"survey_uid": 1})

        expected_response = {
            "data": [
                {
                    "role_uid": 1,
                    "role_name": "Core User",
                    "reporting_role_uid": None,
                    "survey_uid": 1,
                    "permissions": []
                },
            ],
            "success": True,
        }

        checkdiff = jsondiff.diff(expected_response, response.json)
        assert checkdiff == {}

    def test_delete_reporting_role(
        self, client, login_test_user, create_roles, csrf_token
    ):
        """
        Test that a role cannot be deleted if it is being referenced by another role
        """

        # Try to delete a role that is being referenced by another role
        payload = {
            "roles": [
                {
                    "role_uid": 2,
                    "role_name": "Regional Coordinator",
                    "reporting_role_uid": 1,
                },
            ]
        }

        response = client.put(
            "/api/roles",
            query_string={"survey_uid": 1},
            json=payload,
            content_type="application/json",
            headers={"X-CSRF-Token": csrf_token},
        )
        assert response.status_code == 500

    def test_roles_validate_hierarchy_invalid_hierarchy(
        self, client, login_test_user, create_survey, csrf_token
    ):
        """
        Test that existing roles can be updated
        """

        payload = {
            "roles": [
                {
                    "role_uid": None,
                    "role_name": "Core Team",
                    "reporting_role_uid": None,
                    "permissions": []
                },
                {
                    "role_uid": None,
                    "role_name": "State Coordinator",
                    "reporting_role_uid": None,
                    "permissions": []

                },
                {
                    "role_uid": None,
                    "role_name": "District Coordinator",
                    "reporting_role_uid": None,
                    "permissions": []

                },
            ]
        }

        response = client.put(
            "/api/roles",
            query_string={"survey_uid": 1},
            json=payload,
            content_type="application/json",
            headers={"X-CSRF-Token": csrf_token},
        )
        assert response.status_code == 200

        # Case 1:
        # Multiple child nodes
        payload = {
            "roles": [
                {
                    "role_uid": 1,
                    "role_name": "Core Team",
                    "reporting_role_uid": None,
                    "permissions": []

                },
                {
                    "role_uid": 2,
                    "role_name": "State Coordinator",
                    "reporting_role_uid": 1,
                    "permissions": []

                },
                {
                    "role_uid": 3,
                    "role_name": "District Coordinator",
                    "reporting_role_uid": 1,
                    "permissions": []

                },
            ],
            "validate_hierarchy": True,
        }

        response = client.put(
            "/api/roles",
            query_string={"survey_uid": 1, "validate_hierarchy": "true"},
            json=payload,
            content_type="application/json",
            headers={"X-CSRF-Token": csrf_token},
        )

        assert response.status_code == 422

        # Check the response
        assert response.json["errors"] == [
            "Each role should have at most one child role. Role 'Core Team' has 2 child roles:\nState Coordinator, District Coordinator"
        ]

        # Case 2:
        # No root node
        payload = {
            "roles": [
                {
                    "role_uid": 1,
                    "role_name": "Core Team",
                    "reporting_role_uid": 3,
                    "permissions": []

                },
                {
                    "role_uid": 2,
                    "role_name": "State Coordinator",
                    "reporting_role_uid": 1,
                    "permissions": []

                },
                {
                    "role_uid": 3,
                    "role_name": "District Coordinator",
                    "reporting_role_uid": 2,
                    "permissions": []

                },
            ],
            "validate_hierarchy": True,
        }

        response = client.put(
            "/api/roles",
            query_string={"survey_uid": 1, "validate_hierarchy": "true"},
            json=payload,
            content_type="application/json",
            headers={"X-CSRF-Token": csrf_token},
        )

        assert response.status_code == 422

        # Check the response
        assert response.json["errors"] == [
            "The hierarchy should have exactly one top level role (ie, a role with no parent). The current hierarchy has 0 roles with no parent."
        ]

        # Case 3:
        # Multiple root nodes
        payload = {
            "roles": [
                {
                    "role_uid": 1,
                    "role_name": "Core Team",
                    "reporting_role_uid": None,
                    "permissions": []

                },
                {
                    "role_uid": 2,
                    "role_name": "State Coordinator",
                    "reporting_role_uid": None,
                    "permissions": []

                },
                {
                    "role_uid": 3,
                    "role_name": "District Coordinator",
                    "reporting_role_uid": 2,
                    "permissions": []

                },
            ],
            "validate_hierarchy": True,
        }

        response = client.put(
            "/api/roles",
            query_string={"survey_uid": 1, "validate_hierarchy": "true"},
            json=payload,
            content_type="application/json",
            headers={"X-CSRF-Token": csrf_token},
        )

        assert response.status_code == 422

        # Check the response
        assert response.json["errors"] == [
            "The hierarchy should have exactly one top level role (ie, a role with no parent). The current hierarchy has 2 roles with no parent:\nCore Team, State Coordinator"
        ]

        # Case 4:
        # Check for a disconnected hierarchy
        payload = {
            "roles": [
                {
                    "role_uid": 1,
                    "role_name": "Core Team",
                    "reporting_role_uid": None,
                    "permissions": []

                },
                {
                    "role_uid": 2,
                    "role_name": "State Coordinator",
                    "reporting_role_uid": 3,
                    "permissions": []

                },
                {
                    "role_uid": 3,
                    "role_name": "District Coordinator",
                    "reporting_role_uid": 2,
                    "permissions": []

                },
            ],
            "validate_hierarchy": True,
        }

        response = client.put(
            "/api/roles",
            query_string={"survey_uid": 1, "validate_hierarchy": "true"},
            json=payload,
            content_type="application/json",
            headers={"X-CSRF-Token": csrf_token},
        )

        assert response.status_code == 422

        assert response.json["errors"] == [
            "All roles in the hierarchy should be able to be connected back to the top level role via a chain of parent role references. The current hierarchy has 2 roles that cannot be connected:\nState Coordinator, District Coordinator"
        ]

        # Case 5:
        # Check for a disconnected hierarchy
        # Caused by self-reference and non-existent parent
        payload = {
            "roles": [
                {
                    "role_uid": 1,
                    "role_name": "Core Team",
                    "reporting_role_uid": None,
                    "permissions": []

                },
                {
                    "role_uid": 2,
                    "role_name": "State Coordinator",
                    "reporting_role_uid": 2,
                    "permissions": []

                },
                {
                    "role_uid": 3,
                    "role_name": "District Coordinator",
                    "reporting_role_uid": 5,
                    "permissions": []

                },
            ],
            "validate_hierarchy": True,
        }

        response = client.put(
            "/api/roles",
            query_string={"survey_uid": 1, "validate_hierarchy": "true"},
            json=payload,
            content_type="application/json",
            headers={"X-CSRF-Token": csrf_token},
        )

        assert response.status_code == 422

        assert response.json["errors"] == [
            "All roles in the hierarchy should be able to be connected back to the top level role via a chain of parent role references. The current hierarchy has 2 roles that cannot be connected:\nState Coordinator, District Coordinator",
            "Role 'State Coordinator' is referenced as its own parent. Self-referencing is not allowed.",
            "Role 'District Coordinator' references a parent role with unique id '5' that is not found in the hierarchy.",
        ]

        # Case 6:
        # Duplicate uid's and names
        payload = {
            "roles": [
                {
                    "role_uid": 1,
                    "role_name": "Core Team",
                    "reporting_role_uid": None,
                    "permissions": []

                },
                {
                    "role_uid": 1,
                    "role_name": "State Coordinator",
                    "reporting_role_uid": 2,
                    "permissions": []

                },
                {
                    "role_uid": 3,
                    "role_name": "State Coordinator",
                    "reporting_role_uid": 5,
                    "permissions": []

                },
            ],
            "validate_hierarchy": True,
        }

        response = client.put(
            "/api/roles",
            query_string={"survey_uid": 1, "validate_hierarchy": "true"},
            json=payload,
            content_type="application/json",
            headers={"X-CSRF-Token": csrf_token},
        )

        assert response.status_code == 422

        assert response.json["errors"] == [
            "Each role unique id defined in the role hierarchy should appear exactly once in the hierarchy. Role with role_uid='1' appears 2 times in the hierarchy.",
            "Each role name defined in the role hierarchy should appear exactly once in the hierarchy. Role with role_name='State Coordinator' appears 2 times in the hierarchy.",
        ]

    def test_roles_validate_hierarchy_valid_hierarchy(
        self, client, login_test_user, create_survey, csrf_token
    ):
        """
        Test that existing roles can be updated
        """

        payload = {
            "roles": [
                {
                    "role_uid": None,
                    "role_name": "Core Team",
                    "reporting_role_uid": None,
                    "permissions": []

                },
                {
                    "role_uid": None,
                    "role_name": "State Coordinator",
                    "reporting_role_uid": None,
                    "permissions": []

                },
                {
                    "role_uid": None,
                    "role_name": "District Coordinator",
                    "reporting_role_uid": None,
                    "permissions": []

                },
            ]
        }

        response = client.put(
            "/api/roles",
            query_string={"survey_uid": 1},
            json=payload,
            content_type="application/json",
            headers={"X-CSRF-Token": csrf_token},
        )
        assert response.status_code == 200

        # Try to update the existing roles
        payload = {
            "roles": [
                {
                    "role_uid": 1,
                    "role_name": "Core Team",
                    "reporting_role_uid": None,
                    "permissions": []

                },
                {
                    "role_uid": 2,
                    "role_name": "State Coordinator",
                    "reporting_role_uid": 1,
                    "permissions": []

                },
                {
                    "role_uid": 3,
                    "role_name": "District Coordinator",
                    "reporting_role_uid": 2,
                    "permissions": []

                },
            ],
            "validate_hierarchy": True,
        }

        response = client.put(
            "/api/roles",
            query_string={"survey_uid": 1, "validate_hierarchy": "true"},
            json=payload,
            content_type="application/json",
            headers={"X-CSRF-Token": csrf_token},
        )

        assert response.status_code == 200
