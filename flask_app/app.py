from functools import wraps
import json
import os

from datetime import timedelta
from flask_app.utils import (
    get_postgres_uri,
    concat_names,
    create_ssh_connection_object,
    safe_isoformat,
    get_aws_secret,
    safe_get_dict_value,
)
from sshtunnel import HandlerSSHTunnelForwarderError
import wtforms_json
from boto3 import client as boto3_client
from werkzeug.utils import secure_filename
from flask import Flask, jsonify, request, make_response, session
from flask_login import (
    LoginManager,
    current_user,
    login_required,
    login_user,
    logout_user,
)
from flask_mail import Mail, Message
from flask_wtf.csrf import generate_csrf
from passlib.pwd import genword

from flask_app.database import db
from sqlalchemy.dialects.postgresql import insert as pg_insert
from flask_app.queries.helper_queries import (
    build_survey_query,
    build_user_level_query,
)
from flask_app.queries.method_level_queries import (
    build_get_enumerators_query,
    build_get_targets_query,
    build_get_assignments_query,
    build_get_assignment_surveyors_query,
)
from flask_app.models.data_models import (
    ResetPasswordToken,
    User,
    Survey,
    AdminForm,
    ParentForm,
    ChildForm,
    UserHierarchy,
    SurveyorAssignment,
    Target,
    TargetStatus,
    SurveyorForm,
    TableConfig,
)
from flask_app.models.form_models import (
    ChangePasswordForm,
    ForgotPasswordForm,
    RegisterForm,
    WelcomeUserForm,
    LoginForm,
    ResetPasswordForm,
    UpdateSurveyorFormStatusForm,
    UpdateSurveyorAssignmentsForm,
    UpdateUserProfileForm,
    UploadUserAvatarForm,
    RemoveUserAvatarForm,
)
from sqlalchemy import or_
from flask_redoc import Redoc
from surveys import survey_bp
from module_questionnaire import module_questionnaire_bp
from module_selection import module_selection_bp

dod_app = Flask(__name__)

dod_app.register_blueprint(survey_bp)
dod_app.register_blueprint(module_questionnaire_bp)
dod_app.register_blueprint(module_selection_bp)

##############################################################################
# SET GLOBALS
##############################################################################

CONFIG_MODE = os.getenv("CONFIG_MODE")
REACT_BASE_URL = os.getenv("REACT_BASE_URL")
S3_REGION = os.getenv(
    "S3_REGION"
)  # Can we get rid of this if all the AWS roles and resources are in the same region?

if CONFIG_MODE in ["REMOTE_DEV", "STAGING", "PROD_NEW", "TEST_E2E"]:
    S3_BUCKET_NAME = get_aws_secret("web-assets-bucket-name", S3_REGION)
else:
    S3_BUCKET_NAME = os.getenv("S3_BUCKET_NAME")


##############################################################################
# DOCUMENTATION SETUP
##############################################################################

if CONFIG_MODE not in ["PRODUCTION", "PROD_NEW"]:
    dod_app.config["REDOC"] = {"spec_route": "/api/docs"}
    redoc = Redoc(dod_app, "openapi/surveystream.yml")

##############################################################################
# LOAD COMPONENTS
##############################################################################


