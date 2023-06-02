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


CREATE TABLE config_sandbox.parent_forms
(
    form_uid SERIAL PRIMARY KEY,
	survey_uid INTEGER REFERENCES config_sandbox.surveys(survey_uid) NOT NULL,
    scto_form_id VARCHAR NOT NULL,
    form_name VARCHAR NOT NULL,
    tz_name VARCHAR,
    scto_server_name VARCHAR,
    encryption_key_shared boolean DEFAULT false,
    server_access_role_granted boolean DEFAULT false,
    server_access_allowed boolean DEFAULT false,
    scto_variable_mapping jsonb,
    last_ingested_at timestamp without time zone,
    CONSTRAINT _parent_forms_survey_uid_form_name_uc UNIQUE (survey_uid, form_name),
    CONSTRAINT _parent_forms_survey_uid_scto_form_id_uc UNIQUE (survey_uid, scto_form_id)
);


CREATE TABLE config_sandbox.scto_form_questions
(
    form_uid INTEGER REFERENCES config_sandbox.parent_forms(form_uid) NOT NULL,
	survey_uid INTEGER REFERENCES config_sandbox.surveys(survey_uid) NOT NULL,
    scto_form_id VARCHAR NOT NULL,
	variable_name VARCHAR NOT NULL,
	variable_type VARCHAR,
	question_no VARCHAR,
	choice_name VARCHAR,
    PRIMARY KEY (form_uid, scto_form_id, variable_name)
);
