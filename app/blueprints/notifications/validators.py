from flask_wtf import FlaskForm
from wtforms import IntegerField, StringField
from wtforms.validators import AnyOf, DataRequired


class GetNotificationsQueryValidator(FlaskForm):
    class Meta:
        csrf = False

    user_uid = StringField(validators=[DataRequired()])


class PostNotificationsPayloadValidator(FlaskForm):

    def __init__(self, type=None, *args, **kwargs):
        super(PostNotificationsPayloadValidator, self).__init__(*args, **kwargs)
        if type == "survey":
            self.survey_uid.validators = [DataRequired()]
            self.module_id.validators = [DataRequired()]
        else:
            self.survey_uid.validators = []
            self.survey_uid.default = None
            self.module_id.validators = []
            self.module_id.default = None
        if type == "user":
            self.user_uid.validators = [DataRequired()]
        else:
            self.user_uid.validators = []
            self.user_uid.default = None

    survey_uid = IntegerField()
    module_id = IntegerField()
    user_uid = IntegerField()
    type = StringField(
        validators=[
            DataRequired(),
            AnyOf(
                ["user", "survey"],
                message="Invalid Notification type, valid values are user, survey",
            ),
        ],
    )
    severity = StringField(
        validators=[
            DataRequired(),
            AnyOf(
                ["alert", "warning", "error"],
                message="Invalid Notification severity, valid values are alert, warning, error",
            ),
        ],
        default="alert",
    )
    resolution_status = StringField(
        validators=[
            AnyOf(
                ["in progress", "done"],
                message="Invalid Resolution Status valid values are in progress, done",
            ),
        ]
    )
    message = StringField(validators=[DataRequired()])


class PutNotificationsPayloadValidator(FlaskForm):

    notification_uid = IntegerField(validators=[DataRequired()])
    type = StringField(
        validators=[
            DataRequired(),
            AnyOf(
                ["user", "survey"],
                message="Invalid Notification type, valid values are user, survey",
            ),
        ],
    )
    severity = StringField(
        validators=[
            DataRequired(),
            AnyOf(
                ["alert", "warning", "error"], message="Invalid Notification severity"
            ),
        ],
        default="alert",
    )
    resolution_status = StringField(
        validators=[
            AnyOf(["in progress", "done"], message="Invalid Resolution Status"),
        ]
    )
    message = StringField(validators=[DataRequired()])
