#!/bin/bash
set -e

# Function to add any cleanup actions
function cleanup() {
	echo "Cleanup."
}
trap cleanup EXIT	

# Function to get value from secrets manager using secret name, key name and output type
function get_secret_value() {
	local secret_name="$1" key="$2" form="$3" region="$4"
  	: "${json_secret:=$(aws secretsmanager get-secret-value --secret-id ${secret_name} --region "${region}" --output ${form} --query "SecretString")}"
  	# If key name is provided, parse json output for the key or return text output
  	if [ -z "$key" ]; 
  	then
  		echo $json_secret
  	else
  		: "${value:=$(echo ${json_secret} | jq -r 'fromjson | ."'${key}'"')}"
 		echo $value
 	fi
}

# Function to get value from secrets manager using global secret name, key name and output type
function get_global_secret_value() {
    local secret_name="$1" key="$2" form="$3" region="$4"
    ASSUME_TASK_ROLE_ARN="arn:aws:iam::$ADMIN_ACCOUNT:role/web-assume-task-role"

    export $(printf "AWS_ACCESS_KEY_ID=%s AWS_SECRET_ACCESS_KEY=%s AWS_SESSION_TOKEN=%s" \
        $(aws sts assume-role \
        --role-arn $ASSUME_TASK_ROLE_ARN \
        --role-session-name GlobalSecretSession \
        --query "Credentials.[AccessKeyId,SecretAccessKey,SessionToken]" \
        --output text))	

  	: "${json_secret:=$(aws secretsmanager get-secret-value --secret-id ${secret_name} --region "${region}" --output ${form} --query "SecretString")}"
  	# If key name is provided, parse json output for the key or return text output
  	if [ -z "$key" ]; 
  	then
  		echo $json_secret
  	else
  		: "${value:=$(echo ${json_secret} | jq -r 'fromjson | ."'${key}'"')}"
 		echo $value
 	fi
    unset AWS_ACCESS_KEY_ID
    unset AWS_SECRET_ACCESS_KEY
    unset AWS_SESSION_TOKEN
}

echo "Fetching variables from aws store.."

# DB credentials
export DB_HOST=$(get_secret_value "data-db-connection-details" "host" "json" "$AWS_REGION")
export DB_USER=$(get_secret_value "data-db-connection-details" "username" "json" "$AWS_REGION")
export DB_PASS=$(get_secret_value "data-db-connection-details" "password" "json" "$AWS_REGION")
export DB_NAME=$(get_secret_value "data-db-connection-details" "dbname" "json" "$AWS_REGION")

# Sendgrid API credentials
export MAIL_PASSWORD=$(get_global_secret_value "sendgrid-api-key" "" "text" "$AWS_REGION")
export MAIL_USERNAME="apikey"

# S3 web assets bucket
export S3_BUCKET_NAME=$(get_secret_value "web-assets-bucket-name" "" "text" "$AWS_REGION")

# Flask secret key
export SECRET_KEY=$(get_secret_value "flask-secret-key" "SECRET_KEY" "json" "$AWS_REGION")

exec "$@"


