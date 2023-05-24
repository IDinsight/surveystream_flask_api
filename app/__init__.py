"""
This contains the application factory for creating flask application instances.
Using the application factory allows for the creation of flask applications configured 
for different environments based on the value of the CONFIG_TYPE environment variable
"""

import os
from flask_mail import Mail
import logging.config
import wtforms_json
from flask_sqlalchemy import SQLAlchemy
from flask import Flask, jsonify
from flask_login import LoginManager
from flask_mail import Mail
from app.config import Config
import sentry_sdk
from sentry_sdk.integrations.flask import FlaskIntegration
from sentry_sdk.integrations.sqlalchemy import SqlalchemyIntegration
from flask_cors import CORS


db = SQLAlchemy()
mail = Mail()
login_manager = LoginManager()
wtforms_json.init()


### Application Factory ###
def create_app():
    app = Flask(__name__)

    #initialize cors for localhost and idinsight.io subdomains
    origins = ['http://localhost:*', 'https://*.idinsight.io']
    CORS(app, origins=origins, supports_credentials=True)

    # Configure the flask app instance
    CONFIG_TYPE = os.getenv("CONFIG_TYPE", default="app.config.DevelopmentConfig")
    app.config.from_object(CONFIG_TYPE)

    # Configure logging
    logging.config.dictConfig(app.config["LOGGING_CONFIG"])

    # Configure Sentry
    sentry_sdk.init(
        integrations=[FlaskIntegration(), SqlalchemyIntegration()],
        **app.config["SENTRY_CONFIG"]
    )

    # Register blueprints
    register_blueprints(app)

    # Initialize flask extension objects
    db.init_app(app)
    mail.init_app(app)
    login_manager.init_app(app)

    # Configure login manager
    from app.models.data_models import User

    @login_manager.user_loader
    def user_loader(user_uid):
        """
        Given user_uid, return the associated User object.
        :param unicode user_uid: user_uid of user to retrieve
        """
        return (
            db.session.query(User)
            .filter(User.user_uid == user_uid, User.active.is_(True))
            .one_or_none()
        )

    # Register error handlers
    register_error_handlers(app)

    return app


### Helper Functions ###
def register_blueprints(app):
    from app.blueprints.assignments import assignments_bp
    from app.blueprints.auth import auth_bp
    from app.blueprints.docs import docs_bp
    from app.blueprints.enumerators import enumerators_bp
    from app.blueprints.forms import forms_bp
    from app.blueprints.healthcheck import healthcheck_bp
    from app.blueprints.module_questionnaire import module_questionnaire_bp
    from app.blueprints.module_selection import module_selection_bp
    from app.blueprints.profile import profile_bp
    from app.blueprints.surveys import surveys_bp
    from app.blueprints.surveys_list import surveys_list_bp
    from app.blueprints.table_config import table_config_bp
    from app.blueprints.targets import targets_bp
    from app.blueprints.user_management import user_management_bp

    app.register_blueprint(assignments_bp)
    app.register_blueprint(auth_bp)
    app.register_blueprint(docs_bp)
    app.register_blueprint(enumerators_bp)
    app.register_blueprint(forms_bp)
    app.register_blueprint(healthcheck_bp)
    app.register_blueprint(module_questionnaire_bp)
    app.register_blueprint(module_selection_bp)
    app.register_blueprint(profile_bp)
    app.register_blueprint(surveys_bp)
    app.register_blueprint(surveys_list_bp)
    app.register_blueprint(table_config_bp)
    app.register_blueprint(targets_bp)
    app.register_blueprint(user_management_bp)


def register_error_handlers(app):
    @app.errorhandler(401)
    def unauthorized(e):
        return jsonify(message=str(e)), 401

    @app.errorhandler(403)
    def forbidden(e):
        return jsonify(message=str(e)), 403

    @app.errorhandler(404)
    def page_not_found(e):
        return jsonify(message=str(e)), 404

    @app.errorhandler(500)
    def internal_server_error(e):
        return jsonify(message=str(e)), 500