def setup():
    if CONFIG_MODE in ["REMOTE_DEV", "STAGING", "PROD_NEW", "TEST_E2E"]:
        dod_app.config["SECRET_KEY"] = json.loads(
            get_aws_secret("flask-secret-key", S3_REGION)
        )[
            "SECRET_KEY"
        ]  # can we store this as text instead so we don't need to parse json?
    else:
        dod_app.config["SECRET_KEY"] = json.loads(
            get_aws_secret("dod-flask-secret-key", S3_REGION)
        )["secret_key"]

    dod_app.config["SQLALCHEMY_ENGINE_OPTIONS"] = {
        "pool_pre_ping": True,
        "pool_recycle": 300,
    }

    if CONFIG_MODE == "PRODUCTION":
        db_secret = json.loads(get_aws_secret("dod-airflow-dod-data-db", S3_REGION))

        PG_ENDPOINT = db_secret["host"]
        PG_PORT = 5432
        PG_DATABASE = db_secret["dbname"]
        PG_USERNAME = db_secret["username"]
        PG_PASSWORD = db_secret["password"]

        DB_URI = get_postgres_uri(
            PG_ENDPOINT, PG_PORT, PG_DATABASE, PG_USERNAME, PG_PASSWORD
        )

    elif CONFIG_MODE in ["STAGING", "PROD_NEW"]:
        db_secret = json.loads(get_aws_secret("data-db-connection-details", S3_REGION))

        PG_ENDPOINT = db_secret["host"]
        PG_PORT = 5432
        PG_DATABASE = db_secret["dbname"]
        PG_USERNAME = db_secret["username"]
        PG_PASSWORD = db_secret["password"]

        DB_URI = get_postgres_uri(
            PG_ENDPOINT, PG_PORT, PG_DATABASE, PG_USERNAME, PG_PASSWORD
        )

    elif CONFIG_MODE == "REMOTE_DEV":
        db_secret = json.loads(get_aws_secret("data-db-connection-details", S3_REGION))

        PG_ENDPOINT = "host.docker.internal"
        PG_PORT = 5432
        PG_DATABASE = db_secret["dbname"]
        PG_USERNAME = db_secret["username"]
        PG_PASSWORD = db_secret["password"]

        DB_URI = get_postgres_uri(
            PG_ENDPOINT, PG_PORT, PG_DATABASE, PG_USERNAME, PG_PASSWORD
        )

    elif CONFIG_MODE == "TEST_E2E":
        PG_ENDPOINT = "postgres"
        PG_PORT = 5433
        PG_DATABASE = "dod"
        PG_USERNAME = "test_user"
        PG_PASSWORD = "dod"

        DB_URI = get_postgres_uri(
            PG_ENDPOINT, PG_PORT, PG_DATABASE, PG_USERNAME, PG_PASSWORD
        )

    dod_app.config["SQLALCHEMY_DATABASE_URI"] = DB_URI
    dod_app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False
    db.init_app(dod_app)

    ### MAIL SETUP
    dod_app.config["MAIL_SERVER"] = "smtp.sendgrid.net"
    dod_app.config["MAIL_PORT"] = 587
    dod_app.config["MAIL_USERNAME"] = "apikey"
    dod_app.config["MAIL_USE_TLS"] = True
    dod_app.config["MAIL_DEFAULT_SENDER"] = "surveystream@idinsight.org"

    if CONFIG_MODE in ["REMOTE_DEV", "STAGING", "PROD_NEW", "TEST_E2E"]:
        dod_app.config["MAIL_PASSWORD"] = get_aws_secret(
            "sendgrid-api-key", S3_REGION, is_global_secret=True
        )
    else:
        dod_app.config["MAIL_PASSWORD"] = get_aws_secret(
            "dod-sendgrid-api-key", S3_REGION
        )

    # WTFORMS JSON
    wtforms_json.init()


setup()
mail = Mail(dod_app)

##############################################################################
# S3 SETUP
##############################################################################

s3 = boto3_client("s3", S3_REGION)

def get_s3_presigned_url(filekey):
    return s3.generate_presigned_url(
        "get_object", Params={"Bucket": S3_BUCKET_NAME, "Key": filekey}, ExpiresIn=60
    )


##############################################################################
# DEFINE ERROR HANDLERS
##############################################################################


@dod_app.errorhandler(401)
def unauthorized(e):
    return jsonify(message=str(e)), 401


@dod_app.errorhandler(403)
def forbidden(e):
    return jsonify(message=str(e)), 403


@dod_app.errorhandler(404)
def page_not_found(e):
    return jsonify(message=str(e)), 404


@dod_app.errorhandler(500)
def internal_server_error(e):
    return jsonify(message=str(e)), 500


##############################################################################
# AUTHENTICATION SETUP
##############################################################################

login_manager = LoginManager()
login_manager.init_app(dod_app)


def logged_in_active_user_required(f):
    """
    Login required middlerware
    Checks additional active user logic. Otherwise pass flow to built-in login_required (Flask-Login) decorator
    """

    @wraps(f)
    def decorated_function(*args, **kwargs):
        if "_user_id" in session:
            user_uid = session.get("_user_id")

            if user_uid is not None:
                user = (
                    db.session.query(User)
                    .filter(User.user_uid == user_uid)
                    .one_or_none()
                )
                if user.is_active() is False:
                    return jsonify(message="INACTIVE_USER"), 403

        return login_required(f)(*args, **kwargs)

    return decorated_function


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


##############################################################################
# INTERNAL ENDPOINTS
##############################################################################


@dod_app.route("/api/healthcheck", methods=["GET"])
def healthcheck():
    """
    Check if flask_app can connect to DB
    """
    try:
        db.session.execute("SELECT 1;")
        return jsonify(message="Healthy"), 200
    except:
        return jsonify(message="Failed DB connection"), 500


@dod_app.route("/api/get-csrf", methods=["GET"])
def set_xsrf_cookie():
    """
    Sets CSRF-TOKEN cookie
    """
    response = make_response(jsonify({"message": "Success"}), 200)
    response.set_cookie("CSRF-TOKEN", generate_csrf())
    return response


