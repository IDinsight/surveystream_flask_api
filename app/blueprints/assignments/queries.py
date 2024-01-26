from app import db
from .models import SurveyorAssignment
from app.blueprints.targets.models import TargetStatus
from app.blueprints.enumerators.models import SurveyorForm
from sqlalchemy.sql.functions import func
from sqlalchemy import case, or_


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
