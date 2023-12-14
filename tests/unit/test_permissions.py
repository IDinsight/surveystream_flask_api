import pytest
from app import db
from app.blueprints.user_management.models import Invite
from app.blueprints.user_management.utils import generate_invite_code, send_invite_email
from app.blueprints.auth.models import User
import jsondiff
import json


@pytest.mark.permissions
class TestPermissions:

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

    def test_default_data_available(self, client, login_test_user, csrf_token):
        response = client.get('/api/permissions', content_type="application/json",
                              headers={"X-CSRF-Token": csrf_token})
        assert response.status_code == 200
        # Ensure the default permission is present in the response
        response_data = response.json
        expected_data = [
            {'description': 'Admin permission',
                'name': 'ADMIN', 'permission_uid': 1},
            {'description': 'Read Survey Locations permission',
                'name': 'READ Survey Locations', 'permission_uid': 2},
            {'description': 'Write Survey Locations permission', 'name': 'WRITE Survey Locations',
             'permission_uid': 3},
            {'description': 'Read Enumerators permission',
                'name': 'READ Enumerators', 'permission_uid': 4},
            {'description': 'Write Enumerators permission',
                'name': 'WRITE Enumerators', 'permission_uid': 5},
            {'description': 'Read Targets permission',
                'name': 'READ Targets', 'permission_uid': 6},
            {'description': 'Write Targets permission',
                'name': 'WRITE Targets', 'permission_uid': 7},
            {'description': 'Read Assignments permission',
                'name': 'READ Assignments', 'permission_uid': 8},
            {'description': 'Write Assignments permission',
                'name': 'WRITE Assignments', 'permission_uid': 9},
            {'description': 'Read Audio Audits permission',
                'name': 'READ Audio Audits', 'permission_uid': 10},
            {'description': 'Write Audio Audits permission',
                'name': 'WRITE Audio Audits', 'permission_uid': 11},
            {'description': 'Read Photo Audits permission',
                'name': 'READ Photo Audits', 'permission_uid': 12},
            {'description': 'Write Photo Audits permission',
                'name': 'WRITE Photo Audits', 'permission_uid': 13},
            {'description': 'Read Productivity permission',
                'name': 'READ Productivity', 'permission_uid': 14},
            {'description': 'Write Productivity permission',
                'name': 'WRITE Productivity', 'permission_uid': 15},
            {'description': 'Read Data Quality permission',
                'name': 'READ Data Quality', 'permission_uid': 16},
            {'description': 'Write Data Quality permission',
                'name': 'WRITE Data Quality', 'permission_uid': 17},
            {'description': 'Read Emails permission',
                'name': 'READ Emails', 'permission_uid': 18},
            {'description': 'Write Emails permission',
                'name': 'WRITE Emails', 'permission_uid': 19}
         ]

        assert jsondiff.diff(expected_data, response_data) == {}


    def test_get_permissions(self, client, login_test_user, csrf_token, create_permission):
        response = client.get('/api/permissions', content_type="application/json",
                              headers={"X-CSRF-Token": csrf_token})
        assert response.status_code == 200

        response_data = response.json
        expected_data = [
            {'description': 'Admin permission',
             'name': 'ADMIN', 'permission_uid': 1},
            {'description': 'Read Survey Locations permission',
             'name': 'READ Survey Locations', 'permission_uid': 2},
            {'description': 'Write Survey Locations permission', 'name': 'WRITE Survey Locations',
             'permission_uid': 3},
            {'description': 'Read Enumerators permission',
             'name': 'READ Enumerators', 'permission_uid': 4},
            {'description': 'Write Enumerators permission',
             'name': 'WRITE Enumerators', 'permission_uid': 5},
            {'description': 'Read Targets permission',
             'name': 'READ Targets', 'permission_uid': 6},
            {'description': 'Write Targets permission',
             'name': 'WRITE Targets', 'permission_uid': 7},
            {'description': 'Read Assignments permission',
             'name': 'READ Assignments', 'permission_uid': 8},
            {'description': 'Write Assignments permission',
             'name': 'WRITE Assignments', 'permission_uid': 9},
            {'description': 'Read Audio Audits permission',
             'name': 'READ Audio Audits', 'permission_uid': 10},
            {'description': 'Write Audio Audits permission',
             'name': 'WRITE Audio Audits', 'permission_uid': 11},
            {'description': 'Read Photo Audits permission',
             'name': 'READ Photo Audits', 'permission_uid': 12},
            {'description': 'Write Photo Audits permission',
             'name': 'WRITE Photo Audits', 'permission_uid': 13},
            {'description': 'Read Productivity permission',
             'name': 'READ Productivity', 'permission_uid': 14},
            {'description': 'Write Productivity permission',
             'name': 'WRITE Productivity', 'permission_uid': 15},
            {'description': 'Read Data Quality permission',
             'name': 'READ Data Quality', 'permission_uid': 16},
            {'description': 'Write Data Quality permission',
             'name': 'WRITE Data Quality', 'permission_uid': 17},
            {'description': 'Read Emails permission',
             'name': 'READ Emails', 'permission_uid': 18},
            {'description': 'Write Emails permission',
             'name': 'WRITE Emails', 'permission_uid': 19},
            {'permission_uid': create_permission['permission_uid'], 'name': create_permission['name'],
             'description': create_permission['description']},
        ]

        assert jsondiff.diff(expected_data, response_data) == {}

    def test_get_permission(self, client, login_test_user, csrf_token, create_permission):
        response = client.get(f"/api/permissions/{create_permission['permission_uid']}", content_type="application/json",
                              headers={"X-CSRF-Token": csrf_token})
        assert response.status_code == 200
        assert response.json == {'permission_uid': create_permission['permission_uid'], 'name': create_permission['name'],
                'description': create_permission['description']}

    def test_update_permission(self, client, login_test_user, csrf_token, create_permission):
        permission_id = create_permission['permission_uid']
        data = {'name': 'UPDATED', 'description': 'Updated permission'}
        response = client.put(f'/api/permissions/{permission_id}', json=data, content_type="application/json",
                              headers={"X-CSRF-Token": csrf_token})
        assert response.status_code == 200
        assert response.json['message'] == 'Permission updated successfully'

        # Verify the permission is updated in the database
        update_response = client.get(f'/api/permissions/{permission_id}', content_type="application/json",
                                     headers={"X-CSRF-Token": csrf_token})
        assert update_response.status_code == 200
        assert update_response.json == {'permission_uid': permission_id, 'name': 'UPDATED',
                                        'description': 'Updated permission'}

    def test_delete_permission(self, client, login_test_user, csrf_token, create_permission):
        permission_id = create_permission['permission_uid']
        response = client.delete(f'/api/permissions/{permission_id}', content_type="application/json",
                                 headers={"X-CSRF-Token": csrf_token})
        assert response.status_code == 200
        assert response.json['message'] == 'Permission deleted successfully'

        # Verify the permission is deleted from the database
        delete_response = client.get(f'/api/permissions/{permission_id}', content_type="application/json",
                                     headers={"X-CSRF-Token": csrf_token})
        assert delete_response.status_code == 404
