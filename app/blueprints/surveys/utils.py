from app.blueprints.module_selection.models import Module, ModuleStatus
from .models import Survey
from app import db
from sqlalchemy import func
from app.blueprints.module_questionnaire.models import ModuleQuestionnaire


class ModuleStatusCalculator:
    """
    Class with functions to to check the status of a module for a survey
    based on the data in the database

    """

    def __init__(self, survey_uid):
        self.survey_uid = survey_uid

        if self.__check_survey_exists() is False:
            raise ValueError("Survey not found")

        self.forms = []
        self.modules = []

        self.calculated_module_status = {}

    def __check_survey_exists(self):
        survey = Survey.query.filter_by(survey_uid=self.survey_uid).first()
        return False if survey is None else True

    def __check_unresolved_notifications(self, module_id):
        from app.blueprints.notifications.models import SurveyNotification

        notifications = SurveyNotification.query.filter_by(
            survey_uid=self.survey_uid,
            module_id=module_id,
            severity="error",  # Check if we need to check for other severity levels
            resolution_status="in progress",
        ).all()
        if notifications is not None and len(notifications) > 0:
            return True
        return False

    def __check_basic_information(self):
        module_questionnaire = ModuleQuestionnaire.query.filter_by(
            survey_uid=self.survey_uid
        ).all()

        if module_questionnaire is None or len(module_questionnaire) == 0:
            return "In Progress"
        else:
            return "Done"

    def __check_module_selection(self):
        # Get list of all optional modules
        modules = (
            db.session.query(ModuleStatus)
            .join(Module, Module.module_id == ModuleStatus.module_id)
            .filter(Module.optional.is_(True))
            .filter(ModuleStatus.survey_uid == self.survey_uid)
            .all()
        )

        if modules is None or len(modules) == 0:
            return "Not Started"

        self.modules = [module.module_id for module in modules]
        return "Done"

    def __check_surveycto_information(self):
        from app.blueprints.forms.models import Form, SCTOQuestionMapping

        forms = Form.query.filter_by(
            survey_uid=self.survey_uid, form_type="parent"
        ).all()

        if forms is None or len(forms) == 0:
            return "Not Started"

        self.forms = [form.form_uid for form in forms]

        # Check if question mapping is done for all forms
        for form in self.forms:
            scto_question_mapping = SCTOQuestionMapping.query.filter_by(
                form_uid=form
            ).first()
            if scto_question_mapping is None:
                return "In Progress"
        return "Done"

    def __check_user_role_management(self):
        from app.blueprints.user_management.models import User
        from app.blueprints.roles.models import Role, SurveyAdmin

        roles = Role.query.filter_by(survey_uid=self.survey_uid).first()
        survey_admin = SurveyAdmin.query.filter_by(survey_uid=self.survey_uid).first()

        # If module selection is not done, then return not started
        # Additional roles/users are required based on which modules are selected
        if self.calculated_module_status.get(2) is None:
            self.calculated_module_status[2] = self.__check_module_selection()
        if self.calculated_module_status[2] == "Not Started":
            return "Not Started"

        # if field supervisor information is required - # Assignments and Emails
        if set(self.modules) & {9, 15}:
            users = (
                db.session.query(User)
                .join(Role, Role.role_uid == func.any(User.roles))
                .filter(Role.survey_uid == self.survey_uid)
                .all()
            )

            if roles is None and survey_admin is None:
                return "Not Started"
            elif users is None or len(users) == 0:
                return "In Progress"
            else:
                return "Done"
        else:
            if roles is None and survey_admin is None:
                return "Not Started"
            else:
                return "Done"

    def __check_survey_locations(self):
        from app.blueprints.locations.models import GeoLevel, Location

        geo_levels = GeoLevel.query.filter_by(survey_uid=self.survey_uid).first()
        if geo_levels is None:
            return "Not Started"

        locations = Location.query.filter_by(survey_uid=self.survey_uid).first()
        if locations is None:
            return "In Progress"
        else:
            return "Done"

    def __check_enumerators(self):
        from app.blueprints.enumerators.models import Enumerator

        # Check if surveycto information is present, if not then return not started
        if self.calculated_module_status.get(3) is None:
            self.calculated_module_status[3] = self.__check_surveycto_information()
        if self.calculated_module_status[3] == "Not Started":
            return "Not Started"

        one_form = False
        all_forms = True
        for form in self.forms:
            enumerators = Enumerator.query.filter_by(form_uid=form).first()
            if enumerators is not None:
                one_form = True
            else:
                all_forms = False

        if one_form and all_forms:
            return "Done"
        elif one_form:
            return "In Progress"
        else:
            return "Not Started"

    def __check_targets(self):
        from app.blueprints.targets.models import Target, TargetConfig

        # Check if surveycto information is present, if not then return not started
        if self.calculated_module_status.get(3) is None:
            self.calculated_module_status[3] = self.__check_surveycto_information()
        if self.calculated_module_status[3] == "Not Started":
            return "Not Started"

        one_form = False
        all_forms = True
        for form in self.forms:
            targets = Target.query.filter_by(form_uid=form).first()
            target_config = TargetConfig.query.filter_by(form_uid=form).first()
            if target_config is not None:
                one_form = True
            if targets is None:
                all_forms = False

        if one_form and all_forms:
            return "Done"
        elif one_form:
            return "In Progress"
        else:
            return "Not Started"

    def __check_target_status_mapping(self):
        from app.blueprints.target_status_mapping.models import (
            DefaultTargetStatusMapping,
            TargetStatusMapping,
        )

        # Check if surveycto information is present, if not then return not started
        if self.calculated_module_status.get(3) is None:
            self.calculated_module_status[3] = self.__check_surveycto_information()
        if self.calculated_module_status[3] == "Not Started":
            return "Not Started"

        surveying_method = (
            Survey.query.filter_by(survey_uid=self.survey_uid).first().surveying_method
        )
        default_target_status_mapping = DefaultTargetStatusMapping.query.filter_by(
            surveying_method=surveying_method
        ).first()

        if default_target_status_mapping:
            return "Done"

        one_form = False
        all_forms = True
        for form in self.forms:
            target_status_mapping = TargetStatusMapping.query.filter_by(
                form_uid=form
            ).first()

            if target_status_mapping is not None:
                one_form = True
            else:
                all_forms = False

        if one_form and all_forms:
            return "Done"
        elif one_form:
            return "In Progress"
        else:
            return "Not Started"

    def __check_assignments(self):
        if self.calculated_module_status.get(7) is None:
            self.calculated_module_status[7] = self.__check_enumerators()
        if self.calculated_module_status.get(8) is None:
            self.calculated_module_status[8] = self.__check_targets()

        if (
            self.calculated_module_status[7] == "Not Started"
            or self.calculated_module_status[8] == "Not Started"
        ):
            return "Not Started"
        else:
            return "In Progress"

    def __check_productivity_tracker(self):
        return "Not Started"

    def __check_data_quality(self):
        from app.blueprints.dq.models import DQConfig
        from app.blueprints.forms.models import Form, SCTOQuestionMapping

        # Check if surveycto information is present, if not then return not started
        if self.calculated_module_status.get(3) is None:
            self.calculated_module_status[3] = self.__check_surveycto_information()
        if self.calculated_module_status[3] == "Not Started":
            return "Not Started"

        dq_config_in_progress = False
        dq_form_in_progress = False
        done = True
        for form in self.forms:
            # if dq config is present for any form, then it is in progress
            dq_config = DQConfig.query.filter_by(form_uid=form).first()
            if dq_config is not None:
                dq_config_in_progress = True

            # if dq form is present for any form, then it is in progress
            dq_form_config = Form.query.filter_by(
                survey_uid=self.survey_uid,
                form_type="dq",
                parent_form_uid=form,
            ).all()
            if dq_form_config is not None and len(dq_form_config) > 0:
                dq_form_in_progress = True

            # Check if scto question mapping is done for all dq forms
            for dq_form in dq_form_config:
                scto_question_mapping = SCTOQuestionMapping.query.filter_by(
                    form_uid=dq_form.form_uid
                ).first()

                # if scto question mapping is not done for any dq form, then it is not done
                if scto_question_mapping is None:
                    done = False
                    break

        # if both dq form and dq config are not in progress, then it is not started
        if not dq_form_in_progress and not dq_config_in_progress:
            return "Not Started"

        # if dq form is in progress but dq config is not in progress, then it is in progress - incomplete
        if dq_form_in_progress and not dq_config_in_progress:
            return "In Progress - Incomplete"

        # if dq form is in progress but question mapping is not done for any dq form, then it is in progress - incomplete
        if dq_form_in_progress and done == False:
            return "In Progress - Incomplete"

        # if dq config is in progress and question mapping is done for all available dq forms, then it is in progress
        if dq_config_in_progress and done:
            return "In Progress"

    def __check_media_audits(self):
        from app.blueprints.media_files.models import MediaFilesConfig

        # Check if surveycto information is present, if not then return not started
        if self.calculated_module_status.get(3) is None:
            self.calculated_module_status[3] = self.__check_surveycto_information()
        if self.calculated_module_status[3] == "Not Started":
            return "Not Started"

        for form in self.forms:
            media_files_config = MediaFilesConfig.query.filter_by(form_uid=form).first()
            if media_files_config is not None:
                return "In Progress"

        return "Not Started"

    def __check_surveyor_hiring(self):
        return "Not Started"

    def __check_emails(self):
        from app.blueprints.emails.models import EmailConfig

        # Check if surveycto information is present, if not then return not started
        if self.calculated_module_status.get(3) is None:
            self.calculated_module_status[3] = self.__check_surveycto_information()
        if self.calculated_module_status[3] == "Not Started":
            return "Not Started"

        for form in self.forms:
            email_config = EmailConfig.query.filter_by(form_uid=form).first()
            if email_config is not None:
                return "In Progress"

        return "Not Started"

    def __check_assignments_column_configuration(self):
        from app.blueprints.assignments.table_config.models import TableConfig

        # Check if surveycto information is present, if not then return not started
        if self.calculated_module_status.get(3) is None:
            self.calculated_module_status[3] = self.__check_surveycto_information()
        if self.calculated_module_status[3] == "Not Started":
            return "Not Started"

        for form in self.forms:
            assignment_column_config = TableConfig.query.filter_by(
                form_uid=form
            ).first()
            if assignment_column_config is not None:
                return "In Progress"

        return "Not Started"

    def __check_mapping(self):
        from app.blueprints.targets.models import Target
        from app.blueprints.enumerators.models import Enumerator
        from app.blueprints.mapping.utils import SurveyorMapping, TargetMapping

        # Check if surveycto information is present, if not then return not started
        if self.calculated_module_status.get(3) is None:
            self.calculated_module_status[3] = self.__check_surveycto_information()
        if self.calculated_module_status[3] == "Not Started":
            return "Not Started"

        completed = True
        error = True
        for form in self.forms:
            # Check if there are unmapped enumerators and targets
            try:
                surveyor_mapping = SurveyorMapping(form)
                target_mapping = TargetMapping(form)

                error = False
            except:
                continue

            s_mappings = surveyor_mapping.generate_mappings()
            t_mappings = target_mapping.generate_mappings()

            # Find count of all enumerators and targets
            targets = db.session.query(Target).filter(Target.form_uid == form).count()
            enumerators = (
                db.session.query(Enumerator).filter(Enumerator.form_uid == form).count()
            )

            if len(s_mappings) < enumerators or len(t_mappings) <= targets:
                completed = False

        if error:
            return "Not Started"  # If mapping gives errors for all forms, then return not started
        if completed:
            return "Done"

        return "In Progress - Incomplete"

    def __check_admin_forms(self):
        from app.blueprints.forms.models import Form, SCTOQuestionMapping

        admin_form_config = Form.query.filter_by(
            survey_uid=self.survey_uid, form_type="admin"
        ).all()

        if admin_form_config is None or len(admin_form_config) == 0:
            return "Not Started"

        for form in admin_form_config:
            scto_question_mapping = SCTOQuestionMapping.query.filter_by(
                form_uid=form.form_uid
            ).first()
            if scto_question_mapping is None:
                return "In Progress - Incomplete"

        return "In Progress"

    def get_status(self, module_id):
        if self.__check_unresolved_notifications(module_id):
            status = "Error"
        elif module_id == 1:
            status = self.__check_basic_information()
        elif module_id == 2:
            status = self.__check_module_selection()
        elif module_id == 3:
            status = self.__check_surveycto_information()
        elif module_id == 4:
            status = self.__check_user_role_management()
        elif module_id == 5:
            status = self.__check_survey_locations()
        elif module_id == 7:
            status = self.__check_enumerators()
        elif module_id == 8:
            status = self.__check_targets()
        elif module_id == 9:
            status = self.__check_assignments()
        elif module_id == 10:
            status = self.__check_productivity_tracker()
        elif module_id == 11:
            status = self.__check_data_quality()
        elif module_id == 12:
            status = self.__check_media_audits()
        elif module_id == 13:
            status = self.__check_surveyor_hiring()
        elif module_id == 14:
            status = self.__check_target_status_mapping()
        elif module_id == 15:
            status = self.__check_emails()
        elif module_id == 16:
            status = self.__check_assignments_column_configuration()
        elif module_id == 17:
            status = self.__check_mapping()
        elif module_id == 18:
            status = self.__check_admin_forms()
        else:
            return "Module not found"

        self.calculated_module_status[module_id] = status
        return self.calculated_module_status[module_id]


