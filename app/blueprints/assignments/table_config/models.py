from app import db
from app.blueprints.forms.models import ParentForm
from sqlalchemy import CheckConstraint


class TableConfig(db.Model):
    """
    SQLAlchemy data model for Table Config
    Description: This table contains the column configurations for the assignments module tables
    """

    __tablename__ = "assignments_table_config"

    form_uid = db.Column(
        db.Integer(), db.ForeignKey(ParentForm.form_uid), nullable=False
    )
    table_name = db.Column(
        db.String(),
        CheckConstraint(
            "table_name IN ('assignments_main','assignments_surveyors','assignments_review', 'surveyors', 'targets')",
            name="ck_assignments_table_config_table_name",
        ),
        nullable=False,
    )
    group_label = db.Column(db.String())
    column_label = db.Column(db.String(), nullable=False)
    column_key = db.Column(db.String(), nullable=False)
    column_order = db.Column(db.Integer(), nullable=False)

    __table_args__ = (
        db.PrimaryKeyConstraint("form_uid", "table_name", "column_key"),
        {"schema": "webapp"},
    )
