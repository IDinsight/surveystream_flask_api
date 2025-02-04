from app import db
from app.blueprints.surveys.models import Survey
from sqlalchemy import CheckConstraint


class Module(db.Model):
    __tablename__ = "modules"
    __table_args__ = {
        "schema": "webapp",
    }

    module_id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String, unique=True, nullable=False)
    optional = db.Column(db.Boolean, nullable=False)

    module_status = db.relationship("ModuleStatus", back_populates="module")

    def __init__(self, name, optional):
        self.name = name
        self.optional = optional

    def to_dict(self):
        return {
            "module_id": self.module_id,
            "name": self.name,
            "optional": self.optional,
        }


class ModuleStatus(db.Model):
    __tablename__ = "module_status"
    __table_args__ = {
        "schema": "webapp",
    }

    survey_uid = db.Column(
        db.Integer, db.ForeignKey(Survey.survey_uid), primary_key=True
    )
    module_id = db.Column(db.Integer, db.ForeignKey(Module.module_id), primary_key=True)
    config_status = db.Column(
        db.String,
        CheckConstraint(
            "config_status IN ('Done','In Progress','Not Started', 'Error', 'Live')",
            name="ck_module_status_config_status",
        ),
        server_default="Not Started",
    )

    module = db.relationship(Module, back_populates="module_status")

    def __init__(self, survey_uid, module_id, config_status):
        self.survey_uid = survey_uid
        self.module_id = module_id
        self.config_status = config_status

    def to_dict(self):
        return {
            "survey_uid": self.survey_uid,
            "module_id": self.module_id,
            "config_status": self.config_status,
        }


class ModuleDependency(db.Model):
    __tablename__ = "module_dependency"
    __table_args__ = {
        "schema": "webapp",
    }

    module_id = db.Column(db.Integer, db.ForeignKey(Module.module_id), primary_key=True)
    requires_module_id = db.Column(
        db.Integer, db.ForeignKey(Module.module_id), primary_key=True
    )
    required_if = db.Column(db.ARRAY(db.String()))

    def __init__(self, module_id, requires_module_id, required_if):
        self.module_id = module_id
        self.requires_module_id = requires_module_id
        required_if = required_if

    def to_dict(self):
        return {
            "module_id": self.module_id,
            "requires_module_id": self.requires_module_id,
            "required_if": self.required_if,
        }
