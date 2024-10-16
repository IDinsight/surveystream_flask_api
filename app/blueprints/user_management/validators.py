from flask_wtf import FlaskForm
from wtforms import (
    BooleanField,
    FieldList,
    IntegerField,
    PasswordField,
    StringField,
    validators,
)
from wtforms.validators import DataRequired, Email, Optional, ValidationError

from app.blueprints.auth.models import User
from app.blueprints.locations.models import Location
from app.blueprints.surveys.models import Survey
from app.blueprints.module_questionnaire.models import ModuleQuestionnaire
from app.blueprints.roles.models import Role
from app.blueprints.roles.utils import RoleHierarchy
from app.blueprints.roles.errors import InvalidRoleHierarchyError


class GetUsersQueryParamValidator(FlaskForm):
    class Meta:
        csrf = False

    survey_uid = IntegerField()


class RegisterValidator(FlaskForm):
    email = StringField("Email", validators=[DataRequired()])
    password = PasswordField("Password", validators=[DataRequired()])


class WelcomeUserValidator(FlaskForm):
    email = StringField("Email", validators=[DataRequired()])


class CheckUserValidator(FlaskForm):
    email = StringField("Email", validators=[DataRequired()])
    survey_uid = IntegerField("survey_uid", validators=[Optional()], default=None)


def validate_locations(form, field):
    """
    Custom validator to validate that the locations provided are prime geo level locations.
    """
    # Validate locations only if survey UID is provided and locations are provided
    if form.survey_uid.data and field.data and len(field.data) > 0:
        # Get the prime geo level from the survey configuration
        prime_geo_level_uid = (
            Survey.query.filter_by(survey_uid=form.survey_uid.data)
            .first()
            .prime_geo_level_uid
        )
        if not prime_geo_level_uid:
            raise ValidationError(
                "A prime geo level must be defined for the survey for user location mapping."
            )

        for location_uid in field.data:
            location = Location.query.get(location_uid)
            if not location:
                raise ValidationError(
                    f"Location with UID {location_uid} does not exist."
                )

            if location.geo_level_uid != prime_geo_level_uid:
                raise ValidationError(
                    f"Location with UID {location_uid} is not a prime geo level location."
                )


def validate_mapping_fields(form, field):
    """
    Custom validator to check that field needed for mapping are provided for the lowest supervisor role

    """
    user_roles = form.roles.data

    # Validate mapping fields only if survey UID is provided and user has roles
    if form.survey_uid.data and user_roles and len(user_roles) > 0:
        roles = [
            role.to_dict()
            for role in Role.query.filter_by(survey_uid=form.survey_uid.data).all()
        ]
        # Get the user's roles linked to the given survey
        user_survey_roles = [
            role["role_uid"] for role in roles if str(role["role_uid"]) in user_roles
        ]

        # Proceed only if user has survey roles
        if len(user_survey_roles) > 0:
            module_questionnaire = ModuleQuestionnaire.query.filter_by(
                survey_uid=form.survey_uid.data
            ).first()
            if (
                module_questionnaire is None
                or module_questionnaire.target_mapping_criteria is None
                or len(module_questionnaire.target_mapping_criteria) == 0
                or module_questionnaire.surveyor_mapping_criteria is None
                or len(module_questionnaire.surveyor_mapping_criteria) == 0
            ):
                raise ValidationError(
                    "No mapping criteria defined for the survey. Kindly add mapping criteria to the survey first."
                )

            try:
                roles = RoleHierarchy(roles)
            except InvalidRoleHierarchyError as e:
                raise ValidationError(e.role_hierarchy_errors)

            bottom_level_role_uid = roles.ordered_roles[-1]["role_uid"]

            # Check if the lowest supervisor role is in the user roles
            if bottom_level_role_uid in user_survey_roles:
                if field.name == "location_uids":
                    if (
                        "Location" in module_questionnaire.target_mapping_criteria
                        or "Location" in module_questionnaire.surveyor_mapping_criteria
                    ):
                        if not field.data or len(field.data) == 0:
                            raise ValidationError(
                                "Location mapping is required for the lowest supervisor role."
                            )

                if field.name == "languages":
                    if (
                        "Language" in module_questionnaire.target_mapping_criteria
                        or "Language" in module_questionnaire.surveyor_mapping_criteria
                    ):
                        if not field.data or len(field.data) == 0:
                            raise ValidationError(
                                "Language mapping is required for the lowest supervisor role."
                            )
            else:
                # If user is not the lowest supervisor role, check that language and location mapping is not provided
                if field.name == "location_uids":
                    if field.data and len(field.data) > 0:
                        raise ValidationError(
                            "Location mapping is not required for roles other than the lowest supervisor role."
                        )

                if field.name == "languages":
                    if field.data and len(field.data) > 0:
                        raise ValidationError(
                            "Language mapping is not required for roles other than the lowest supervisor role."
                        )


