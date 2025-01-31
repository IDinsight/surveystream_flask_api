from app.blueprints.module_selection.models import Module, ModuleStatus
from .models import Survey
from app import db
from sqlalchemy import func


class ModuleStatusCalculator:
    """
    Class with functions to to check the status of a module for a survey
    based on the data in the database

    """

    def __init__(self, survey_uid, module_id):
        self.survey_uid = survey_uid
        self.module_id = module_id

        if self.__check_survey_exists() is False:
            raise ValueError("Survey not found")

        self.forms = []
        self.modules = []

    def __check_survey_exists(self):
        survey = Survey.query.filter_by(survey_uid=self.survey_uid).first()
        return False if survey is None else True

    def __check_unresolved_notifications(self):
        from app.blueprints.notifications.models import SurveyNotification

        notifications = SurveyNotification.query.filter_by(
            survey_uid=self.survey_uid,
            module_id=self.module_id,
            severity="error",  # Check if we need to check for other severity levels
            resolution_status="in progress",
        ).all()
        if notifications is not None and len(notifications) > 0:
            return True
        return False

    def __check_basic_information(self):
        from app.blueprints.module_questionnaire.models import ModuleQuestionnaire

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

        self.__check_module_selection()

        # if field supervisor is required - # Assignments and Emails
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

        if self.__check_surveycto_information() == "Not Started":
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

        if self.__check_surveycto_information() == "Not Started":
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
        from app.blueprints.target_status_mapping.models import TargetStatusMapping

        if self.__check_surveycto_information() == "Not Started":
            return "Not Started"

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
        enumerator = self.__check_enumerators()
        targets = self.__check_targets()

        if enumerator == "Not Started" or targets == "Not Started":
            return "Not Started"
        else:
            return "In Progress"

    def __check_productivity_tracker(self):
        return "Not Started"

    def __check_data_quality(self):
        from app.blueprints.dq.models import DQConfig
        from app.blueprints.forms.models import Form

        if self.__check_surveycto_information() == "Not Started":
            return "Not Started"

        for form in self.forms:
            dq_form_config = Form.query.filter_by(
                survey_uid=self.survey_uid,
                form_type="dq",
                parent_form_uid=form,
            ).first()
            dq_config = DQConfig.query.filter_by(form_uid=form).first()

            if dq_form_config is not None or dq_config is not None:
                return "In Progress"

        return "Not Started"

    def __check_media_audits(self):
        from app.blueprints.media_files.models import MediaFilesConfig

        if self.__check_surveycto_information() == "Not Started":
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

        if self.__check_surveycto_information() == "Not Started":
            return "Not Started"

        for form in self.forms:
            email_config = EmailConfig.query.filter_by(form_uid=form).first()
            if email_config is not None:
                return "In Progress"

        return "Not Started"

    def __check_assignments_column_configuration(self):
        from app.blueprints.assignments.table_config.models import TableConfig

        if self.__check_surveycto_information() == "Not Started":
            return "Not Started"

        for form in self.forms:
            assignment_column_config = TableConfig.query.filter_by(
                form_uid=form
            ).first()
            if assignment_column_config is not None:
                return "In Progress"

        return "Not Started"

    def __check_mapping(self):
        from app.blueprints.mapping.models import (
            UserMappingConfig,
            UserSurveyorMapping,
            UserTargetMapping,
        )

        if self.__check_surveycto_information() == "Not Started":
            return "Not Started"

        for form in self.forms:
            mapping_config = UserMappingConfig.query.filter_by(form_uid=form).first()
            if mapping_config is None:
                mapping_config = UserSurveyorMapping.query.filter_by(
                    form_uid=form
                ).first()
            if mapping_config is None:
                mapping_config = UserTargetMapping.query.filter_by(
                    form_uid=form
                ).first()

            if mapping_config is not None:
                return "In Progress"

        return "Not Started"

    def __check_admin_forms(self):
        from app.blueprints.forms.models import Form

        admin_form_config = Form.query.filter_by(
            survey_uid=self.survey_uid, form_type="admin"
        ).first()
        if admin_form_config is not None:
            return "In Progress"

        return "Not Started"

    def get_status(self):
        if self.__check_unresolved_notifications():
            return "Error"

        if self.module_id == 1:
            return self.__check_basic_information()
        elif self.module_id == 2:
            return self.__check_module_selection()
        elif self.module_id == 3:
            return self.__check_surveycto_information()
        elif self.module_id == 4:
            return self.__check_user_role_management()
        elif self.module_id == 5:
            return self.__check_survey_locations()
        elif self.module_id == 7:
            return self.__check_enumerators()
        elif self.module_id == 8:
            return self.__check_targets()
        elif self.module_id == 9:
            return self.__check_assignments()
        elif self.module_id == 10:
            return self.__check_productivity_tracker()
        elif self.module_id == 11:
            return self.__check_data_quality()
        elif self.module_id == 12:
            return self.__check_media_audits()
        elif self.module_id == 13:
            return self.__check_surveyor_hiring()
        elif self.module_id == 14:
            return self.__check_target_status_mapping()
        elif self.module_id == 15:
            return self.__check_emails()
        elif self.module_id == 16:
            return self.__check_assignments_column_configuration()
        elif self.module_id == 17:
            return self.__check_mapping()
        elif self.module_id == 18:
            return self.__check_admin_forms()
        else:
            return "Module not found"
