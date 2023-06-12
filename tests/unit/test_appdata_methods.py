import jsondiff
import pytest
from app import db
from utils import (
    delete_assignments,
    reset_surveyor_status,
    load_reference_data,
)


@pytest.mark.appdata
class TestAppData:
    def test_table_config_response(self, client, login_test_user):
        """
        Check table-config endpoint response
        """

        response = client.get("/api/table-config", query_string={"form_uid": 4})
        assert response.status_code == 200

        checkdiff = jsondiff.diff(
            load_reference_data("table-config.json"), response.json
        )

        assert checkdiff == {}

    @pytest.mark.slow
    def test_targets_response(self, client, login_test_user):
        """
        Check targets endpoint response
        """

        response = client.get("/api/targets", query_string={"form_uid": 4})
        assert response.status_code == 200

        checkdiff = jsondiff.diff(load_reference_data("targets.json"), response.json)

        assert checkdiff == {}

    @pytest.mark.slow
    def test_enumerators_response(self, client, login_test_user):
        """
        Check enumerators endpoint response
        """

        response = client.get("/api/enumerators", query_string={"form_uid": 4})
        assert response.status_code == 200

        checkdiff = jsondiff.diff(
            load_reference_data("enumerators.json"), response.json
        )

        assert checkdiff == {}

    @pytest.mark.slow
    def test_assignments_response(self, client, login_test_user):
        """
        Check assignments endpoint response
        """

        response = client.get("/api/assignments", query_string={"form_uid": 4})
        assert response.status_code == 200

        checkdiff = jsondiff.diff(
            load_reference_data("assignments.json"), response.json
        )

        assert checkdiff == {}

    @pytest.mark.slow
    def test_surveyor_status_update(self, app, client, login_test_user, csrf_token):
        """
        Check updating a surveyor's status and confirm that only allowed statuses work
        """

        form_uid = 4
        enumerator_uid = 1311
        statuses_to_check = [
            {"status": "Active", "expected_diff": {}, "expected_status_code": 200},
            {
                "status": "Temp. Inactive",
                "expected_diff": {26: {"status": "Temp. Inactive"}},
                "expected_status_code": 200,
            },
            {
                "status": "Dropout",
                "expected_diff": {26: {"status": "Dropout"}},
                "expected_status_code": 200,
            },
            {
                "status": "asdf",
                "expected_diff": None,
                "expected_status_code": 500,
            },
        ]

        for item in statuses_to_check:
            reset_surveyor_status(self, app, db, enumerator_uid, form_uid, "Active")

            response = client.patch(
                f"/api/enumerators/{enumerator_uid}",
                headers={"X-CSRF-Token": csrf_token},
                json={"form_uid": form_uid, "status": item["status"]},
            )

            assert response.status_code == item["expected_status_code"]

            if item["expected_diff"] is not None:
                response = client.get("/api/enumerators", query_string={"form_uid": 4})
                assert response.status_code == 200

                checkdiff = jsondiff.diff(
                    load_reference_data("enumerators.json"), response.json
                )
                assert checkdiff == item["expected_diff"]

    @pytest.mark.slow
    def test_assignments_update(self, app, client, login_test_user, csrf_token):
        """
        Check that assigning, reassigning, and deleting assignments works as expected
        """

        form_uid = 4
        target_uids = [
            5297,
            7564,
            8478,
            9740,
        ]

        enumerator_uids = [1311, 1343]

        reference_data = load_reference_data("assignments.json")

        # Clear all the assignments for a form in the database
        delete_assignments(app, db, form_uid)

        # Test assignment

        assignments_payload = {
            "assignments": [
                {"target_uid": target_uid, "enumerator_uid": enumerator_uids[0]}
                for target_uid in target_uids
            ]
        }

        response = client.put(
            "/api/assignments",
            query_string={"form_uid": form_uid},
            headers={"X-CSRF-Token": csrf_token},
            json=assignments_payload,
        )
        assert response.status_code == 200

        response = client.get(
            "/api/assignments",
            query_string={"form_uid": form_uid},
        )

        checkdiff = jsondiff.diff(reference_data, response.json)

        expected_diff = {
            "assignments": {
                0: {
                    "assigned_enumerator_id": "7d334d6176",
                    "assigned_enumerator_name": "d5f5359788e37d0090d52292a4ff701e "
                    "d8f260966e391f0a1349c3dd79212e9f "
                    "523ee4fe2574cc5728043c69898187fd",
                    "assigned_enumerator_uid": 1311,
                    "home_block": "739c7b5b523d7a9c951f20b5483df8fe",
                    "home_district": "0ab0d0e6d78ed85b614c6849a03482c4",
                    "home_state": "9fbfe15b36b494e66115a797c9c55ffc",
                },
                1284: {
                    "assigned_enumerator_id": "7d334d6176",
                    "assigned_enumerator_name": "d5f5359788e37d0090d52292a4ff701e "
                    "d8f260966e391f0a1349c3dd79212e9f "
                    "523ee4fe2574cc5728043c69898187fd",
                    "assigned_enumerator_uid": 1311,
                    "home_block": "739c7b5b523d7a9c951f20b5483df8fe",
                    "home_district": "0ab0d0e6d78ed85b614c6849a03482c4",
                    "home_state": "9fbfe15b36b494e66115a797c9c55ffc",
                },
                1925: {
                    "assigned_enumerator_id": "7d334d6176",
                    "assigned_enumerator_name": "d5f5359788e37d0090d52292a4ff701e "
                    "d8f260966e391f0a1349c3dd79212e9f "
                    "523ee4fe2574cc5728043c69898187fd",
                    "assigned_enumerator_uid": 1311,
                    "home_block": "739c7b5b523d7a9c951f20b5483df8fe",
                    "home_district": "0ab0d0e6d78ed85b614c6849a03482c4",
                    "home_state": "9fbfe15b36b494e66115a797c9c55ffc",
                },
                2453: {
                    "assigned_enumerator_id": "7d334d6176",
                    "assigned_enumerator_name": "d5f5359788e37d0090d52292a4ff701e "
                    "d8f260966e391f0a1349c3dd79212e9f "
                    "523ee4fe2574cc5728043c69898187fd",
                    "assigned_enumerator_uid": 1311,
                    "home_block": "739c7b5b523d7a9c951f20b5483df8fe",
                    "home_district": "0ab0d0e6d78ed85b614c6849a03482c4",
                    "home_state": "9fbfe15b36b494e66115a797c9c55ffc",
                },
            },
            "surveyors": {
                26: {
                    "form_productivity": {0: {"total_complete": 3, "total_pending": 1}},
                    "total_complete_targets": 3,
                    "total_pending_targets": 1,
                }
            },
        }

        assert checkdiff == expected_diff

        # Test reassignment

        assignments_payload = {
            "assignments": [
                {"target_uid": target_uid, "enumerator_uid": enumerator_uids[1]}
                for target_uid in target_uids
            ]
        }
        response = client.put(
            "/api/assignments",
            query_string={"form_uid": form_uid},
            headers={"X-CSRF-Token": csrf_token},
            json=assignments_payload,
        )

        response = client.get(
            "/api/assignments",
            query_string={"form_uid": form_uid},
        )

        checkdiff = jsondiff.diff(reference_data, response.json)

        expected_diff = {
            "assignments": {
                0: {
                    "assigned_enumerator_id": "326ef9ba37",
                    "assigned_enumerator_name": "272d62f9ea5986ac42680d70c5a65fa4 "
                    "573dba4db8eaea4808c7ca383e5b1db2 "
                    "0a6ca90e15e191d40771e88430801ad0",
                    "assigned_enumerator_uid": 1343,
                    "home_block": "bb544c3dcc183ec04e32e0abdebe5336",
                    "home_district": "ffda5c391523b8c8a02cd00bbb098485",
                    "home_state": "d107f92388c154a032aaac92a24aed4c",
                },
                1284: {
                    "assigned_enumerator_id": "326ef9ba37",
                    "assigned_enumerator_name": "272d62f9ea5986ac42680d70c5a65fa4 "
                    "573dba4db8eaea4808c7ca383e5b1db2 "
                    "0a6ca90e15e191d40771e88430801ad0",
                    "assigned_enumerator_uid": 1343,
                    "home_block": "bb544c3dcc183ec04e32e0abdebe5336",
                    "home_district": "ffda5c391523b8c8a02cd00bbb098485",
                    "home_state": "d107f92388c154a032aaac92a24aed4c",
                },
                1925: {
                    "assigned_enumerator_id": "326ef9ba37",
                    "assigned_enumerator_name": "272d62f9ea5986ac42680d70c5a65fa4 "
                    "573dba4db8eaea4808c7ca383e5b1db2 "
                    "0a6ca90e15e191d40771e88430801ad0",
                    "assigned_enumerator_uid": 1343,
                    "home_block": "bb544c3dcc183ec04e32e0abdebe5336",
                    "home_district": "ffda5c391523b8c8a02cd00bbb098485",
                    "home_state": "d107f92388c154a032aaac92a24aed4c",
                },
                2453: {
                    "assigned_enumerator_id": "326ef9ba37",
                    "assigned_enumerator_name": "272d62f9ea5986ac42680d70c5a65fa4 "
                    "573dba4db8eaea4808c7ca383e5b1db2 "
                    "0a6ca90e15e191d40771e88430801ad0",
                    "assigned_enumerator_uid": 1343,
                    "home_block": "bb544c3dcc183ec04e32e0abdebe5336",
                    "home_district": "ffda5c391523b8c8a02cd00bbb098485",
                    "home_state": "d107f92388c154a032aaac92a24aed4c",
                },
            },
            "surveyors": {
                9: {
                    "form_productivity": {0: {"total_complete": 3, "total_pending": 1}},
                    "total_complete_targets": 3,
                    "total_pending_targets": 1,
                }
            },
        }

        assert checkdiff == expected_diff

        # Test unassignment

        response = client.put(
            "/api/assignments",
            query_string={"form_uid": form_uid},
            headers={"X-CSRF-Token": csrf_token},
            json=assignments_payload,
        )

        response = client.get(
            "/api/assignments",
            query_string={"form_uid": form_uid},
        )
        assert response.status_code == 200

        checkdiff = jsondiff.diff(reference_data, response.json)

        assert checkdiff == {}

    @pytest.mark.slow
    def test_surveyor_dropout_assignments_release(
        self, app, client, login_test_user, csrf_token
    ):
        """
        Check that marking a surveyor as dropout releases their assignments
        """

        form_uid = 4
        target_uids = [
            5297,
            7564,
            8478,
            9740,
        ]

        enumerator_uid = 1311

        reference_data = load_reference_data("assignments.json")

        # Clear all the assignments for a form in the database
        delete_assignments(app, db, form_uid)

        assignments_payload = {
            "assignments": [
                {"target_uid": target_uid, "enumerator_uid": enumerator_uid}
                for target_uid in target_uids
            ]
        }
        response = client.put(
            "/api/assignments",
            query_string={"form_uid": form_uid},
            headers={"X-CSRF-Token": csrf_token},
            json=assignments_payload,
        )

        assert response.status_code == 200

        response = client.get(
            "/api/assignments",
            query_string={"form_uid": form_uid},
        )

        checkdiff = jsondiff.diff(reference_data, response.json)

        expected_diff = {
            "assignments": {
                0: {
                    "assigned_enumerator_id": "7d334d6176",
                    "assigned_enumerator_name": "d5f5359788e37d0090d52292a4ff701e "
                    "d8f260966e391f0a1349c3dd79212e9f "
                    "523ee4fe2574cc5728043c69898187fd",
                    "assigned_enumerator_uid": 1311,
                    "home_block": "739c7b5b523d7a9c951f20b5483df8fe",
                    "home_district": "0ab0d0e6d78ed85b614c6849a03482c4",
                    "home_state": "9fbfe15b36b494e66115a797c9c55ffc",
                },
                1284: {
                    "assigned_enumerator_id": "7d334d6176",
                    "assigned_enumerator_name": "d5f5359788e37d0090d52292a4ff701e "
                    "d8f260966e391f0a1349c3dd79212e9f "
                    "523ee4fe2574cc5728043c69898187fd",
                    "assigned_enumerator_uid": 1311,
                    "home_block": "739c7b5b523d7a9c951f20b5483df8fe",
                    "home_district": "0ab0d0e6d78ed85b614c6849a03482c4",
                    "home_state": "9fbfe15b36b494e66115a797c9c55ffc",
                },
                1925: {
                    "assigned_enumerator_id": "7d334d6176",
                    "assigned_enumerator_name": "d5f5359788e37d0090d52292a4ff701e "
                    "d8f260966e391f0a1349c3dd79212e9f "
                    "523ee4fe2574cc5728043c69898187fd",
                    "assigned_enumerator_uid": 1311,
                    "home_block": "739c7b5b523d7a9c951f20b5483df8fe",
                    "home_district": "0ab0d0e6d78ed85b614c6849a03482c4",
                    "home_state": "9fbfe15b36b494e66115a797c9c55ffc",
                },
                2453: {
                    "assigned_enumerator_id": "7d334d6176",
                    "assigned_enumerator_name": "d5f5359788e37d0090d52292a4ff701e "
                    "d8f260966e391f0a1349c3dd79212e9f "
                    "523ee4fe2574cc5728043c69898187fd",
                    "assigned_enumerator_uid": 1311,
                    "home_block": "739c7b5b523d7a9c951f20b5483df8fe",
                    "home_district": "0ab0d0e6d78ed85b614c6849a03482c4",
                    "home_state": "9fbfe15b36b494e66115a797c9c55ffc",
                },
            },
            "surveyors": {
                26: {
                    "form_productivity": {0: {"total_complete": 3, "total_pending": 1}},
                    "total_complete_targets": 3,
                    "total_pending_targets": 1,
                }
            },
        }

        assert checkdiff == expected_diff

        response = client.patch(
            f"/api/enumerators/{enumerator_uid}",
            headers={"X-CSRF-Token": csrf_token},
            json={"form_uid": form_uid, "status": "Dropout"},
        )

        response = client.get(
            "/api/assignments",
            query_string={"form_uid": form_uid},
        )

        checkdiff = jsondiff.diff(reference_data, response.json, marshal=True)

        assert checkdiff == {
            "assignments": {
                1284: {
                    "assigned_enumerator_id": "7d334d6176",
                    "assigned_enumerator_name": "d5f5359788e37d0090d52292a4ff701e "
                    "d8f260966e391f0a1349c3dd79212e9f "
                    "523ee4fe2574cc5728043c69898187fd",
                    "assigned_enumerator_uid": 1311,
                    "home_block": "739c7b5b523d7a9c951f20b5483df8fe",
                    "home_district": "0ab0d0e6d78ed85b614c6849a03482c4",
                    "home_state": "9fbfe15b36b494e66115a797c9c55ffc",
                },
                1925: {
                    "assigned_enumerator_id": "7d334d6176",
                    "assigned_enumerator_name": "d5f5359788e37d0090d52292a4ff701e "
                    "d8f260966e391f0a1349c3dd79212e9f "
                    "523ee4fe2574cc5728043c69898187fd",
                    "assigned_enumerator_uid": 1311,
                    "home_block": "739c7b5b523d7a9c951f20b5483df8fe",
                    "home_district": "0ab0d0e6d78ed85b614c6849a03482c4",
                    "home_state": "9fbfe15b36b494e66115a797c9c55ffc",
                },
                2453: {
                    "assigned_enumerator_id": "7d334d6176",
                    "assigned_enumerator_name": "d5f5359788e37d0090d52292a4ff701e "
                    "d8f260966e391f0a1349c3dd79212e9f "
                    "523ee4fe2574cc5728043c69898187fd",
                    "assigned_enumerator_uid": 1311,
                    "home_block": "739c7b5b523d7a9c951f20b5483df8fe",
                    "home_district": "0ab0d0e6d78ed85b614c6849a03482c4",
                    "home_state": "9fbfe15b36b494e66115a797c9c55ffc",
                },
            },
            "surveyors": {"$delete": [26]},
        }
