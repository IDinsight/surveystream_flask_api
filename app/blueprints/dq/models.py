from sqlalchemy import CheckConstraint

from app import db
from app.blueprints.forms.models import Form


class DQCheckTypes(db.Model):
    __tablename__ = "dq_check_types"

    type_id = db.Column(db.Integer(), primary_key=True)

    name = db.Column(
        db.String(),
        primary_key=True,
        nullable=False,
    )
    abbr = db.Column(db.ARRAY(db.String), nullable=False)

    __table_args__ = {"schema": "webapp"}


class DQConfig(db.Model):
    __tablename__ = "dq_config"

    form_uid = db.Column(
        db.Integer(), db.ForeignKey(Form.form_uid, ondelete="CASCADE"), nullable=False
    )
    survey_status_filter = db.Column(db.ARRAY(db.Integer), nullable=False)

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

    question_name = db.Column(db.String(), nullable=False)
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
    is_repeat_group = db.Column(db.Boolean(), nullable=False)

    filter_operator = db.Column(
        db.String(),
        CheckConstraint(
            "filter_operator IN ('Is','Is not','Contains','Does not contain','Is Empty','Is not empty', 'Greather than', 'Smaller than')",
            name="ck_dq_check_filters_filter_operator",
        ),
        nullable=False,
    )
    filter_value = db.Column(db.Text(), nullable=True)

    __table_args__ = {"schema": "webapp"}
