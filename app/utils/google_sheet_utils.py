import json
import sys

import gspread
import pandas as pd
from flask import current_app, jsonify
from oauth2client.service_account import ServiceAccountCredentials

from app.utils.utils import get_aws_secret, retry_on_exception


class google_sheet_helpers:
    """
    Group of functions to perform all actions relating to Google Sheets
    """

    def __init__(
        self,
        google_service_account_credentials,
        google_sheet_url=None,
        google_sheet_tab=None,
        header_index=1,
        google_sheet_headers=[],
        google_sheet_row_data=[],
        clear_sheet=False,
        clear_sheet_start="A",
        clear_sheet_end="ZZZ",
        cell_range=None,
        *args,
        **kwargs
    ):
        self.google_service_account_credentials = google_service_account_credentials
        self.google_sheet_url = google_sheet_url
        self.google_sheet_tab = google_sheet_tab
        self.header_index = header_index
        self.google_sheet_headers = google_sheet_headers
        self.google_sheet_row_data = google_sheet_row_data
        self.clear_sheet = clear_sheet
        self.clear_sheet_start = clear_sheet_start
        self.clear_sheet_end = clear_sheet_end
        self.cell_range = cell_range
        self.wb = None
        self.sheet = None
        self.sheet_df = None
        super().__init__(*args, **kwargs)

    @retry_on_exception(Exception)
    def google_sheets_client(self):
        scope = ["https://spreadsheets.google.com/feeds"]
        credentials = ServiceAccountCredentials.from_json_keyfile_dict(
            self.google_service_account_credentials, scope
        )

        client = gspread.authorize(credentials)

        return client

    @retry_on_exception(Exception)
    def open_sheet(self, numericise_flag=None):
        """
        Create the sheet object and the sheet dataframe
        """

        client = self.google_sheets_client()

        wb = client.open_by_url(self.google_sheet_url)
        sheet = wb.worksheet(self.google_sheet_tab)
        self.wb = wb
        self.sheet = sheet

        if self.header_index is None:
            self.header_index = 1
        if self.header_index > 0:
            sheet_records = []

            sheet_records = self.sheet.get_all_records(
                head=int(self.header_index), numericise_ignore=numericise_flag
            )
            try:
                if len(sheet_records) > 0:
                    df = pd.DataFrame(
                        sheet_records,
                        columns=self.sheet.row_values(int(self.header_index)),
                    )
                else:
                    df = pd.DataFrame(
                        [], columns=self.sheet.row_values(int(self.header_index))
                    )
            except Exception as e:
                print(str(e))
                sys.exit()

            self.sheet_df = df
        else:
            # When sheet is empty
            self.sheet_df = None

    def read_sheet_headers(self):
        if self.sheet is None:
            self.open_sheet()
        headers_full_list = [x.strip() for x in self.sheet_df.columns.values.tolist()]

        return headers_full_list

    def verify_sheet(self):
        if self.sheet is None:
            self.open_sheet()

        # Check the names of the column headers - match only the required columns from the left
        correct_headers = [x.strip() for x in self.google_sheet_headers]
        actual_headers_full_list = [
            x.strip() for x in self.sheet_df.columns.values.tolist()
        ]
        actual_headers = actual_headers_full_list[0 : len(correct_headers)]

        header_check = True

        for value in actual_headers:
            if value not in correct_headers:
                header_check = False

        if len(correct_headers) != len(actual_headers):
            header_check = False

        if header_check == False:
            raise ValueError(
                'Wrong headers in sheet: "'
                + self.google_sheet_tab
                + '" in row '
                + str(self.header_index)
                + " - Expected: "
                + str(correct_headers)
                + " - Actual: "
                + str(actual_headers)
            )

        return actual_headers

    def read_sheet(self, numericise_ignore=None):
        if self.sheet is None:
            self.open_sheet(numericise_ignore)

            if len(self.google_sheet_headers) > 0:
                self.verify_sheet()

        return self.sheet_df

    def read_cell_range(self):
        if self.sheet is None:
            self.open_sheet()

        sheet_records = self.sheet.get(self.cell_range)

        return sheet_records


def load_google_service_account_credentials():
    # Get the Google sheet Service Account credentials
    google_service_account_secret_name = "google-sheets-service-account"
    try:
        google_service_account_credentials_response = get_aws_secret(
            google_service_account_secret_name,
            current_app.config["AWS_REGION"],
            is_global_secret=True,
        )

        google_service_account_credentials = json.loads(
            google_service_account_credentials_response
        )
        return google_service_account_credentials

    except Exception as e:
        return e
