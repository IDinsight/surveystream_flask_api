from flask_wtf import FlaskForm
from wtforms import IntegerField, StringField
from wtforms.validators import AnyOf, DataRequired


class GetNotificationsQueryValidator(FlaskForm):
    class Meta:
        csrf = False

    user_uid = StringField(validators=[DataRequired()])


class PostSurveyNotificationsPayloadValidator(FlaskForm):

    survey_uid = IntegerField(validators=[DataRequired()])
    module_id = IntegerField(validators=[DataRequired()])
    type = StringField(
        validators=[
            DataRequired(),
            AnyOf(["alert", "warning", "error"], message="Invalid Notification Type"),
        ],
        default="alert",
    )
    resolution_status = StringField(
        validators=[
            AnyOf(["in progress", "done"], message="Invalid Resolution Status"),
        ]
    )
    message = StringField(validators=[DataRequired()])


class PostUserNotificationsPayloadValidator(FlaskForm):

    user_uid = IntegerField(validators=[DataRequired()])
    type = StringField(
        validators=[
            DataRequired(),
            AnyOf(["alert", "warning", "error"], message="Invalid Notification Type"),
        ],
        default="alert",
    )
    resolution_status = StringField(
        validators=[
            AnyOf(["in progress", "done"], message="Invalid Resolution Status"),
        ]
    )
    message = StringField(validators=[DataRequired()])


class PutNotificationsPayloadValidator(FlaskForm):

    notification_uid = IntegerField(validators=[DataRequired()])
    type = StringField(
        validators=[
            DataRequired(),
            AnyOf(["alert", "warning", "error"], message="Invalid Notification Type"),
        ],
        default="alert",
    )
    resolution_status = StringField(
        validators=[
            AnyOf(["in progress", "done"], message="Invalid Resolution Status"),
        ]
    )
    message = StringField(validators=[DataRequired()])