##############################################################################
# LOGIN / LOGOUT
##############################################################################


@dod_app.route("/api/register", methods=["POST"])
@logged_in_active_user_required
def register():
    """
    Endpoint to register users
    Requires JSON body with following keys:
    - email
    - password
    Requires X-CSRF-Token in header, obtained from cookie set by /get-csrf
    """

    form = RegisterForm.from_json(request.get_json())
    if "X-CSRF-Token" in request.headers:
        form.csrf_token.data = request.headers.get("X-CSRF-Token")
    else:
        return jsonify(message="X-CSRF-Token required in header"), 403

    if form.validate():
        if current_user.email == "registration_user":
            user_with_email = User.query.filter_by(email=form.email.data).first()
            if not user_with_email:
                User(form.email.data, form.password.data)
                return jsonify(message="Success: registered"), 200
            else:
                return jsonify(message="User already exists with email"), 422
        else:
            return jsonify(message="Unauthorized"), 401
    else:
        return jsonify(message=form.errors), 422


@dod_app.route("/api/login", methods=["POST"])
def login():
    """
    Endpoint to login

    Requires JSON body with following keys:
    - email
    - password

    Requires X-CSRF-Token in header, obtained from cookie set by /get-csrf
    """

    form = LoginForm.from_json(request.get_json())
    if "X-CSRF-Token" in request.headers:
        form.csrf_token.data = request.headers.get("X-CSRF-Token")
    else:
        return jsonify(message="X-CSRF-Token required in header"), 403

    if form.validate():
        user = User.query.filter_by(email=form.email.data).first()

        if user:
            if not user.is_active():
                return jsonify(message="INACTIVE_USER"), 403

            if user.verify_password(form.password.data):
                login_user(user, remember=True, duration=timedelta(days=7))
                return jsonify(message="Success: logged in"), 200
            else:
                return jsonify(message="UNAUTHORIZED"), 401
        else:
            return jsonify(message="UNAUTHORIZED"), 401

    else:
        return jsonify(message=form.errors), 422


@dod_app.route("/api/logout", methods=["GET"])
@logged_in_active_user_required
def logout():
    logout_user()
    return jsonify(message="Success: logged out"), 200


##############################################################################
# PASSWORD MANAGEMENT
##############################################################################


@dod_app.route("/api/change-password", methods=["POST"])
@logged_in_active_user_required
def change_password():
    """
    Endpoint to change password, user must be logged in

    Requires JSON body with following keys:
    - cur_password
    - new_password
    - confirm

    Requires X-CSRF-Token in header, obtained from cookie set by /get-csrf
    """
    form = ChangePasswordForm.from_json(request.get_json())
    if "X-CSRF-Token" in request.headers:
        form.csrf_token.data = request.headers.get("X-CSRF-Token")
    else:
        return jsonify(message="X-CSRF-Token required in header"), 403

    if form.validate():
        if current_user.verify_password(form.cur_password.data):
            current_user.change_password(form.new_password.data)
            return jsonify(message="Success: password changed"), 200
        else:
            return jsonify(message="Wrong password"), 403
    else:
        return jsonify(message=form.errors), 422


@dod_app.route("/api/forgot-password", methods=["POST"])
def forgot_password():
    """
    Endpoint to request reset password link by email
    User must not be logged in

    Requires JSON body with following keys:
    - email

    Requires X-CSRF-Token in header, obtained from cookie set by /get-csrf
    """
    if current_user.is_authenticated:
        return jsonify(message="Already logged in - use /change-password"), 400

    form = ForgotPasswordForm.from_json(request.get_json())
    if "X-CSRF-Token" in request.headers:
        form.csrf_token.data = request.headers.get("X-CSRF-Token")
    else:
        return jsonify(message="X-CSRF-Token required in header"), 403

    if form.validate():
        user = User.query.filter_by(email=form.email.data).first()

        if user:
            email_token = genword(length=32, charset="ascii_62")
            rpt = ResetPasswordToken(user.user_uid, email_token)

            # Add this rpt, delete all other rpts for this user
            ResetPasswordToken.query.filter_by(user_uid=user.user_uid).delete()
            db.session.add(rpt)
            db.session.commit()

            rp_message = Message(
                subject="SurveyStream Reset Password",
                html="Reset your SurveyStream password by clicking <a href='%s/reset-password/%s/%s'>here</a>.<br><br>The link will expire in one hour."
                % (REACT_BASE_URL, rpt.reset_uid, email_token),
                recipients=[user.email],
            )
            mail.send(rp_message)

        # For security, return 200/Success in any situation!
        # Don't let people figure out if they entered a valid email or not
        return jsonify(message="Request processed"), 200

    else:
        return jsonify(message=form.errors), 422