def check_module_dependency_condition(survey_uid, conditions):
    """
    Match notification conditions according to survey configuration and dependency conditions

    Args:
        survey_uid: UID of surveys
        form_uid: UID of form
        conditions: Conditions
    """
    condition_checks = {
        "surveyor_location_mapping": lambda: check_surveyor_location_mapping(
            survey_uid
        ),
        "target_location_mapping": lambda: check_target_location_mapping(survey_uid),
        "surveying_method_mixed_mode": lambda: check_surveying_method_mixed_mode(
            survey_uid
        ),
    }

    survey_conditions = {
        condition: condition_checks[condition]()
        for condition in conditions
        if condition in condition_checks
    }

    return any(survey_conditions.values())


def check_surveyor_location_mapping(survey_uid):
    return (
        ModuleQuestionnaire.query.filter(
            ModuleQuestionnaire.survey_uid == survey_uid,
            ModuleQuestionnaire.surveyor_mapping_criteria.any("Location"),
        ).first()
        is not None
    )


def check_target_location_mapping(survey_uid):
    return (
        ModuleQuestionnaire.query.filter(
            ModuleQuestionnaire.survey_uid == survey_uid,
            ModuleQuestionnaire.target_mapping_criteria.any("Location"),
        ).first()
        is not None
    )


def check_surveying_method_mixed_mode(survey_uid):
    return (
        Survey.query.filter(
            Survey.survey_uid == survey_uid,
            Survey.surveying_method == "mixed-mode",
        ).first()
        is not None
    )


def is_module_optional(
    survey_uid, saved_optional_flag, required_if_conditions, config_status
):
    """
    Check if the module is optional based on the conditions and the saved optional flag

    """

    # These are universally mandatory modules
    if saved_optional_flag is False:
        return False

    # Check if the module is required based on the conditions
    required_if_conditions = (
        [item for sublist in required_if_conditions for item in sublist]
        if required_if_conditions
        else []
    )

    # if 'Always' is in the required_if_conditions, then the module is mandatory always
    if required_if_conditions and "Always" in required_if_conditions:
        return False

    # check if required_if_conditions are met
    elif required_if_conditions and check_module_dependency_condition(
        survey_uid,
        required_if_conditions,
    ):
        return False

    # For all other cases, the module is optional if the config is not started
    # As soon as the config is started, the module becomes mandatory
    if config_status == "Not Started":
        return True
    else:
        return False
