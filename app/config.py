#!/usr/bin/env python

import os


class Config:
    """
    Base configuration class. Contains default configuration settings + configuration settings applicable to all environments.
    """

    # Default Flask settings
    DEBUG = False
    TESTING = False
    WTF_CSRF_ENABLED = True

    # AWS region
    AWS_REGION = os.getenv("AWS_REGION")

    # Flask secret key
    SECRET_KEY = os.getenv("SECRET_KEY")

    # Web assets bucket name
    S3_BUCKET_NAME = os.getenv("S3_BUCKET_NAME")

    # DB login details
    DB_HOST = os.getenv("DB_HOST")
    DB_USER = os.getenv("DB_USER")
    DB_PASS = os.getenv("DB_PASS")
    DB_NAME = os.getenv("DB_NAME")

    # DB settings
    SQLALCHEMY_ENGINE_OPTIONS = {
        "pool_pre_ping": True,
        "pool_recycle": 300,
    }

    # Mail settings
    MAIL_SERVER = "smtp.sendgrid.net"
    MAIL_PORT = 587
    MAIL_USERNAME = os.getenv("MAIL_USERNAME")
    MAIL_USE_TLS = True
    MAIL_DEFAULT_SENDER = "surveystream@idinsight.org"
    MAIL_PASSWORD = os.getenv("MAIL_PASSWORD")
    MAIL_SUPPRESS_SEND = False

    SQLALCHEMY_TRACK_MODIFICATIONS = False

    REACT_BASE_URL = "http://localhost:3000"

    PROTECT_DOCS_ENDPOINT = True

    LOGGING_CONFIG = {
        "version": 1,
        "disable_existing_loggers": False,
        "formatters": {
            "default": {
                "format": "%(asctime)s [%(process)d] [%(levelname)s] in %(module)s: %(message)s",
                "datefmt": "[%Y-%m-%d %H:%M:%S %z]",
                "class": "logging.Formatter",
            },
        },
        "handlers": {
            "stream": {
                "class": "logging.StreamHandler",
                "stream": "ext://sys.stdout",
                "formatter": "default",
            },
        },
        "root": {"handlers": ["stream"], "level": "INFO"},
    }

    SENTRY_CONFIG = {"dsn": ""}


class DevelopmentConfig(Config):
    DEBUG = True

    SQLALCHEMY_DATABASE_URI = "postgresql://%s:%s@%s:%s/%s" % (
        Config.DB_USER,
        Config.DB_PASS,
        "host.docker.internal",
        5432,
        Config.DB_NAME,
    )

    PROTECT_DOCS_ENDPOINT = False


class ProfilerConfig(Config):
    SQLALCHEMY_ECHO = True
    LOGGING_CONFIG = {
        "version": 1,
        "disable_existing_loggers": False,
        "formatters": {"default": {"format": "%(message)s"}},
        "handlers": {
            "file": {
                "class": "logging.FileHandler",
                "level": "INFO",
                "formatter": "default",
                "filename": "/usr/src/dod_surveystream_backend/app.log",
                "mode": "w",
            },
        },
        "root": {"handlers": ["file"], "level": "INFO"},
    }

    SQLALCHEMY_DATABASE_URI = "postgresql://%s:%s@%s:%s/%s" % (
        Config.DB_USER,
        Config.DB_PASS,
        Config.DB_HOST,
        5432,
        Config.DB_NAME,
    )


class E2eTestConfig(Config):
    SQLALCHEMY_DATABASE_URI = "postgresql://%s:%s@%s:%s/%s" % (
        "test_user",
        "dod",
        "postgres",
        5433,
        "dod",
    )


class UnitTestConfig(Config):
    SQLALCHEMY_DATABASE_URI = "postgresql://%s:%s@%s:%s/%s" % (
        "test_user",
        "dod",
        "postgres",
        5433,
        "dod",
    )


class StagingConfig(Config):
    SQLALCHEMY_DATABASE_URI = "postgresql://%s:%s@%s:%s/%s" % (
        Config.DB_USER,
        Config.DB_PASS,
        Config.DB_HOST,
        5432,
        Config.DB_NAME,
    )

    REACT_BASE_URL = "https://callisto.stg.surveystream.idinsight.io"

    SENTRY_CONFIG = {
        "dsn": "https://c320e08cbf204069afb2cc62ee498018@o564222.ingest.sentry.io/4505070237319168",
        "traces_sample_rate": "1.0",
        "environment": "staging-callisto",
    }


class ProductionConfig(Config):
    SQLALCHEMY_DATABASE_URI = "postgresql://%s:%s@%s:%s/%s" % (
        Config.DB_USER,
        Config.DB_PASS,
        Config.DB_HOST,
        5432,
        Config.DB_NAME,
    )

    REACT_BASE_URL = "https://surveystream.idinsight.io"

    SENTRY_CONFIG = {
        "dsn": "https://c320e08cbf204069afb2cc62ee498018@o564222.ingest.sentry.io/4505070237319168",
        "traces_sample_rate": "1.0",
        "environment": "production",
    }
