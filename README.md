[![Coverage Status](https://coveralls.io/repos/github/IDinsight/dod_surveystream_flask_api/badge.svg?t=BhAQ0K)](https://coveralls.io/github/IDinsight/dod_surveystream_flask_api)
![Unit Tests](https://github.com/IDinsight/dod_surveystream_flask_api/actions/workflows/unittest.yml/badge.svg)

# DOD SurveyStream Back End

## Instructions for running locally

### Running locally with the remote dev database

- [First time setup] Set up your AWS config file (`~/.aws/config`) to work with the dev environment and AWS SSO. Make sure your config file contains the following entry:

`[profile surveystream_dev]
sso_start_url = https://idinsight.awsapps.com/start
sso_region = ap-south-1
sso_account_id = 453207568606
sso_role_name = AdministratorAccess
region = ap-south-1`

- Verify that you *do not* have an entry for `surveystream_dev` in your AWS credentials file (`~/.aws/credentials`). This is needed to make sure the local endpoints container looks for your temporary SSO-based credentials that are stored in `~/.aws/sso/`.
- From the `root` directory, run `make login` to log into AWS SSO. You will be prompted to log in via a browser window that opens automatically.
- Open a second terminal window and `cd` into the repository root directory. Run `make db-tunnel` to open the connection to the remote db via the bastion host.
- Build the backend image by running `make image`
- Start the container by running `make container-up`.

Now you should be able to access the endpoints on localhost:5001/api/<endpoint_name>.

To stop the app:
- In your first terminal window, remove the running containers by running `make container-down`
- In your second terminal window, type `ctrl-c` to close the SSM connection to the database.

## Accessing the endpoint documentation

The API documentation can be accessed at `/api/docs`. In staging and production environments, this endpoint requires the user to be logged in. 

When running the backend locally, the docs can be accessed without logging in at `localhost:5001/api/docs`.

## Testing the database connection

`localhost:5001/api/healthcheck`

## Instructions for running unit tests

### Update configuration values for the tests

The tests can be configured by updating the values found in `tests/unit/config.yml`:

`email` (string) - The email address to set for the test user. Updating this value will let you customize where emails will be sent for the relevant tests (`forgot-password`, `welcome-user`, etc). You will need to manually check receipt of the emails.

`run_slow_tests` (bool) - Whether to run test cases that have been marked as "slow". Setting this value to True will run the whole test suite which can take over an hour. 

### Build the image

The unit tests get packaged with the main application image. Before running the tests, make sure the image is updated:

`make image`

### Run the tests

Once the images are built, the unit tests can be run with the following commands:

`make login`

`make -i run-unit-tests` (note the `-i` flag will ensure the container cleanup happens even if some of the tests fail)

### Running the tests on CI/CD

The unit tests will run on GitHub Actions on any `push` or `pull request` actions.