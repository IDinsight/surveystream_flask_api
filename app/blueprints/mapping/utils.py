from sqlalchemy import JSON, and_, distinct, exists, func, type_coerce
from sqlalchemy.dialects.postgresql import insert as pg_insert

from app import db
from app.blueprints.forms.models import Form
from app.blueprints.module_questionnaire.models import ModuleQuestionnaire
from app.blueprints.roles.models import Role
from app.blueprints.roles.utils import InvalidRoleHierarchyError, RoleHierarchy
from app.blueprints.surveys.models import Survey
from app.blueprints.targets.models import Target

from .errors import InvalidMappingRecordsError, MappingError
from .models import UserMappingConfig, UserSurveyorMapping, UserTargetMapping
from .queries import (
    build_supervisors_with_mapping_criteria_values_subquery,
    build_targets_with_mapping_criteria_values_subquery,
)


class TargetMapping:
    """
    Class to handle the mapping of the targets to supervisors

    """

    def __init__(self, form_uid):
        self.form_uid = form_uid

        # Get basics needed for the mapping
        self.survey_uid = self.__get_survey_uid()
        try:
            self.mapping_criteria = self.__get_mapping_criteria()
            self.prime_geo_level_uid = self.__get_prime_geo_level_uid()
            self.bottom_level_role_uid = self.__get_bottom_level_role_uid()
        except:
            raise

    def __get_survey_uid(self):
        """
        Method to get the survey uid for the form

        """
        survey_uid = Form.query.filter_by(form_uid=self.form_uid).first().survey_uid
        return survey_uid

    def __get_mapping_criteria(self):
        """
        Method to get the mapping criteria for the form

        """
        module_questionnaire = ModuleQuestionnaire.query.filter_by(
            survey_uid=self.survey_uid
        ).first()
        if (
            module_questionnaire is None
            or module_questionnaire.target_mapping_criteria is None
            or len(module_questionnaire.target_mapping_criteria) == 0
        ):
            raise MappingError("Supervisor to target mapping criteria not found.")

        return module_questionnaire.target_mapping_criteria

    def __get_prime_geo_level_uid(self):
        """
        Method to get the prime geo level uid for the form

        """
        prime_geo_level_uid = (
            Survey.query.filter_by(survey_uid=self.survey_uid)
            .first()
            .prime_geo_level_uid
        )
        if "Location" in self.mapping_criteria:
            if prime_geo_level_uid is None:
                raise MappingError(
                    "Prime geo level not configured for the survey. Cannot perform supervisor to target mapping based on location without a prime geo level."
                )
        return prime_geo_level_uid

    def __get_bottom_level_role_uid(self):
        """
        Method to get the bottom level role uid for the survey

        """
        roles = [
            role.to_dict()
            for role in Role.query.filter_by(survey_uid=self.survey_uid).all()
        ]
        if not roles:
            raise MappingError(
                "Roles not configured for the survey. Cannot perform supervisor to target mapping without roles."
            )

        try:
            roles = RoleHierarchy(roles)
        except InvalidRoleHierarchyError as e:
            raise MappingError(e.role_hierarchy_errors)

        bottom_level_role_uid = roles.ordered_roles[-1]["role_uid"]
        return bottom_level_role_uid

    def get_targets_subquery(self):
        """
        Method to get the subquery for fetching targets with mapping criteria values

        Note: This query will have only one row for each target
        """
        targets_subquery = build_targets_with_mapping_criteria_values_subquery(
            self.survey_uid,
            self.form_uid,
            self.prime_geo_level_uid,
            self.mapping_criteria,
        )
        return targets_subquery

    def get_supervisors_subquery(self):
        """
        Method to get the subquery for fetching supervisors with mapping criteria values

        Note: This query can have more than one row for each supervisor

        """
        supervisors_subquery = build_supervisors_with_mapping_criteria_values_subquery(
            self.survey_uid, self.bottom_level_role_uid, self.mapping_criteria
        )
        return supervisors_subquery

    def get_mapping_config_subquery(self):
        """
        Method to get the mapping configuration subquery for the form

        Note: This should only fetch the saved custom mapping for values
        for which no supervisor exists in the system. If a supervisor exists,
        then the mapping is based on original mapping criteria values

        """
        supervisors_subquery = self.get_supervisors_subquery()

        mapping_config_subquery = db.session.query(
            UserMappingConfig.form_uid,
            UserMappingConfig.mapping_type,
            UserMappingConfig.mapping_values,
            UserMappingConfig.mapped_to,
        ).filter(
            UserMappingConfig.form_uid == self.form_uid,
            UserMappingConfig.mapping_type == "target",
            ~exists().where(
                *[
                    (
                        type_coerce(
                            supervisors_subquery.c.mapping_criteria_values, JSON
                        )[criteria]
                        == type_coerce(UserMappingConfig.mapping_values, JSON)[criteria]
                    )
                    for criteria in self.mapping_criteria
                ]
            ),
        )
        return mapping_config_subquery.subquery()

    def get_targets_with_mapped_to_subquery(self):
        """
        Method to get the subquery for fetching targets with custom mapping config values

        """

        targets_subquery = self.get_targets_subquery()
        mapping_config = self.get_mapping_config_subquery()

        targets_with_custom_mapping_subquery = db.session.query(
            targets_subquery.c.target_uid,
            targets_subquery.c.target_id,
            targets_subquery.c.gender,
            targets_subquery.c.language,
            targets_subquery.c.location_id.label("location_id"),
            targets_subquery.c.location_name.label("location_name"),
            targets_subquery.c.mapping_criteria_values.label("mapping_criteria_values"),
            func.coalesce(
                mapping_config.c.mapped_to, targets_subquery.c.mapping_criteria_values
            ).label("mapped_to_values"),
        ).outerjoin(
            mapping_config,
            and_(
                *[
                    (
                        type_coerce(mapping_config.c.mapping_values, JSON)[criteria]
                        == type_coerce(
                            targets_subquery.c.mapping_criteria_values, JSON
                        )[criteria]
                    )
                    for criteria in self.mapping_criteria
                ]
            ),
        )

        return targets_with_custom_mapping_subquery.subquery()

    def get_targets_with_invalid_mappings(self):
        """
        Function to return the target uids with invalid mappings
        In case mapping criteria values for a target/supervisor have changed, some
        saved mappings may no longer be valid. This function will return the target uids
        with invalid mappings

        """
        supervisors_subquery = self.get_supervisors_subquery()
        targets_subquery = self.get_targets_with_mapped_to_subquery()

        # Get all the saved mappings for the current form
        subquery = db.session.query(Target.target_uid).filter(
            Target.form_uid == self.form_uid
        )
        saved_mappings = UserTargetMapping.query.filter(
            UserTargetMapping.target_uid.in_(subquery)
        ).all()

        targets_with_invalid_mappings = []
        for mapping in saved_mappings:
            target_uid = mapping.target_uid
            supervisor_uid = mapping.user_uid

            # We don't need to check for deleted targets and supervisors as they will be removed
            # by delete cascades
            # Only check if the mapping holds true for the current mapping criteria values
            target = (
                db.session.query(targets_subquery)
                .filter(targets_subquery.c.target_uid == target_uid)
                .first()
            )

            supervisor = None
            if target is not None:
                # There will be only one supervisor for the specific mapping criteria values and supervisor UID
                supervisor = (
                    db.session.query(supervisors_subquery)
                    .filter(
                        supervisors_subquery.c.user_uid == supervisor_uid,
                        *[
                            (
                                type_coerce(
                                    supervisors_subquery.c.mapping_criteria_values, JSON
                                )[criteria]
                                == type_coerce(target.mapped_to_values[criteria], JSON)
                            )
                            for criteria in self.mapping_criteria
                        ],
                    )
                    .first()
                )

            # If the query returned no supervisor, then the mapping is invalid
            if supervisor is None:
                targets_with_invalid_mappings.append(target_uid)

        return targets_with_invalid_mappings

    def get_saved_mappings(self):
        """
        Method to get the saved mappings for the form. This method will only return the mappings that
        are valid based on the current mapping criteria values

        """
        supervisors_subquery = self.get_supervisors_subquery()
        targets_subquery = self.get_targets_with_mapped_to_subquery()

        # Fetch saved mappings which are valid based on the current mapping criteria values
        saved_mappings = (
            db.session.query(UserTargetMapping.target_uid, UserTargetMapping.user_uid)
            .join(
                targets_subquery,
                UserTargetMapping.target_uid == targets_subquery.c.target_uid,
            )
            .join(
                supervisors_subquery,
                and_(
                    UserTargetMapping.user_uid == supervisors_subquery.c.user_uid,
                    *[
                        (
                            type_coerce(
                                supervisors_subquery.c.mapping_criteria_values, JSON
                            )[criteria]
                            == type_coerce(targets_subquery.c.mapped_to_values, JSON)[
                                criteria
                            ]
                        )
                        for criteria in self.mapping_criteria
                    ],
                ),
            )
            .all()
        )

        return saved_mappings

    def generate_mappings(self):
        """
        Method to generate the mapping of the targets to supervisors
        This method will generate the mapping based on the mapping criteria values
        and add the saved mappings in the database for targets that could not be
        mapped automatically

        """
        supervisors_subquery = self.get_supervisors_subquery()
        targets_subquery = self.get_targets_with_mapped_to_subquery()

        # Step 1: Generate mappings for targets that can be mapped automatically

        # Only mapping criteria values with 1 supervisor can be mapped automatically
        # Hence, filter supervisors to only those mapping criteria values with 1 supervisor
        single_supervisor_per_mapping_values_subquery = (
            db.session.query(supervisors_subquery.c.mapping_criteria_values)
            .group_by(
                supervisors_subquery.c.mapping_criteria_values,
            )
            .having(func.count(distinct(supervisors_subquery.c.user_uid)) == 1)
            .subquery()
        )

        supervisors_subquery = (
            db.session.query(
                supervisors_subquery.c.user_uid,
                supervisors_subquery.c.mapping_criteria_values,
            )
            .join(
                single_supervisor_per_mapping_values_subquery,
                and_(
                    *[
                        (
                            type_coerce(
                                single_supervisor_per_mapping_values_subquery.c.mapping_criteria_values,
                                JSON,
                            )[criteria]
                            == type_coerce(
                                supervisors_subquery.c.mapping_criteria_values, JSON
                            )[criteria]
                        )
                        for criteria in self.mapping_criteria
                    ]
                ),
            )
            .subquery()
        )

        # Create mapping
        mappings = (
            db.session.query(
                targets_subquery.c.target_uid,
                supervisors_subquery.c.user_uid.label("supervisor_uid"),
            )
            .join(
                supervisors_subquery,
                and_(
                    *[
                        (
                            type_coerce(
                                supervisors_subquery.c.mapping_criteria_values, JSON
                            )[criteria]
                            == type_coerce(targets_subquery.c.mapped_to_values, JSON)[
                                criteria
                            ]
                        )
                        for criteria in self.mapping_criteria
                    ]
                ),
            )
            .all()
        )
        mappings = [
            {"target_uid": mapping.target_uid, "supervisor_uid": mapping.supervisor_uid}
            for mapping in mappings
        ]

        # Step 2: Add saved mappings for targets that could not be mapped automatically
        target_mapped = [mapping["target_uid"] for mapping in mappings]

        # Fetch saved mappings
        saved_mappings = self.get_saved_mappings()
        for mapping in saved_mappings:
            if mapping.target_uid not in target_mapped:
                mappings.append(
                    {
                        "target_uid": mapping.target_uid,
                        "supervisor_uid": mapping.user_uid,
                    }
                )

        return mappings

    def validate_mappings(self, mappings):
        """
        Method to validate the mapping of the targets to supervisors
        """
        # Validate the mappings
        # 1. Check if all the targets exist
        # 2. Check if all the supervisors exist
        # 3. Check there are no duplicate targets
        # 4. Check if the targets and supervisors are following the mapping criteria selected for the survey

        targets_subquery = self.get_targets_with_mapped_to_subquery()
        supervisors_subquery = self.get_supervisors_subquery()

        not_found_target_uids = []
        not_found_supervisor_uids = []
        duplicate_target_uids = []
        invalid_mapping = []
        target_uids = []
        for mapping in mappings:
            target_uids.append(mapping["target_uid"])
            target = (
                db.session.query(targets_subquery)
                .filter(targets_subquery.c.target_uid == mapping["target_uid"])
                .first()
            )
            if target is None:
                not_found_target_uids.append(mapping["target_uid"])

            supervisor = (
                db.session.query(supervisors_subquery)
                .filter(supervisors_subquery.c.user_uid == mapping["supervisor_uid"])
                .first()
            )
            if supervisor is None:
                not_found_supervisor_uids.append(mapping["supervisor_uid"])

            supervisor_with_same_mapping = (
                db.session.query(supervisors_subquery)
                .filter(
                    supervisors_subquery.c.user_uid == mapping["supervisor_uid"],
                    *[
                        (
                            type_coerce(
                                supervisors_subquery.c.mapping_criteria_values, JSON
                            )[criteria]
                            == type_coerce(target.mapped_to_values[criteria], JSON)
                        )
                        for criteria in self.mapping_criteria
                    ],
                )
                .first()
            )
            if supervisor_with_same_mapping is None:
                invalid_mapping.append(mapping["target_uid"])

        for target_uid in target_uids:
            if target_uids.count(target_uid) > 1:
                if target_uid not in duplicate_target_uids:
                    duplicate_target_uids.append(target_uid)

        if len(not_found_target_uids) > 0:
            raise InvalidMappingRecordsError(
                f"The following target UIDs were not found for the given form: {', '.join(not_found_target_uids)}"
            )
        if len(not_found_supervisor_uids) > 0:
            raise InvalidMappingRecordsError(
                f"The following user UIDs were not found with lowest field supervisor roles for the given survey: {', '.join(not_found_supervisor_uids)}"
            )
        if len(duplicate_target_uids) > 0:
            raise InvalidMappingRecordsError(
                f"The following target UIDs are duplicated in the mappings: {', '.join(duplicate_target_uids)}"
            )
        if len(invalid_mapping) > 0:
            raise InvalidMappingRecordsError(
                f"The mappings for the following target UIDs are violating the mapping criteria: {', '.join(invalid_mapping)}"
            )
        return

    def save_mappings(self, mappings, targets_with_invalid_mappings=[]):
        """
        Method to save the mapping of the targets to supervisors
        and delete the invalid mappings

        """
        # Delete the invalid mappings
        if len(targets_with_invalid_mappings) > 0:
            UserTargetMapping.query.filter(
                UserTargetMapping.target_uid.in_(targets_with_invalid_mappings)
            ).delete(synchronize_session=False)

        # Save the mappings
        for mapping in mappings:
            target_uid = mapping["target_uid"]
            supervisor_uid = mapping["supervisor_uid"]

            # do upsert
            statement = (
                pg_insert(UserTargetMapping)
                .values(
                    target_uid=target_uid,
                    user_uid=supervisor_uid,
                )
                .on_conflict_do_update(
                    constraint="pk_user_target_mapping",
                    set_={
                        "user_uid": supervisor_uid,
                    },
                )
            )
            db.session.execute(statement)
