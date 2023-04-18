# Running test

- Login to AWS SSO and copy the access key, id and token (under Command line or programmatic access. Copy option 2 details ) from the admin and dev profiles to your aws credentials file. The profile name for admin is `surveystream_admin` and dev is `surveystream_dev` (the details in []).

- set the AWS profile: `export AWS_PROFILE=surveystream_dev`

Run this command before running the application container. This will connect to the Bastion host and enable the db to be accessed through localhost

`AWS_DEFAULT_REGION=ap-south-1 AWS_PROFILE=surveystream_dev aws ssm start-session --target i-0c08ac05a9796bc30 --document-name AWS-StartPortForwardingSession --parameters '{"portNumber":["5432"],"localPortNumber":["5432"]}'`

- Run test: `pytest auth_test_cases.py`

If you get error or you want to print stdout then run pytest with capture flag.
Example: `pytest auth_test_cases.py --capture=no`
