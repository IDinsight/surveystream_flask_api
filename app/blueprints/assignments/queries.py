from app import db
from .models import SurveyorAssignment
from app.blueprints.targets.models import TargetStatus
from app.blueprints.enumerators.models import SurveyorForm
from app.blueprints.forms.models import ParentForm
from sqlalchemy.sql.functions import func
from sqlalchemy import case, or_, cast


def build_assignment_status_subquery(form_uid):
    """
    Build a subquery at the enumerator level for a given form with assignment status counts:
    total pending, total complete, total assigned

    The result will only include enumerators that have been assigned a target on the given form
    """

    assignment_status_subquery = (
        db.session.query(
            SurveyorForm.enumerator_uid,
            func.count(
                case(
                    [
                        (
                            or_(
                                TargetStatus.target_assignable.is_(True),
                                TargetStatus.target_assignable.is_(None),
                            ),
                            1,
                        )
                    ]
                )
            ).label("total_pending_targets"),
            func.count(
                case(
                    [
                        (
                            TargetStatus.target_assignable.is_(False),
                            1,
                        )
                    ]
                )
            ).label("total_completed_targets"),
            func.count(
                case(
                    [
                        (
                            or_(
                                TargetStatus.target_assignable.is_(True),
                                TargetStatus.target_assignable.is_(False),
                                TargetStatus.target_assignable.is_(None),
                            ),
                            1,
                        )
                    ]
                )
            ).label("total_assigned_targets"),
        )
        .join(
            SurveyorAssignment,
            SurveyorForm.enumerator_uid == SurveyorAssignment.enumerator_uid,
        )
        .outerjoin(
            TargetStatus, SurveyorAssignment.target_uid == TargetStatus.target_uid
        )
        .filter(SurveyorForm.form_uid == form_uid)
        .group_by(SurveyorForm.enumerator_uid)
        .subquery()
    )

    return assignment_status_subquery


def build_surveyor_formwise_productivity_subquery(survey_uid):
    """
    Build a subquery at the enumerator level with assignment status counts for each form in the survey:
    total pending, total complete, total assigned

    The result will only include enumerators that have been assigned a target on the given forms
    """

    assignment_status_subquery = (
        db.session.query(
            SurveyorForm.enumerator_uid,
            SurveyorForm.form_uid,
            func.count(
                case(
                    [
                        (
                            or_(
                                TargetStatus.target_assignable.is_(True),
                                TargetStatus.target_assignable.is_(None),
                            ),
                            1,
                        )
                    ]
                )
            ).label("total_pending_targets"),
            func.count(
                case(
                    [
                        (
                            TargetStatus.target_assignable.is_(False),
                            1,
                        )
                    ]
                )
            ).label("total_completed_targets"),
            func.count(
                case(
                    [
                        (
                            or_(
                                TargetStatus.target_assignable.is_(True),
                                TargetStatus.target_assignable.is_(False),
                                TargetStatus.target_assignable.is_(None),
                            ),
                            1,
                        )
                    ]
                )
            ).label("total_assigned_targets"),
        )
        .join(
            ParentForm,
            SurveyorForm.form_uid == ParentForm.form_uid,
        )
        .join(
            SurveyorAssignment,
            SurveyorForm.enumerator_uid == SurveyorAssignment.enumerator_uid,
        )
        .outerjoin(
            TargetStatus, SurveyorAssignment.target_uid == TargetStatus.target_uid
        )
        .filter(ParentForm.survey_uid == survey_uid)
        .group_by(SurveyorForm.enumerator_uid, SurveyorForm.form_uid)
        .subquery()
    )

    # Create the final subquery at the enumerator level
    surveyor_formwise_productivity_subquery = (
        db.session.query(
            SurveyorForm.enumerator_uid,
            func.jsonb_object_agg(
                ParentForm.scto_form_id,
                func.jsonb_build_object(
                    "form_name",
                    ParentForm.form_name,
                    "scto_form_id",
                    ParentForm.scto_form_id,
                    "total_assigned_targets",
                    func.coalesce(
                        cast(
                            assignment_status_subquery.c.total_assigned_targets,
                            db.Integer(),
                        ),
                        0,
                    ),
                    "total_pending_targets",
                    func.coalesce(
                        cast(
                            assignment_status_subquery.c.total_pending_targets,
                            db.Integer(),
                        ),
                        0,
                    ),
                    "total_completed_targets",
                    func.coalesce(
                        cast(
                            assignment_status_subquery.c.total_completed_targets,
                            db.Integer(),
                        ),
                        0,
                    ),
                ),
            ).label("form_productivity"),
        )
        .join(ParentForm, SurveyorForm.form_uid == ParentForm.form_uid)
        .outerjoin(
            assignment_status_subquery,
            (SurveyorForm.enumerator_uid == assignment_status_subquery.c.enumerator_uid)
            & (SurveyorForm.form_uid == assignment_status_subquery.c.form_uid),
        )
        .filter(ParentForm.survey_uid == survey_uid)
        .group_by(SurveyorForm.enumerator_uid)
        .subquery()
    )

    return surveyor_formwise_productivity_subquery
