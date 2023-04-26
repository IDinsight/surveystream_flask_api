import boto3
import base64
from botocore.exceptions import ClientError
import json
import psycopg2 as pg
import yaml


"""
The purpose of this script is to prepare web app tables for the back end e2e tests.

For the e2e tests we want to load csv's into a local db instance to be used
by a local instance of the web app.

This script downloads tables from the remote dev db, de-identifies necessary fields,
and saves them as local csv's.

The de-identification is done as part of the queries (found in configs/table_download_configs.yml)
in order to avoid saving any PII locally.
"""


def main():

    """
    Main function to download tables

    """

    conn = get_dev_db_conn()
    cur = conn.cursor()

    surveys = [3]  # agrifieldnet
    forms = [4]  # agrifieldnet_main_form

    tables_to_download = read_config()

    surveys_tuple_as_str = "(" + ", ".join(str(item) for item in surveys) + ")"
    forms_tuple_as_str = "(" + ", ".join(str(item) for item in forms) + ")"

    for table_item in tables_to_download["tables"]:

        filename = table_item["table_name"]
        inner_sql = (
            table_item["query"]
            .replace("{surveys}", surveys_tuple_as_str)
            .replace("{forms}", forms_tuple_as_str)
        )

        sql = f"COPY ({inner_sql}) TO STDOUT WITH CSV HEADER;"
        with open(f"raw_downloads/table_downloads/{filename}.csv", "w") as file:
            cur.copy_expert(sql, file)

    cur.close()
    conn.close()


def get_dev_db_conn():

    """
    Get the connection to the remote dev db

    """

    db_secret = json.loads(get_aws_secret("data-db-connection-details", "ap-south-1"))

    PG_DATABASE = db_secret["dbname"]
    PG_USERNAME = db_secret["username"]
    PG_PASSWORD = db_secret["password"]

    local_port = 5432

    try:

        conn = pg.connect(
            host="localhost",
            port=local_port,
            user=PG_USERNAME,
            password=PG_PASSWORD,
            database=PG_DATABASE,
        )
    except:
        print("Connection Has Failed...")
    return conn


def get_aws_secret(secret_name, region_name):

    """
    Function to get secrets from the aws secrets manager

    """

    # Create a Secrets Manager client
    session = boto3.session.Session()
    client = session.client(service_name="secretsmanager", region_name=region_name)
    secret = None
    # Retrieve secret
    try:

        secret_value_response = client.get_secret_value(SecretId=secret_name)

    except ClientError as e:
        if e.response["Error"]["Code"] == "DecryptionFailureException":
            raise e
        elif e.response["Error"]["Code"] == "InternalServiceErrorException":
            raise e
        elif e.response["Error"]["Code"] == "InvalidParameterException":
            raise e
        elif e.response["Error"]["Code"] == "InvalidRequestException":
            raise e
        elif e.response["Error"]["Code"] == "ResourceNotFoundException":
            raise e
        else:
            raise e
    else:
        # Decrypt secret using the associated KMS CMK
        if "SecretString" in secret_value_response:
            secret = secret_value_response["SecretString"]
        else:
            secret = base64.b64decode(secret_value_response["SecretBinary"])

    return secret


def read_config():

    """
    Read in the yaml file with configuration for each table to download

    """

    with open("configs/table_download_config.yml") as file:
        tables_to_download = yaml.safe_load(file)

    return tables_to_download


if __name__ == "__main__":
    main()
