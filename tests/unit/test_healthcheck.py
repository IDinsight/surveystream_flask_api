def test_healthcheck(client):
    """
    Check healthcheck endpoint response
    """

    response = client.get("/api/healthcheck")

    assert response.status_code == 200
