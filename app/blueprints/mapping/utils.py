from sqlalchemy import case, distinct, exists, func
from sqlalchemy.dialects.postgresql import insert as pg_insert

from app import db
from app.blueprints.forms.models import Form
from app.blueprints.roles.models import Role
from app.blueprints.roles.utils import InvalidRoleHierarchyError, RoleHierarchy
from app.blueprints.surveys.models import Survey

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
            if "Location" in self.mapping_criteria:
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
        target_mapping_criteria = (
            Survey.query.filter_by(survey_uid=self.survey_uid)
            .first()
            .target_mapping_criteria
        )
        if target_mapping_criteria is None:
            raise MappingError("Supervisor to target mapping criteria not found.")
        return target_mapping_criteria

    def __get_prime_geo_level_uid(self):
        """
        Method to get the prime geo level uid for the form

        """
        prime_geo_level_uid = (
            Survey.query.filter_by(survey_uid=self.survey_uid)
            .first()
            .prime_geo_level_uid
        )
        if prime_geo_level_uid is None:
            raise MappingError(
                "Prime geo level not configured for the survey. Cannot perform supervisor to target mapping based on location without prime geo level."
            )
        return prime_geo_level_uid

    def __get_bottom_level_role_uid(self):
        """
        Method to get the bottom level role uid for the survey

        """
        roles = Role.query.filter_by(survey_uid=self.survey_uid).all()
        if not roles:
            raise MappingError(
                "Roles not configured for the survey. Cannot perform supervisor to target mapping without roles."
            )

        try:
            roles = RoleHierarchy(roles)
        except InvalidRoleHierarchyError as e:
            raise MappingError(e.role_hierarchy_errors)

        bottom_level_role_uid = roles.ordered_geo_levels[-1].role_uid
        return bottom_level_role_uid

    def get_targets_subquery(self):
        """
        Method to get the subquery for fetching targets with mapping criteria values

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
        supervisor_mapping_criteria_values = db.session.query(
            distinct(supervisors_subquery.c.mapping_criteria_values)
        )

        mapping_config_subquery = db.session.query(
            UserMappingConfig.form_uid,
            UserMappingConfig.mapping_type,
            UserMappingConfig.mapping_values,
            UserMappingConfig.mapped_to,
        ).filter(
            UserMappingConfig.form_uid == self.form_uid,
            UserMappingConfig.mapping_type == "target",
            ~exists.where(
                *[
                    getattr(
                        supervisor_mapping_criteria_values.mapping_criteria_values,
                        criteria,
                    )
                    == getattr(UserMappingConfig.mapping_values, criteria)
                    for criteria in self.mapping_criteria
                ]
            ),
        )

        return mapping_config_subquery

    def get_mapping_config(self):
        """
        Method to get the mapping configuration for the form

        """
        mapping_config = self.get_mapping_config_subquery().all()
        return mapping_config

    def get_targets_with_mapped_to_subquery(self):
        """
        Method to get the subquery for fetching targets with custom mapping

        """
        targets_subquery = self.get_targets_subquery()
        mapping_config = self.get_mapping_config_subquery()

        targets_with_custom_mapping_subquery = db.session.query(
            targets_subquery.c.target_uid,
            targets_subquery.c.mapping_criteria_values.label("mapping_criteria_values"),
            func.coalesce(
                mapping_config.c.mapped_to, targets_subquery.c.mapping_criteria_values
            ).label("mapped_to_values"),
        ).outerjoin(
            mapping_config,
            *[
                getattr(mapping_config.c.mapping_values, criteria)
                == getattr(targets_subquery.c.mapping_criteria_values, criteria)
                for criteria in self.mapping_criteria
            ],
        )

        return targets_with_custom_mapping_subquery

    def generate_mappings(self):
        """
        Method to generate the mapping of the targets to supervisors

        """
        supervisors_subquery = self.get_supervisors_subquery()
        targets_subquery = self.get_targets_with_mapped_to_subquery()

        # Only mapping criteria values with 1 supervisor can be mapped automatically
        # Hence, filter supervisors to only those mapping criteria values with 1 supervisor
        supervisors_subquery = (
            supervisors_subquery.filter(
                func.count(distinct(supervisors_subquery.c.user_uid)) == 1
            )
            .group_by(
                supervisors_subquery.c.mapping_criteria_values,
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
                *[
                    getattr(supervisors_subquery.c.mapping_criteria_values, criteria)
                    == getattr(targets_subquery.c.mapped_to_values, criteria)
                    for criteria in self.mapping_criteria
                ],
            )
            .all()
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
            target_uids.append(mapping.target_uid)
            target = targets_subquery.filter_by(target_uid=mapping.target_uid).first()
            if target is None:
                not_found_target_uids.append(mapping.target_uid)

            supervisor = supervisors_subquery.filter_by(
                user_uid=mapping.supervisor_uid
            ).first()

            if supervisor is None:
                not_found_supervisor_uids.append(mapping.supervisor_uid)

            supervisor_with_same_mapping = supervisors_subquery.filter_by(
                user_uid=mapping.supervisor_uid,
                *[
                    getattr(supervisors_subquery.c.mapping_criteria_values, criteria)
                    == getattr(target.mapped_to_values, criteria)
                    for criteria in self.mapping_criteria
                ],
            ).first()
            if supervisor_with_same_mapping is None:
                invalid_mapping.append(mapping.target_uid)

        for target_uid in target_uids:
            if target_uids.count(target_uid) > 1:
                if target_uid not in duplicate_target_uids:
                    duplicate_target_uids.append(target_uid)

        if len(not_found_target_uids) > 0:
            raise InvalidMappingRecordsError(
                f"The following target UIDs were not found in the database: {', '.join(not_found_target_uids)}"
            )
        if len(not_found_supervisor_uids) > 0:
            raise InvalidMappingRecordsError(
                f"The following supervisor UIDs were not found in the database: {', '.join(not_found_supervisor_uids)}"
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

    def save_mappings(self, mappings):
        """
        Method to save the mapping of the targets to supervisors

        """
        # Save the mappings
        for mapping in mappings:
            target_uid = mapping.target_uid
            supervisor_uid = mapping.supervisor_uid

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
