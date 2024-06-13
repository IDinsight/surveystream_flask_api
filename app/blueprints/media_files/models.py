from app import db
from app.blueprints.forms.models import Form
from sqlalchemy import CheckConstraint
from sqlalchemy.ext.mutable import MutableDict
from sqlalchemy.dialects.postgresql import JSONB, ARRAY


class MediaFilesConfig(db.Model):
    __tablename__ = "media_files_config"

    __table_args__ = (
        db.UniqueConstraint(
            "form_uid",
            "file_type",
            "source",
            name="_media_files_config_form_uid_file_type_source_uc",
        ),
        {
            "schema": "webapp",
        },
    )

    media_files_config_uid = db.Column(
        db.Integer(), primary_key=True, autoincrement=True
    )

    form_uid = db.Column(db.Integer(), db.ForeignKey(Form.form_uid), nullable=False)
    file_type = db.Column(
        db.String(),
        CheckConstraint(
            "file_type IN ('audio','photo')",
            name="ck_media_files_config_file_type",
        ),
        nullable=False,
    )
    source = db.Column(
        db.String(),
        CheckConstraint(
            "source IN ('SurveyCTO','Exotel')",
            name="ck_media_files_config_source",
        ),
        server_default="SurveyCTO",
        nullable=False,
    )
    scto_fields = db.Column(db.ARRAY(db.String()))
    mapping_criteria = db.Column(
        db.String(),
        CheckConstraint(
            "mapping_criteria IN ('location','language')",
            name="ck_media_files_config_mapping_criteria",
        ),
    )

    def __init__(self, form_uid, file_type, source, scto_fields, mapping_criteria):
        self.form_uid = form_uid
        self.file_type = file_type
        self.source = source
        self.scto_fields = scto_fields
        self.mapping_criteria = mapping_criteria

    def to_dict(self):
        return {
            "media_files_config_uid": self.media_files_config_uid,
            "form_uid": self.form_uid,
            "file_type": self.file_type,
            "source": self.source,
            "scto_fields": self.scto_fields,
            "mapping_criteria": self.mapping_criteria,
        }