@dod_app.route("/api/welcome-user", methods=["POST"])
@logged_in_active_user_required
def welcome_user():
    """
    Endpoint to send welcome email with password reset to new user

    Requires JSON body with following keys:
    - email

    Requires X-CSRF-Token in header, obtained from cookie set by /get-csrf
    """

    form = WelcomeUserForm.from_json(request.get_json())
    if "X-CSRF-Token" in request.headers:
        form.csrf_token.data = request.headers.get("X-CSRF-Token")
    else:
        return jsonify(message="X-CSRF-Token required in header"), 403

    if form.validate():
        if current_user.email == "registration_user":
            user = User.query.filter_by(email=form.email.data).first()

            if user:
                email_token = genword(length=32, charset="ascii_62")
                rpt = ResetPasswordToken(user.user_uid, email_token)

                # Add this rpt, delete all other rpts for this user
                ResetPasswordToken.query.filter_by(user_uid=user.user_uid).delete()
                db.session.add(rpt)
                db.session.commit()

                rp_message = Message(
                    subject="Welcome to SurveyStream - Password Reset Required",
                    html="Welcome to SurveyStream! Your login email is %s. Please reset your password by clicking <a href='%s/reset-password/%s/%s'>here</a>.<br><br>The link will expire in 24 hours."
                    % (user.email, REACT_BASE_URL, rpt.reset_uid, email_token),
                    recipients=[user.email],
                )
                mail.send(rp_message)
                return jsonify(message="Request processed"), 200
            else:
                return jsonify(message="Record not found"), 404

        else:
            return jsonify(message="Unauthorized"), 401

    else:
        return jsonify(message=form.errors), 422


@dod_app.route("/api/reset-password", methods=["POST"])
def reset_password():
    """
    Endpoint to reset password
    User must not be logged in

    Requires JSON body with following keys:
    - rpt_id
    - rpt_token
    - new_password
    - confirm

    Requires X-CSRF-Token in header, obtained from cookie set by /get-csrf
    """
    if current_user.is_authenticated:
        return jsonify(message="Already logged in - use /change-password"), 400

    form = ResetPasswordForm.from_json(request.get_json())
    if "X-CSRF-Token" in request.headers:
        form.csrf_token.data = request.headers.get("X-CSRF-Token")
    else:
        return jsonify(message="X-CSRF-Token required in header"), 403

    if form.validate():
        rpt_to_check = ResetPasswordToken.query.get(form.rpt_id.data)
        if rpt_to_check and rpt_to_check.use_token(form.rpt_token.data):
            user = User.query.get(rpt_to_check.user_uid)
            user.change_password(form.new_password.data)
            db.session.delete(rpt_to_check)
            db.session.commit()
            return jsonify(message="Success: password reset"), 200
        else:
            return jsonify(message="Invalid link"), 404
    else:
        return jsonify(message=form.errors), 422


##############################################################################
# USER PROFILE
##############################################################################


@dod_app.route("/api/profile", methods=["GET"])
@logged_in_active_user_required
def view_profile():
    """
    Returns the profile of the logged in user
    """

    final_result = {
        "first_name": current_user.first_name,
        "middle_name": current_user.middle_name,
        "last_name": current_user.last_name,
        "email": current_user.email,
        "phone_primary": current_user.phone_primary,
        "home_state_name": current_user.home_state,
        "home_district_name": current_user.home_district,
    }

    return jsonify(final_result)


@dod_app.route("/api/profile", methods=["PATCH"])
@logged_in_active_user_required
def update_profile():
    """
    Updates the profile of the logged in user
    """
    form = UpdateUserProfileForm.from_json(request.get_json())

    if "X-CSRF-Token" in request.headers:
        form.csrf_token.data = request.headers.get("X-CSRF-Token")
    else:
        return jsonify(message="X-CSRF-Token required in header"), 403

    if form.validate():
        current_user.email = form.new_email.data
        db.session.commit()

        return jsonify(message="Profile updated"), 200

    else:
        return jsonify(message=form.errors), 422


@dod_app.route("/api/profile/avatar", methods=["GET"])
@logged_in_active_user_required
def view_profile_avatar():
    """
    Returns a presigned url for the profile avatar image of the logged in user
    """

    s3_filekey = current_user.avatar_s3_filekey
    if s3_filekey:
        url = get_s3_presigned_url(s3_filekey)
    else:
        url = None

    final_result = {"image_url": url}

    return jsonify(final_result)


