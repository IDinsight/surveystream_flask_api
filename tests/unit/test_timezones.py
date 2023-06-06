import pytest


@pytest.mark.timezones
class TestTimezones:
    def test_get_timezones(self, client, login_test_user):
        """
        Test that the timezones can be fetched
        """

        response = client.get("/api/timezones")
        assert response.status_code == 200
        print(response.json)
        # Check the response
        assert "success" in response.json
        assert response.json["success"] is True
        assert "data" in response.json
        assert isinstance(response.json["data"], list)
        assert len(response.json["data"]) > 0
        assert isinstance(response.json["data"][0], dict)
        assert "name" in response.json["data"][0]
        assert "abbrev" in response.json["data"][0]
        assert "utc_offset" in response.json["data"][0]
        assert response.json["data"][1]["name"] == "EST"
        assert response.json["data"][1]["abbrev"] == "EST"
        assert response.json["data"][1]["utc_offset"] == "-05:00"
