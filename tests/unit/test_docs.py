import pytest


@pytest.mark.docs
class TestDocs:
    def test_redoc_response(self, client, login_test_user):
        """
        Test docs
        """

        response = client.get("/api/docs")

        assert response.status_code == 200

    def test_redoc_protected_endpoint(self, client):
        """
        Test docs page is protected
        """

        response = client.get("/api/docs")

        assert response.status_code == 401