@dod_app.route("/api/profile/avatar", methods=["PUT"])
@logged_in_active_user_required
def update_profile_avatar():
    """
    Updates the profile avatar image of the logged in user
    """
    form = UploadUserAvatarForm()

    if "X-CSRF-Token" in request.headers:
        form.csrf_token.data = request.headers.get("X-CSRF-Token")
    else:
        return jsonify(message="X-CSRF-Token required in header"), 403

    if form.validate_on_submit():
        f = form.image.data
        user_provided_filename = secure_filename(f.filename)
        extension = os.path.splitext(user_provided_filename)[1]
        s3_filekey = "images/avatars/" + str(current_user.user_uid) + extension

        s3.upload_fileobj(f, S3_BUCKET_NAME, s3_filekey)

        current_user.avatar_s3_filekey = s3_filekey
        db.session.commit()

        return jsonify(message="Success"), 200

    else:
        return jsonify(message=form.errors), 422


@dod_app.route("/api/profile/avatar/remove", methods=["POST"])
@logged_in_active_user_required
def remove_profile_avatar():
    """
    Removes the profile avatar image of the logged in user
    """
    form = RemoveUserAvatarForm()

    if "X-CSRF-Token" in request.headers:
        form.csrf_token.data = request.headers.get("X-CSRF-Token")
    else:
        return jsonify(message="X-CSRF-Token required in header"), 403

    if form.validate():
        s3.delete_object(Bucket=S3_BUCKET_NAME, Key=current_user.avatar_s3_filekey)

        current_user.avatar_s3_filekey = None
        db.session.commit()

        return jsonify(message="Success"), 200

    else:
        return jsonify(message=form.errors), 422


##############################################################################
# SURVEYS AND FORMS
##############################################################################


@dod_app.route("/api/surveys_list", methods=["GET"])
@logged_in_active_user_required
def view_surveys():
    """
    Returns survey details for a user
    """
    result = (
        db.session.query(Survey, ParentForm)
        .join(ParentForm, Survey.survey_uid == ParentForm.survey_uid, isouter=True)
        .join(UserHierarchy, Survey.survey_uid == UserHierarchy.survey_uid)
        .filter(UserHierarchy.user_uid == current_user.user_uid)
        .all()  # Switch to distinct in case a user has multiple roles for a single survey
    )

    nested_results = []
    for survey, parent_form in result:
        # Find the index of the given survey in our nested_results list
        survey_index = next(
            (
                i
                for i, item in enumerate(nested_results)
                if item["survey_id"] == survey.survey_id
            ),
            None,
        )

        if survey_index is None:
            nested_results.append(
                {
                    "survey_id": survey.survey_id,
                    "survey_name": survey.survey_name,
                    "active": survey.active,
                    "forms": [],
                }
            )

            survey_index = -1

        # We did a left join so we have to check that this survey has parent forms before appending
        if parent_form is not None:
            # Find the index of the given parent_form in our nested_results list
            parent_form_index = next(
                (
                    i
                    for i, item in enumerate(nested_results[survey_index]["forms"])
                    if item["form_name"] == parent_form.form_name
                ),
                None,
            )

            if parent_form_index is None:
                nested_results[survey_index]["forms"].append(
                    {
                        "form_uid": parent_form.form_uid,
                        "form_name": parent_form.form_name,
                        "scto_form_id": parent_form.scto_form_id,
                        "planned_start_date": safe_isoformat(
                            parent_form.planned_start_date
                        ),
                        "planned_end_date": safe_isoformat(
                            parent_form.planned_end_date
                        ),
                    }
                )

                parent_form_index = -1

    return jsonify(nested_results)


@dod_app.route("/api/forms/<form_uid>", methods=["GET"])
@logged_in_active_user_required
def view_form(form_uid):
    """
    Returns details for a parent form
    """
    parent_form_result = (
        db.session.query(ParentForm, ChildForm, Survey)
        .join(ChildForm, ParentForm.form_uid == ChildForm.parent_form_uid, isouter=True)
        .join(Survey, Survey.survey_uid == ParentForm.survey_uid, isouter=True)
        .join(UserHierarchy, Survey.survey_uid == UserHierarchy.survey_uid)
        .filter(
            ParentForm.form_uid == form_uid,
            UserHierarchy.user_uid == current_user.user_uid,
        )
        .all()
    )

    admin_form_result = (
        db.session.query(AdminForm, Survey)
        .join(Survey, Survey.survey_uid == AdminForm.survey_uid)
        .join(UserHierarchy, Survey.survey_uid == UserHierarchy.survey_uid)
        .filter(
            UserHierarchy.user_uid == current_user.user_uid,
        )
        .all()
    )

    nested_results = {}
    for parent_form, child_form, survey in parent_form_result:
        # The first time through the loop we need to populate the parent form information
        if not nested_results:
            nested_results = {
                "survey_id": survey.survey_id,
                "survey_name": survey.survey_name,
                "form_uid": parent_form.form_uid,
                "form_name": parent_form.form_name,
                "scto_form_id": parent_form.scto_form_id,
                "planned_start_date": safe_isoformat(parent_form.planned_start_date),
                "planned_end_date": safe_isoformat(parent_form.planned_end_date),
                "last_ingested_at": safe_isoformat(parent_form.last_ingested_at),
                "child_forms": [],
            }

        # We did a left join so we have to check that this parent form has child forms before appending
        if child_form is not None:
            nested_results["child_forms"].append(
                {
                    "form_type": child_form.form_type,
                    "scto_form_id": child_form.scto_form_id,
                }
            )

    for admin_form, survey in admin_form_result:
        nested_results["child_forms"].append(
            {
                "form_type": admin_form.form_type,
                "scto_form_id": admin_form.scto_form_id,
            }
        )
    return jsonify(nested_results)


