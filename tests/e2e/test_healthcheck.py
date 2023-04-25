import requests
import os


def test_healthcheck():
    # Placeholder test just to make sure the infra works

    API_HOST = os.getenv("API_HOST")
    API_PORT = os.getenv("API_PORT")

    response = requests.get(f"{API_HOST}:{API_PORT}/api/healthcheck")

    assert response.status_code == 200
