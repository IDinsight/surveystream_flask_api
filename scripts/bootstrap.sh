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
		--region $AWS_REGION \
        --role-session-name GlobalSecretSession \
        --query "Credentials.[AccessKeyId,SecretAccessKey,SessionToken]" \
		--endpoint-url https://sts.$AWS_REGION.amazonaws.com \
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

echo "Fetching variables from aws store..."

# DB credentials

DB_SECRET=$(get_secret_value "web-db-connection-details" "" "json" "$AWS_REGION")

export DB_HOST=$(echo "$DB_SECRET" | jq -r 'fromjson | .host')
export DB_USER=$(echo "$DB_SECRET" | jq -r 'fromjson | .username')
export DB_PASS=$(echo "$DB_SECRET" | jq -r 'fromjson | .password')
export DB_NAME=$(echo "$DB_SECRET" | jq -r 'fromjson | .dbname')

echo "Fetched DB secret"

# Sendgrid API credentials
export MAIL_PASSWORD=$(get_global_secret_value "sendgrid-api-key" "" "text" "$AWS_REGION")
export MAIL_USERNAME="apikey"

echo "Fetched Sendgrid secret"

# S3 web assets bucket
export S3_BUCKET_NAME=$(get_secret_value "web-callisto-assets-bucket-name" "" "text" "$AWS_REGION")

echo "Fetched S3 secret"

# Flask secret key
export SECRET_KEY=$(get_secret_value "flask-secret-key" "SECRET_KEY" "json" "$AWS_REGION")

echo "Fetched Flask secret"


exec "$@"


