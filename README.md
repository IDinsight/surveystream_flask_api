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

With the backend running locally, navigate to localhost:5001/docs

## Testing the database connection

localhost:5001/api/healthcheck

## Instructions for running end-to-end tests

### Build the images

The end-to-end tests require an image for the Flask app and an image for the test runner. These can be created with the following make commands:

Flask app: `make image`

Test runner: `make image-test-e2e`

### Run the tests

Once the images are built, the end-to-end tests can be run with the following commands:

`make login`

`make run-test-e2e`