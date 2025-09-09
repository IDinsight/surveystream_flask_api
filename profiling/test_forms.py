import base64
import json
from datetime import datetime, timedelta
from pathlib import Path

import jsondiff
import pandas as pd
import pytest

from app import db


@pytest.mark.forms
class TestForms:
    @pytest.fixture()
    def create_survey(self, client, login_test_user, csrf_token, test_user_credentials):
        """
        Insert new survey
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
            "prime_geo_level_uid": 1,
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

    @pytest.fixture()
    def create_module_questionnaire(
        self, client, login_test_user, csrf_token, test_user_credentials, create_survey
    ):
        """
        Insert new module_questionnaire to set up mapping criteria needed for assignments
        """

        payload = {
            "assignment_process": "Manual",
            "language_location_mapping": False,
            "reassignment_required": False,
            "target_mapping_criteria": ["Location"],
            "surveyor_mapping_criteria": ["Location"],
            "supervisor_hierarchy_exists": False,
            "supervisor_surveyor_relation": "1:many",
            "survey_uid": 1,
            "target_assignment_criteria": ["Location of surveyors"],
        }

        response = client.put(
            "/api/module-questionnaire/1",
            json=payload,
            content_type="application/json",
            headers={"X-CSRF-Token": csrf_token},
        )
        assert response.status_code == 200

        yield

    @pytest.fixture()
    def create_module_selection(
        self,
        client,
        login_test_user,
        csrf_token,
        test_user_credentials,
        create_module_questionnaire,
    ):
        """
        Insert assignments module_selection
        """

        payload = {
            "survey_uid": 1,
            "modules": ["9"],
        }

        response = client.post(
            "/api/module-status",
            json=payload,
            content_type="application/json",
            headers={"X-CSRF-Token": csrf_token},
        )
        assert response.status_code == 200

        yield

    @pytest.fixture()
    def create_form(self, client, login_test_user, csrf_token, create_module_selection):
        """
        Insert new form
        """

        payload = {
            "survey_uid": 1,
            "scto_form_id": "gates_ifs_survey",
            "form_name": "Agrifieldnet Main Form",
            "tz_name": "Asia/Kolkata",
            "scto_server_name": "dod",
            "encryption_key_shared": True,
            "server_access_role_granted": True,
            "server_access_allowed": True,
            "form_type": "parent",
            "parent_form_uid": None,
            "dq_form_type": None,
            "number_of_attempts": 7,
        }

        response = client.post(
            "/api/forms",
            json=payload,
            content_type="application/json",
            headers={"X-CSRF-Token": csrf_token},
        )
        assert response.status_code == 201

        yield

    def test_scto_form_definition(
        self, client, app, login_test_user, csrf_token, create_form
    ):
        """
        Test ingest the scto form definition from SCTO and fetching them from the database
        """

        # Ingest the SCTO variables from SCTO into the database
        response = client.post(
            "/api/forms/1/scto-form-definition/refresh",
            headers={"X-CSRF-Token": csrf_token},
        )
        print(response.json)
        assert response.status_code == 200

    def test_get_scto_form_definition(
        self, client, app, login_test_user, csrf_token, create_form
    ):
        """
        Test ingest the scto form definition from SCTO and fetching them from the database
        """

        # Ingest the SCTO variables from SCTO into the database
        response = client.post(
            "/api/forms/1/scto-form-definition/refresh",
            headers={"X-CSRF-Token": csrf_token},
        )
        print(response.json)

        # Get the SCTO questions from the database
        response = client.get(
            "/api/forms/1/scto-form-definition",
        )
        assert response.status_code == 200