##############################################################################
# ENUMERATORS
##############################################################################


@dod_app.route("/api/enumerators", methods=["GET"])
@logged_in_active_user_required
def view_enumerators():
    """
    Returns list of enumerators for a user
    """
    form_uid = request.args.get("form_uid")
    user_uid = current_user.user_uid

    result = build_get_enumerators_query(user_uid, form_uid).all()

    final_result = []

    for (
        enumerator,
        surveyor_form,
        locations,
        supervisors,
        forms,
        form_productivity,
    ) in result:
        final_result.append(
            {
                "enumerator_id": enumerator.enumerator_id,
                "enumerator_uid": enumerator.enumerator_uid,
                "name": concat_names(
                    (
                        enumerator.first_name,
                        enumerator.middle_name,
                        enumerator.last_name,
                    )
                ),
                "email": enumerator.email,
                "language": enumerator.language,
                "gender": enumerator.gender,
                "home_state": enumerator.home_address["home_state"],
                "home_district": enumerator.home_address["home_district"],
                "home_block": enumerator.home_address["home_block"],
                "home_address": enumerator.home_address["address"],
                "phone_primary": enumerator.phone_primary,
                "phone_secondary": enumerator.phone_secondary,
                "locations": locations,
                "status": surveyor_form.status,
                "supervisors": supervisors,
                "forms": forms,
                "form_productivity": form_productivity,
            }
        )

    return jsonify(final_result)


@dod_app.route("/api/enumerators/<enumerator_uid>", methods=["PATCH"])
@logged_in_active_user_required
def update_enumerator_status(enumerator_uid):
    """
    Updates the status of an enumerator
    """
    form = UpdateSurveyorFormStatusForm.from_json(request.get_json())

    if "X-CSRF-Token" in request.headers:
        form.csrf_token.data = request.headers.get("X-CSRF-Token")
    else:
        return jsonify(message="X-CSRF-Token required in header"), 403

    if form.validate():
        surveyor_form = (
            db.session.query(SurveyorForm)
            .filter(
                SurveyorForm.enumerator_uid == enumerator_uid,
                SurveyorForm.form_uid == form.form_uid.data,
            )
            .first()
        )

        if surveyor_form:
            survey_query = build_survey_query(form.form_uid.data)

            forms_in_survey_query = db.session.query(ParentForm.form_uid).filter(
                ParentForm.survey_uid.in_(survey_query.subquery())
            )

            # added user_id to show who is performing the action
            db.session.query(SurveyorForm).filter(
                SurveyorForm.enumerator_uid == enumerator_uid,
                SurveyorForm.form_uid.in_(forms_in_survey_query.subquery()),
            ).update(
                {
                    SurveyorForm.status: form.status.data,
                    SurveyorForm.user_uid: current_user.user_uid,
                },
                synchronize_session=False,
            )

            # This is special logic that says to release the surveyor's assignments
            # for all the forms in the survey if the surveyor is marked as a dropout.
            # This should be restricted to the assignable targets (i.e. not completed)
            # assignments for the surveyor

            if form.status.data == "Dropout":
                survey_query = build_survey_query(form.form_uid.data)

                # Add this query so as to capture who is deleting the Assignment
                db.session.query(SurveyorAssignment).filter(
                    SurveyorAssignment.enumerator_uid == enumerator_uid,
                    SurveyorAssignment.target_uid == Target.target_uid,
                ).update(
                    {
                        SurveyorAssignment.user_uid: current_user.user_uid,
                        SurveyorAssignment.to_delete: 1,
                    },
                    synchronize_session=False,
                )

                db.session.query(SurveyorAssignment).filter(
                    SurveyorAssignment.target_uid == Target.target_uid,
                    Target.form_uid == ParentForm.form_uid,
                    TargetStatus.target_uid == SurveyorAssignment.target_uid,
                    ParentForm.survey_uid.in_(survey_query.subquery()),
                    SurveyorAssignment.enumerator_uid == enumerator_uid,
                    or_(
                        TargetStatus.target_assignable.is_(True),
                        TargetStatus.target_assignable.is_(None),
                    ),
                ).delete(synchronize_session=False)

            db.session.commit()

            return jsonify(message="Record updated"), 200

        else:
            return jsonify(message="Record not found"), 404

    else:
        return jsonify(message=form.errors), 422


