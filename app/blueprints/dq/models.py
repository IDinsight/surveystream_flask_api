from sqlalchemy import CheckConstraint

from app import db
from app.blueprints.forms.models import Form


class DQCheckTypes(db.Model):
    __tablename__ = "dq_check_types"

    type_id = db.Column(db.Integer(), primary_key=True)

    name = db.Column(
        db.String(),
        nullable=False,
    )
    abbr = db.Column(db.ARRAY(db.String), nullable=False)

    __table_args__ = {"schema": "webapp"}

    def to_dict(self):
        return {
            "type_id": self.type_id,
            "name": self.name,
            "abbr": self.abbr,
        }


class DQConfig(db.Model):
    __tablename__ = "dq_config"

    form_uid = db.Column(
        db.Integer(), db.ForeignKey(Form.form_uid, ondelete="CASCADE"), nullable=False
    )
    survey_status_filter = db.Column(db.ARRAY(db.Integer), nullable=False)
    group_by_module_name = db.Column(db.Boolean(), nullable=False, default=False)

    __table_args__ = (
        db.PrimaryKeyConstraint("form_uid"),
        {"schema": "webapp"},
    )


class DQCheck(db.Model):
    __tablename__ = "dq_checks"

    dq_check_uid = db.Column(db.Integer(), primary_key=True, autoincrement=True)

    form_uid = db.Column(
        db.Integer(), db.ForeignKey(Form.form_uid, ondelete="CASCADE"), nullable=False
    )

    type_id = db.Column(
        db.Integer(),
        db.ForeignKey(DQCheckTypes.type_id, ondelete="CASCADE"),
        nullable=False,
    )
    all_questions = db.Column(db.Boolean(), default=False, nullable=False)

    question_name = db.Column(db.String(), nullable=True)
    dq_scto_form_uid = db.Column(
        db.Integer(), db.ForeignKey(Form.form_uid, ondelete="CASCADE"), nullable=True
    )

    module_name = db.Column(db.String(), nullable=True)
    flag_description = db.Column(db.String(), nullable=True)

    check_components = db.Column(
        db.JSON(), nullable=False
    )  # JSON field to store check specific components

    active = db.Column(db.Boolean(), default=True, nullable=False)

    __table_args__ = {"schema": "webapp"}

    def __init__(
        self,
        form_uid,
        type_id,
        all_questions,
        question_name,
        dq_scto_form_uid,
        module_name,
        flag_description,
        check_components,
        active,
    ):
        self.form_uid = form_uid
        self.type_id = type_id
        self.all_questions = all_questions
        self.question_name = question_name
        self.dq_scto_form_uid = dq_scto_form_uid
        self.module_name = module_name
        self.flag_description = flag_description
        self.check_components = check_components
        self.active = active

    def to_dict(self):
        return {
            "dq_check_uid": self.dq_check_uid,
            "form_uid": self.form_uid,
            "type_id": self.type_id,
            "all_questions": self.all_questions,
            "question_name": self.question_name,
            "dq_scto_form_uid": self.dq_scto_form_uid,
            "module_name": self.module_name,
            "flag_description": self.flag_description,
            "check_components": self.check_components,
            "active": self.active,
        }


class DQCheckFilters(db.Model):
    __tablename__ = "dq_check_filters"

    filter_uid = db.Column(db.Integer(), primary_key=True, autoincrement=True)

    dq_check_uid = db.Column(
        db.Integer(),
        db.ForeignKey(DQCheck.dq_check_uid, ondelete="CASCADE"),
        primary_key=True,
    )

    filter_group_id = db.Column(db.Integer(), primary_key=True)

    question_name = db.Column(db.String(), nullable=False)
    filter_operator = db.Column(
        db.String(),
        CheckConstraint(
            "filter_operator IN ('Is','Is not','Contains','Does not contain','Is Empty','Is not empty', 'Greater than', 'Smaller than')",
            name="ck_dq_check_filters_filter_operator",
        ),
        nullable=False,
    )
    filter_value = db.Column(db.Text(), nullable=True)

    __table_args__ = {"schema": "webapp"}

    def __init__(
        self,
        dq_check_uid,
        filter_group_id,
        question_name,
        filter_operator,
        filter_value,
    ):
        self.dq_check_uid = dq_check_uid
        self.filter_group_id = filter_group_id
        self.question_name = question_name
        self.filter_operator = filter_operator
        self.filter_value = filter_value

    def to_dict(self):
        return {
            "filter_group_id": self.filter_group_id,
            "question_name": self.question_name,
            "filter_operator": self.filter_operator,
            "filter_value": self.filter_value,
        }
