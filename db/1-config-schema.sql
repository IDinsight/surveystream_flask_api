DROP SCHEMA IF EXISTS config_sandbox CASCADE;
CREATE SCHEMA config_sandbox;

DROP TABLE IF EXISTS config_sandbox.surveys CASCADE;
DROP TABLE IF EXISTS config_sandbox.modules CASCADE;
DROP TABLE IF EXISTS config_sandbox.module_status CASCADE;
DROP TABLE IF EXISTS config_sandbox.module_questionnaire CASCADE;
DROP TABLE IF EXISTS config_sandbox.roles CASCADE;
DROP TABLE IF EXISTS config_sandbox.parent_forms CASCADE;
DROP TABLE IF EXISTS config_sandbox.scto_form_questions CASCADE;

/*
Table name: surveys
Description: This table contains information about each survey
*/

CREATE TABLE config_sandbox.surveys (
	survey_uid SERIAL PRIMARY KEY,
	survey_id VARCHAR UNIQUE,
	survey_name VARCHAR UNIQUE,
	project_name VARCHAR,
	survey_description VARCHAR,
	surveying_method VARCHAR NOT NULL CHECK (surveying_method IN ('phone', 'in-person')),
	planned_start_date DATE NOT NULL,
    planned_end_date DATE NOT NULL,
    irb_approval VARCHAR NOT NULL CHECK (irb_approval IN ('Yes','No','Pending')),
	config_status VARCHAR CHECK (config_status IN ('In Progress - Configuration','In Progress - Backend Setup','Done')),
    state VARCHAR CHECK (state IN ('Draft','Active','Past')),
    created_by_user_uid INTEGER REFERENCES users(user_uid),
	last_updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

/*
Table name: modules
Description: This table contains the reference list of all configurable modules
*/

CREATE TABLE config_sandbox.modules (
	module_id INTEGER PRIMARY KEY,
	name VARCHAR UNIQUE,
	optional BOOLEAN
);

/*
Table name: module_status
Description: This table contains the completion status of each module per survey
*/

CREATE TABLE config_sandbox.module_status (
	survey_uid INTEGER REFERENCES config_sandbox.surveys(survey_uid),
	module_id INTEGER REFERENCES config_sandbox.modules(module_id),
	config_status VARCHAR CHECK (config_status IN ('Done','In Progress','Not Started', 'Error'))
);

/*
Table name: module_questionnaire
Description: This table contains the responses for module questionnaire section for each survey
*/

CREATE TABLE config_sandbox.module_questionnaire (
	survey_uid INTEGER REFERENCES config_sandbox.surveys(survey_uid) PRIMARY KEY,
	target_assignment_criteria VARCHAR[],
	supervisor_assignment_criteria VARCHAR[],
	supervisor_hierarchy_exists BOOLEAN,
	reassignment_required BOOLEAN,
	assignment_process VARCHAR CHECK (assignment_process IN ('Manual','Random')),
	supervisor_enumerator_relation VARCHAR,
	language_lacation_mapping BOOLEAN
);

/*
Table name: roles
Description: This table contains the responses for roles section for each survey
*/

CREATE TABLE config_sandbox.roles (
	role_uid SERIAL PRIMARY KEY,
	survey_uid INTEGER REFERENCES config_sandbox.surveys(survey_uid) NOT NULL,
	role_name VARCHAR NOT NULL,
	reporting_role_uid INTEGER REFERENCES config_sandbox.roles(role_uid),
	user_uid INTEGER DEFAULT -1,
    to_delete INTEGER NOT NULL DEFAULT 0,
	CONSTRAINT _survey_uid_role_name_uc UNIQUE (survey_uid, role_name) DEFERRABLE
);

/*
Table name: geo_levels
Description: This table contains the responses for geo levels section for each survey
*/

CREATE TABLE config_sandbox.geo_levels (
	geo_level_uid SERIAL PRIMARY KEY,
	survey_uid INTEGER NOT NULL REFERENCES config_sandbox.surveys(survey_uid) ON DELETE CASCADE,
	geo_level_name VARCHAR NOT NULL,
	parent_geo_level_uid INTEGER REFERENCES config_sandbox.geo_levels(geo_level_uid),
	user_uid INTEGER DEFAULT -1,
    to_delete INTEGER NOT NULL DEFAULT 0,
	CONSTRAINT _survey_uid_geo_level_name_uc UNIQUE (survey_uid, geo_level_name) DEFERRABLE
);

CREATE TABLE config_sandbox.locations (
	location_uid SERIAL PRIMARY KEY,
	survey_uid INTEGER NOT NULL REFERENCES config_sandbox.surveys(survey_uid) ON DELETE CASCADE,
	geo_level_uid INTEGER NOT NULL REFERENCES config_sandbox.geo_levels(geo_level_uid) ON DELETE CASCADE,
	location_id VARCHAR NOT NULL,
	location_name VARCHAR NOT NULL,
	parent_location_uid INTEGER REFERENCES config_sandbox.locations(location_uid),
	CONSTRAINT _survey_uid_geo_level_uid_location_name_uc UNIQUE (survey_uid, location_id)
);

CREATE INDEX ix_locations_survey_uid_geo_level_uid ON config_sandbox.locations (survey_uid, geo_level_uid);

CREATE TABLE config_sandbox.parent_forms
(
    form_uid SERIAL PRIMARY KEY,
	survey_uid INTEGER NOT NULL REFERENCES config_sandbox.surveys(survey_uid) ON DELETE CASCADE,
    scto_form_id VARCHAR NOT NULL,
    form_name VARCHAR NOT NULL,
    tz_name VARCHAR,
    scto_server_name VARCHAR,
    encryption_key_shared boolean DEFAULT false,
    server_access_role_granted boolean DEFAULT false,
    server_access_allowed boolean DEFAULT false,
    last_ingested_at timestamp without time zone,
    CONSTRAINT _parent_forms_survey_uid_form_name_uc UNIQUE (survey_uid, form_name),
    CONSTRAINT _parent_forms_survey_uid_scto_form_id_uc UNIQUE (survey_uid, scto_form_id)
);

CREATE TABLE config_sandbox.scto_form_settings
(
	form_uid INTEGER NOT NULL PRIMARY KEY REFERENCES config_sandbox.parent_forms(form_uid) ON DELETE CASCADE,
	form_title VARCHAR,
	version VARCHAR NOT NULL,
	public_key VARCHAR,
	submission_url VARCHAR,
	default_language VARCHAR
);

CREATE TABLE config_sandbox.scto_question_mapping
(
	form_uid INTEGER NOT NULL PRIMARY KEY REFERENCES config_sandbox.parent_forms(form_uid) ON DELETE CASCADE,
	survey_status VARCHAR NOT NULL,
	revisit_section VARCHAR NOT NULL,
	enumerator_id VARCHAR NOT NULL,
	target_id VARCHAR NOT NULL,
	locations jsonb
);

CREATE TABLE config_sandbox.scto_form_choice_lists
(
	list_uid SERIAL PRIMARY KEY,
	form_uid INTEGER NOT NULL REFERENCES config_sandbox.parent_forms(form_uid) ON DELETE CASCADE,
	list_name VARCHAR NOT NULL,
	CONSTRAINT _scto_form_choice_lists_form_uid_list_name_uc UNIQUE (form_uid, list_name)
);

CREATE TABLE config_sandbox.scto_form_choice_labels
(
    list_uid INTEGER NOT NULL REFERENCES config_sandbox.scto_form_choice_lists(list_uid) ON DELETE CASCADE,
	choice_value VARCHAR NOT NULL,
	language VARCHAR NOT NULL,
	label VARCHAR,
	PRIMARY KEY (list_uid, choice_value, language)
);

CREATE TABLE config_sandbox.scto_form_questions
(
	question_uid SERIAL PRIMARY KEY,
    form_uid INTEGER NOT NULL REFERENCES config_sandbox.parent_forms(form_uid) ON DELETE CASCADE,
	question_name VARCHAR NOT NULL,
	question_type VARCHAR NOT NULL,
	list_uid INTEGER REFERENCES config_sandbox.scto_form_choice_lists(list_uid),
	is_repeat_group boolean NOT NULL,
	CONSTRAINT _scto_form_questions_form_uid_question_name_question_type_uc UNIQUE (form_uid, question_name, question_type)
);

CREATE TABLE config_sandbox.scto_form_question_labels
(
    question_uid INTEGER NOT NULL REFERENCES config_sandbox.scto_form_questions(question_uid) ON DELETE CASCADE,
	language VARCHAR NOT NULL,
	label VARCHAR,
    PRIMARY KEY (question_uid, language)
);



