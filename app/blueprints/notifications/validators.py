from flask_wtf import FlaskForm
from wtforms import IntegerField, StringField
from wtforms.validators import AnyOf, DataRequired


class GetNotificationsQueryValidator(FlaskForm):
    class Meta:
        csrf = False

    user_uid = StringField(validators=[DataRequired()])


class PostNotificationsPayloadValidator(FlaskForm):

    def validate(self):
        if not (self.user_uid.data or (self.survey_uid.data and self.module_id.data)):
            self.user_uid.errors = list(self.user_uid.errors)
            self.user_uid.errors.append(
                "Either user_uid must be present or both survey_uid and module_id "
                "must be present."
            )
            return False
        return super().validate()

    user_uid = IntegerField(default=None)
    survey_uid = IntegerField(default=None)
    module_id = IntegerField(default=None)

    notification_type = StringField(
        validators=[
            DataRequired(),
            AnyOf(["alert", "warning", "error"], message="Invalid Notification Type"),
        ],
        default="alert",
    )
    notification_status = StringField(
        validators=[
            AnyOf(["in progress", "done"], message="Invalid Notification Status"),
        ]
    )
    notification_message = StringField(validators=[DataRequired()])


class PutNotificationsPayloadValidator(FlaskForm):

    def validate(self):
        if not (self.user_notification_uid.data or self.survey_notification_uid.data):
            self.user_notification_uid.errors = list(self.user_notification_uid.errors)
            self.user_notification_uid.errors.append(
                "Either user_notification_uid must be present "
                "Or survey_notification_uid be present."
            )
            return False
        return super().validate()

    user_notification_uid = IntegerField(default=None)
    survey_notification_uid = IntegerField(default=None)

    notification_type = StringField(
        validators=[
            DataRequired(),
            AnyOf(["alert", "warning", "error"], message="Invalid Notification Type"),
        ],
        default="alert",
    )
    notification_status = StringField(
        validators=[
            AnyOf(["in progress", "done"], message="Invalid Notification Status"),
        ]
    )
    notification_message = StringField(validators=[DataRequired()])