##############################################################################
# TARGETS
##############################################################################


@dod_app.route("/api/targets", methods=["GET"])
@logged_in_active_user_required
def view_targets():
    """
    Returns list of targets for a user
    """
    form_uid = request.args.get("form_uid")
    user_uid = current_user.user_uid

    result = build_get_targets_query(user_uid, form_uid).all()

    final_result = []

    for target, target_status, supervisors, locations in result:
        final_result.append(
            {
                "supervisors": supervisors,
                "locations": locations,
                "target_id": target.target_id,
                "respondent_names": target.respondent_names,
                "respondent_phone_primary": target.respondent_phone_primary,
                "respondent_phone_secondary": target.respondent_phone_secondary,
                "address": target.address,
                "gps_latitude": target.gps_latitude,
                "gps_longitude": target.gps_longitude,
                "custom_fields": target.custom_fields,
                "target_assignable": getattr(target_status, "target_assignable", None),
                "last_attempt_survey_status": getattr(
                    target_status, "last_attempt_survey_status", None
                ),
                "last_attempt_survey_status_label": getattr(
                    target_status, "last_attempt_survey_status_label", None
                ),
                "attempts": getattr(target_status, "num_attempts", None),
                "webapp_tag_color": getattr(target_status, "webapp_tag_color", None),
                "revisit_sections": getattr(target_status, "revisit_sections", None),
            }
        )

    return jsonify(final_result)


##############################################################################
# ASSIGNMENTS
##############################################################################


@dod_app.route("/api/assignments", methods=["GET"])
@logged_in_active_user_required
def view_assignments():
    """
    Returns assignment information for a user
    """

    form_uid = request.args.get("form_uid")
    user_uid = current_user.user_uid

    assignment_result = build_get_assignments_query(user_uid, form_uid).all()
    surveyor_result = build_get_assignment_surveyors_query(user_uid, form_uid).all()

    final_result = {"assignments": [], "surveyors": []}

    for (
        target,
        target_status,
        enumerator,
        locations,
        supervisors,
    ) in assignment_result:
        final_result["assignments"].append(
            {
                "assigned_enumerator_uid": getattr(enumerator, "enumerator_uid", None),
                "assigned_enumerator_id": getattr(enumerator, "enumerator_id", None),
                "assigned_enumerator_name": concat_names(
                    (
                        getattr(enumerator, "first_name", None),
                        getattr(enumerator, "middle_name", None),
                        getattr(enumerator, "last_name", None),
                    )
                ),
                "home_state": safe_get_dict_value(
                    getattr(enumerator, "home_address", None), "home_state"
                ),
                "home_district": safe_get_dict_value(
                    getattr(enumerator, "home_address", None), "home_district"
                ),
                "home_block": safe_get_dict_value(
                    getattr(enumerator, "home_address", None), "home_block"
                ),
                "locations": locations,
                "supervisors": supervisors,
                "target_id": target.target_id,
                "target_uid": target.target_uid,
                "respondent_names": target.respondent_names,
                "respondent_phone_primary": target.respondent_phone_primary,
                "respondent_phone_secondary": target.respondent_phone_secondary,
                "address": target.address,
                "gps_latitude": target.gps_latitude,
                "gps_longitude": target.gps_longitude,
                "custom_fields": target.custom_fields,
                "target_assignable": getattr(target_status, "target_assignable", None),
                "last_attempt_survey_status": getattr(
                    target_status, "last_attempt_survey_status", None
                ),
                "last_attempt_survey_status_label": getattr(
                    target_status, "last_attempt_survey_status_label", None
                ),
                "attempts": getattr(target_status, "num_attempts", None),
                "webapp_tag_color": getattr(target_status, "webapp_tag_color", None),
                "revisit_sections": getattr(target_status, "revisit_sections", None),
            }
        )

    for (
        enumerator,
        surveyor_form,
        locations,
        form_productivity,
        total_pending_targets,
        total_complete_targets,
    ) in surveyor_result:
        final_result["surveyors"].append(
            {
                "enumerator_uid": enumerator.enumerator_uid,
                "enumerator_id": enumerator.enumerator_id,
                "enumerator_name": concat_names(
                    (
                        enumerator.first_name,
                        enumerator.middle_name,
                        enumerator.last_name,
                    )
                ),
                "email": enumerator.email,
                "language": enumerator.language,
                "gender": enumerator.gender,
                "phone_primary": enumerator.phone_primary,
                "phone_secondary": enumerator.phone_secondary,
                "locations": locations,
                "home_state": enumerator.home_address["home_state"],
                "home_district": enumerator.home_address["home_district"],
                "home_block": enumerator.home_address["home_block"],
                "surveyor_status": surveyor_form.status,
                "total_pending_targets": total_pending_targets,
                "total_complete_targets": total_complete_targets,
                "form_productivity": form_productivity,
            }
        )

    return jsonify(final_result)


