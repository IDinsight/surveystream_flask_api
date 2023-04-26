"""
This contains the application factory for creating flask application instances.
Using the application factory allows for the creation of flask applications configured 
for different environments based on the value of the CONFIG_TYPE environment variable
"""

import os
from flask_mail import Mail
import logging.config
from flask_sqlalchemy import SQLAlchemy
from flask import Flask, jsonify
from flask_login import LoginManager
from flask_mail import Mail
from app.config import Config
import sentry_sdk
from sentry_sdk.integrations.flask import FlaskIntegration
from sentry_sdk.integrations.sqlalchemy import SqlalchemyIntegration


db = SQLAlchemy()
mail = Mail()
login_manager = LoginManager()


### Application Factory ###
def create_app():
    app = Flask(__name__)

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
    from app.blueprints.assignments import assignments_blueprint
    from app.blueprints.auth import auth_blueprint
    from app.blueprints.docs import docs_blueprint
    from app.blueprints.enumerators import enumerators_blueprint
    from app.blueprints.misc import misc_blueprint
    from app.blueprints.profile import profile_blueprint
    from app.blueprints.survey_forms import survey_forms_blueprint
    from app.blueprints.targets import targets_blueprint
    from app.blueprints.surveys import surveys_blueprint

    app.register_blueprint(assignments_blueprint)
    app.register_blueprint(auth_blueprint)
    app.register_blueprint(docs_blueprint)
    app.register_blueprint(enumerators_blueprint)
    app.register_blueprint(misc_blueprint)
    app.register_blueprint(profile_blueprint)
    app.register_blueprint(survey_forms_blueprint)
    app.register_blueprint(targets_blueprint)

    app.register_blueprint(surveys_blueprint)


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
