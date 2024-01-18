from flask_wtf import FlaskForm
from wtforms import FieldList, FormField, IntegerField, StringField
from wtforms.validators import DataRequired, ValidationError, InputRequired

from app.blueprints.roles.models import Permission

class SurveyRolesQueryParamValidator(FlaskForm):
    class Meta:
        csrf = False

    survey_uid = IntegerField(validators=[DataRequired()])

class SurveyRoleValidator(FlaskForm):
    class Meta:
        csrf = False

    role_uid = IntegerField()
    role_name = StringField(validators=[DataRequired()])
    reporting_role_uid = IntegerField()
    permissions = FieldList(IntegerField(validators=[DataRequired()]))

    def validate_permissions(form, field):
        # Ensure that field.data is a list
        if not isinstance(field.data, list):
            raise ValidationError("Permissions must be provided as a list")

        all_permission_ids = Permission.query.with_entities(Permission.permission_uid).all()
        all_permission_ids = [permission_uid[0] for permission_uid in all_permission_ids]

        seen_permission_ids = set()

        for permission_id in field.data:
            if not isinstance(permission_id, int):
                raise ValidationError(f"Invalid permission ID: {permission_id} in role {form.role_name.data}")

            if permission_id in seen_permission_ids:
                raise ValidationError(f"Duplicate permission ID: {permission_id} in role {form.role_name.data}")
            seen_permission_ids.add(permission_id)

            if permission_id not in all_permission_ids:
                raise ValidationError(f"Invalid permission ID: {permission_id} in role {form.role_name.data}")
class SurveyRolesPayloadValidator(FlaskForm):
    roles = FieldList(FormField(SurveyRoleValidator))