@dod_app.route("/api/assignments", methods=["PUT"])
@logged_in_active_user_required
def update_assignments():
    """
    Updates assignment mapping
    """
    form = UpdateSurveyorAssignmentsForm.from_json(request.get_json())

    if "X-CSRF-Token" in request.headers:
        form.csrf_token.data = request.headers.get("X-CSRF-Token")
    else:
        return jsonify(message="X-CSRF-Token required in header"), 403

    if form.validate():
        for assignment in form.assignments.data:
            if assignment["enumerator_uid"] is not None:
                # do upsert
                statement = (
                    pg_insert(SurveyorAssignment)
                    .values(
                        target_uid=assignment["target_uid"],
                        enumerator_uid=assignment["enumerator_uid"],
                        user_uid=current_user.user_uid,
                    )
                    .on_conflict_do_update(
                        constraint="surveyor_assignments_pkey",
                        set_={
                            "enumerator_uid": assignment["enumerator_uid"],
                            "user_uid": current_user.user_uid,
                        },
                    )
                )

                db.session.execute(statement)
                db.session.commit()
            else:
                db.session.query(SurveyorAssignment).filter(
                    SurveyorAssignment.target_uid == assignment["target_uid"]
                ).update(
                    {
                        SurveyorAssignment.user_uid: current_user.user_uid,
                        SurveyorAssignment.to_delete: 1,
                    },
                    synchronize_session=False,
                )

                db.session.query(SurveyorAssignment).filter(
                    SurveyorAssignment.target_uid == assignment["target_uid"]
                ).delete()
                db.session.commit()

        return jsonify(message="Success"), 200

    else:
        return jsonify(message=form.errors), 422


##############################################################################
# TABLE DEFINITIONS
##############################################################################


@dod_app.route("/api/table-config", methods=["GET"])
@logged_in_active_user_required
def view_table_config():
    """
    Returns the table definitions for the web flask_app tables
    """

    def is_excluded_supervisor(row, user_level):
        """
        Check if the table config row should be excluded because the supervisor is not at a child supervisor level for the logged in user
        """
        is_excluded_supervisor = False

        try:
            if (
                row.column_key.split(".")[0] == "supervisors"
                and int(row.column_key.split(".")[1].split("_")[1]) <= user_level
            ):
                is_excluded_supervisor = True

        except:
            pass

        return is_excluded_supervisor

    user_uid = current_user.user_uid
    form_uid = request.args.get("form_uid")

    result = (
        db.session.query(TableConfig)
        .filter(TableConfig.form_uid == form_uid)
        .order_by(TableConfig.webapp_table_name, TableConfig.column_order)
        .all()
    )

    survey_query = build_survey_query(form_uid)
    user_level = build_user_level_query(user_uid, survey_query).first().level

    table_config = {
        "surveyors": [],
        "targets": [],
        "assignments_main": [],
        "assignments_surveyors": [],
        "assignments_review": [],
    }

    for row in result:
        if is_excluded_supervisor(row, user_level):
            pass

        else:
            if row.group_label is None:
                table_config[row.webapp_table_name].append(
                    {
                        "group_label": None,
                        "columns": [
                            {
                                "column_key": row.column_key,
                                "column_label": row.column_label,
                            }
                        ],
                    }
                )

            else:
                # Find the index of the given group in our results
                group_index = next(
                    (
                        i
                        for i, item in enumerate(table_config[row.webapp_table_name])
                        if item["group_label"] == row.group_label
                    ),
                    None,
                )

                if group_index is None:
                    table_config[row.webapp_table_name].append(
                        {"group_label": row.group_label, "columns": []}
                    )
                    group_index = -1

                table_config[row.webapp_table_name][group_index]["columns"].append(
                    {"column_key": row.column_key, "column_label": row.column_label}
                )

    return jsonify(table_config)


if __name__ == "__main__":
    dod_app.run(debug=True)
