def test_redoc_response(base_url, client, login_test_user):

    response = client.get(f"{base_url}/api/docs")

    assert response.status_code == 200


def test_redoc_protected_endpoint(base_url, client):

    response = client.get(f"{base_url}/api/docs")

    assert response.status_code == 401