class AddUserValidator(FlaskForm):
    email = StringField("Email", validators=[DataRequired()])
    first_name = StringField("First Name", validators=[DataRequired()])
    last_name = StringField("Last Name", validators=[DataRequired()])
    roles = FieldList(StringField("Roles"), default=[], validators=[Optional()])

    gender = StringField("Gender", validators=[Optional()])
    languages = FieldList(
        StringField("languages"), default=[], validators=[validate_mapping_fields]
    )
    location_uids = FieldList(
        IntegerField("location_uids"),
        default=[],
        validators=[validate_locations, validate_mapping_fields],
    )

    is_super_admin = BooleanField(
        "is_super_admin", default=False, validators=[Optional()]
    )
    can_create_survey = BooleanField(
        "can_create_survey", default=False, validators=[Optional()]
    )

    is_survey_admin = BooleanField(
        "is_survey_admin", default=False, validators=[Optional()]
    )
    survey_uid = IntegerField("survey_uid", default=None)

    def validate_survey_uid(form, survey_uid):
        if form.is_survey_admin.data and not survey_uid.data:
            raise ValidationError("Survey UID is required if user is a survey admin.")

        if form.location_uids.data and not survey_uid.data:
            raise ValidationError(
                "Survey UID is required if user location mapping is provided."
            )

        if form.languages.data and not survey_uid.data:
            raise ValidationError(
                "Survey UID is required if user language mapping is provided."
            )


class EditUserValidator(FlaskForm):
    email = StringField("Email", validators=[Email(), DataRequired()])
    first_name = StringField("First Name", validators=[DataRequired()])
    last_name = StringField("Last Name", validators=[DataRequired()])
    roles = FieldList(StringField("Roles"), default=[], validators=[Optional()])
    gender = StringField("Gender", validators=[Optional()])
    languages = FieldList(
        StringField("Language"), default=[], validators=[validate_mapping_fields]
    )
    location_uids = FieldList(
        IntegerField("Location"),
        default=[],
        validators=[validate_locations, validate_mapping_fields],
    )

    is_super_admin = BooleanField(
        "Is Super Admin", default=False, validators=[Optional()]
    )
    can_create_survey = BooleanField(
        "Can Create Survey", default=False, validators=[Optional()]
    )

    is_survey_admin = BooleanField(
        "is_survey_admin", default=False, validators=[Optional()]
    )
    survey_uid = IntegerField("survey_uid", default=None)
    active = BooleanField()

    def validate_survey_uid(self, field):
        if self.is_survey_admin.data and not field.data:
            raise ValidationError("Survey UID is required if user is a survey admin.")

        if self.location_uids.data and not field.data:
            raise ValidationError(
                "Survey UID is required if user location mapping is provided."
            )

        if self.languages.data and not field.data:
            raise ValidationError(
                "Survey UID is required if user language mapping is provided."
            )


class CompleteRegistrationValidator(FlaskForm):
    invite_code = StringField("Invite Code", validators=[DataRequired()])
    new_password = PasswordField(
        "New Password", [validators.DataRequired(), validators.Length(min=8)]
    )
    confirm_password = PasswordField(
        "Confirm Password",
        [
            validators.DataRequired(),
            validators.EqualTo("new_password", message="Passwords must match"),
        ],
    )


class GetUserLocationsParamValidator(FlaskForm):
    class Meta:
        csrf = False

    survey_uid = IntegerField(validators=[DataRequired()])
    user_uid = IntegerField()


class UserLocationsParamValidator(FlaskForm):
    class Meta:
        csrf = False

    survey_uid = IntegerField(validators=[DataRequired()])
    user_uid = IntegerField(validators=[DataRequired()])


class UserLocationsPayloadValidator(FlaskForm):
    survey_uid = IntegerField(validators=[DataRequired()])
    user_uid = IntegerField(validators=[DataRequired()])
    location_uids = FieldList(
        IntegerField(), validators=[DataRequired(), validate_locations]
    )

    def validate_survey_uid(form, field):
        survey = Survey.query.get(field.data)
        if not survey:
            raise ValidationError(f"Survey with UID {field.data} does not exist.")

    def validate_user_uid(form, field):
        user = User.query.get(field.data)
        if not user:
            raise ValidationError(f"User with UID {field.data} does not exist.")


class GetUserLanguagesParamValidator(FlaskForm):
    class Meta:
        csrf = False

    survey_uid = IntegerField(validators=[DataRequired()])
    user_uid = IntegerField()


class GetUserGenderParamValidator(FlaskForm):
    class Meta:
        csrf = False

    survey_uid = IntegerField(validators=[DataRequired()])
    user_uid = IntegerField()
