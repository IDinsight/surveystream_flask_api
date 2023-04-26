def test_healthcheck(base_url, client):
    # Check healthcheck endpoint response

    response = client.get(f"{base_url}/api/healthcheck")

    assert response.status_code == 200
