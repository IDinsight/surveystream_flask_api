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
    def create_permission(client, login_test_user, csrf_token):
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
        assert response.json == [
            {'permission_uid': 1, 'name': 'READ', 'description': 'Read permission'}]

    def test_get_permissions(self, client, login_test_user, csrf_token):
        response = client.get('/api/permissions', content_type="application/json",
                              headers={"X-CSRF-Token": csrf_token})
        assert response.status_code == 200
        assert response.json == [
            {'permission_uid': 1, 'name': 'READ', 'description': 'Read permission'}]

    def test_get_permission(self, client, login_test_user, csrf_token):
        response = client.get('/api/permissions/1', content_type="application/json",
                              headers={"X-CSRF-Token": csrf_token})
        assert response.status_code == 200
        assert response.json == {'permission_uid': 1,
                                 'name': 'READ', 'description': 'Read permission'}

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


