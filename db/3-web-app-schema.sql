DROP TABLE IF EXISTS users CASCADE;
DROP TABLE IF EXISTS reset_password_tokens;
DROP TABLE IF EXISTS sampling_frames CASCADE;
DROP TABLE IF EXISTS sampling_frame_geo_levels CASCADE;
DROP TABLE IF EXISTS locations CASCADE;
DROP TABLE IF EXISTS location_hierarchy;
DROP TABLE IF EXISTS surveys CASCADE;
DROP TABLE IF EXISTS admin_forms;
DROP TABLE IF EXISTS parent_forms CASCADE;
DROP TABLE IF EXISTS child_forms CASCADE;
DROP TABLE IF EXISTS roles CASCADE;
DROP TABLE IF EXISTS user_hierarchy;
DROP TABLE IF EXISTS location_user_mapping;
DROP TABLE IF EXISTS enumerators CASCADE;
DROP TABLE IF EXISTS surveyor_forms;
DROP TABLE IF EXISTS monitor_forms;
DROP TABLE IF EXISTS location_surveyor_mapping;
DROP TABLE IF EXISTS location_monitor_mapping;
DROP TABLE IF EXISTS targets CASCADE;
DROP TABLE IF EXISTS target_status CASCADE;
DROP TABLE IF EXISTS surveyor_assignments;
DROP TYPE IF EXISTS enumerator_status;
DROP TABLE IF EXISTS webapp_columns;

/*
Table name: users
Description: This table contains the core information for SurveyStream users (supervisors) that will not change survey-to-survey.
*/

CREATE TABLE users (
	user_uid SERIAL PRIMARY KEY,
	email VARCHAR UNIQUE NOT NULL,
	password_secure VARCHAR NOT NULL,
	first_name VARCHAR,
	middle_name VARCHAR,
	last_name VARCHAR,
    home_state VARCHAR,
	home_district VARCHAR,
	phone_primary VARCHAR,
    phone_secondary VARCHAR,
	avatar_s3_filekey VARCHAR,
    active BOOLEAN NOT NULL DEFAULT true
);

/*
Table name: reset_password_tokens
Description: This table stores tokens created by the web app’s “forgot password” functionality
*/

CREATE TABLE reset_password_tokens (
	reset_uid SERIAL PRIMARY KEY,
	user_uid INTEGER UNIQUE NOT NULL REFERENCES users(user_uid),
	secret_token VARCHAR NOT NULL,
	generated_utc TIMESTAMP WITHOUT TIME ZONE NOT NULL
);

/*
Table name: sampling_frames
Description: This table defines our unique sampling frames
*/

CREATE TABLE sampling_frames (
	sampling_frame_uid SERIAL PRIMARY KEY, 
	sampling_frame_name VARCHAR UNIQUE,
    description VARCHAR
);

/*
Table name: sampling_frame_geo_levels
Description: This table defines each geographic level within the sampling frame
*/

CREATE TABLE sampling_frame_geo_levels (
	geo_level_uid SERIAL PRIMARY KEY, 
    sampling_frame_uid INTEGER REFERENCES sampling_frames(sampling_frame_uid), 
    geo_level_name VARCHAR, 
    level INTEGER,
    CONSTRAINT _sampling_frame_uid_geo_level_name_uc UNIQUE (sampling_frame_uid, geo_level_name),
    CONSTRAINT _sampling_frame_uid_level_uc UNIQUE (sampling_frame_uid, level)
);

/*
Table name: locations
Description: This table contains all the locations within the sampling frame
*/

CREATE TABLE locations (
	location_uid SERIAL PRIMARY KEY,
	sampling_frame_uid INTEGER REFERENCES sampling_frames(sampling_frame_uid),
    geo_level_uid INTEGER REFERENCES sampling_frame_geo_levels(geo_level_uid),
    location_id VARCHAR,
    location_name VARCHAR,
    CONSTRAINT _sampling_frame_uid_location_id_uc UNIQUE (sampling_frame_uid, location_id)
);

/*
Table name: location_hierarchy
Description: This table defines the hierarchy (parent-child relationship) between the locations in the location table
*/

CREATE TABLE location_hierarchy (
    location_uid INTEGER PRIMARY KEY REFERENCES locations(location_uid),
    parent_location_uid INTEGER REFERENCES locations(location_uid)
);

/*
Table name: survey
Description: This table contains information about each survey
*/

CREATE TABLE surveys (
	survey_uid SERIAL PRIMARY KEY,
	survey_id VARCHAR UNIQUE,
	survey_name VARCHAR UNIQUE,
	sampling_frame_uid INTEGER REFERENCES sampling_frames(sampling_frame_uid), 
	prime_geo_level_uid INTEGER REFERENCES sampling_frame_geo_levels(geo_level_uid),
	active BOOLEAN
);

/*
Table name: admin_forms
Description: This table contains information about the admin forms within the survey like finance forms, bike log forms, etc, 
which are needed to help administer the survey
*/

CREATE TABLE admin_forms (
    form_uid SERIAL PRIMARY KEY,
    scto_form_id VARCHAR NOT NULL,
    form_name VARCHAR NOT NULL,
    form_type VARCHAR NOT NULL,
    planned_start_date DATE,
    planned_end_date DATE,
    last_ingested_at TIMESTAMP,
    tz_name VARCHAR,
    survey_uid INTEGER NOT NULL REFERENCES surveys(survey_uid),
    CONSTRAINT _admin_forms_survey_uid_scto_form_id_uc UNIQUE (survey_uid, scto_form_id),
    CONSTRAINT _admin_forms_survey_uid_form_name_uc UNIQUE (survey_uid, form_name)
);

/*
Table name: parent_forms
Description: This table contains information about the parent forms within the survey, which are the main forms posed to respondents
*/

CREATE TABLE parent_forms (
    form_uid SERIAL PRIMARY KEY,
    scto_form_id VARCHAR NOT NULL,
    form_name VARCHAR NOT NULL,
    surveying_method VARCHAR NOT NULL,
    planned_start_date DATE,
    planned_end_date DATE,
    last_ingested_at TIMESTAMP,
    tz_name VARCHAR,
    survey_uid INTEGER NOT NULL REFERENCES surveys(survey_uid),
    CONSTRAINT _parent_forms_survey_uid_scto_form_id_uc UNIQUE (survey_uid, scto_form_id),
    CONSTRAINT _parent_forms_survey_uid_form_name_uc UNIQUE (survey_uid, form_name)
);

/*
Table name: child_forms
Description: This table contains information about the child forms (data quality forms, etc) for each parent form
*/

CREATE TABLE child_forms (
    form_uid SERIAL PRIMARY KEY,
    scto_form_id VARCHAR NOT NULL,
    form_type VARCHAR NOT NULL,
    parent_form_uid INTEGER NOT NULL REFERENCES parent_forms(form_uid),
    CONSTRAINT _parent_form_uid_scto_form_id_uc UNIQUE (parent_form_uid, scto_form_id)
);

/*
Table name: roles
Description: This tables defines the supervisor roles for a given survey
*/

CREATE TABLE roles (
    role_uid SERIAL PRIMARY KEY,
    survey_uid INTEGER REFERENCES surveys(survey_uid),
	role_name VARCHAR,
    level INTEGER,
	CONSTRAINT _survey_uid_role_name_uc UNIQUE (survey_uid, role_name),
    CONSTRAINT _survey_uid_level_uc UNIQUE (survey_uid, level)
);

/*
Table name: user_hierarchy
Description: This table defines the relationship between a user and their supervisor and defines the user’s role on the survey. 
Core team members will be included in this table for the purposes of role definition, however they will not be referenced as a 
parent user because of the many-to-many relationship that would result.
*/

CREATE TABLE user_hierarchy (
	survey_uid INTEGER REFERENCES surveys(survey_uid),
	role_uid INTEGER REFERENCES roles(role_uid),
	user_uid INTEGER REFERENCES users(user_uid),
    parent_user_uid INTEGER REFERENCES users(user_uid),
    PRIMARY KEY (survey_uid, user_uid)
);

/*
Table name: location_user_mapping
Description: This table maps FSLn to GL Prime - mapping the lowest supervisor level to the geographical level that they oversee
*/

CREATE TABLE location_user_mapping (
    survey_uid INTEGER REFERENCES surveys(survey_uid),
    user_uid INTEGER REFERENCES users(user_uid), 
    location_uid INTEGER REFERENCES locations(location_uid),
    PRIMARY KEY (survey_uid, location_uid)
);

/*
Table name: enumerators
Description: This table contains information on enumerators that is constant across surveys and forms
*/

CREATE TABLE enumerators (
	enumerator_uid SERIAL PRIMARY KEY,
	enumerator_id VARCHAR UNIQUE,
	first_name VARCHAR,
    middle_name VARCHAR,
    last_name VARCHAR,
	gender VARCHAR,
	language VARCHAR,
	phone_primary VARCHAR,
    phone_secondary VARCHAR,
	email VARCHAR,
    home_address JSONB
);

/*
Table name: surveyor_forms
Description: This table contains information on which forms a surveyor is working 
*/

CREATE TYPE enumerator_status AS ENUM ('Active', 'Dropout', 'Temp. Inactive');

CREATE TABLE surveyor_forms (
    enumerator_uid INTEGER NOT NULL REFERENCES enumerators(enumerator_uid),
    form_uid INTEGER NOT NULL REFERENCES parent_forms(form_uid),
  	status enumerator_status NOT NULL,
    user_uid INTEGER DEFAULT -1,
   	PRIMARY KEY (form_uid, enumerator_uid)
); 

/*
Table name: location_surveyor_mapping
Description: This table describes the location that a surveyor can do surveys on for a given form
*/

CREATE TABLE location_surveyor_mapping (
	form_uid INTEGER NOT NULL REFERENCES parent_forms(form_uid),
    enumerator_uid INTEGER NOT NULL REFERENCES enumerators(enumerator_uid),
    location_uid INTEGER REFERENCES locations(location_uid),
	PRIMARY KEY(form_uid, enumerator_uid, location_uid)
);

/*
Table name: monitor_forms
Description: This table contains information on which forms a monitor is working 
*/

CREATE TABLE monitor_forms (
    enumerator_uid INTEGER NOT NULL REFERENCES enumerators(enumerator_uid),
    form_uid INTEGER NOT NULL REFERENCES child_forms(form_uid),
  	status enumerator_status NOT NULL,
   	PRIMARY KEY (form_uid, enumerator_uid)
); 

/*
Table name: location_monitor_mapping
Description: This table describes the location that a monitor can do dq forms on for a given form
*/

CREATE TABLE location_monitor_mapping (
	form_uid INTEGER NOT NULL REFERENCES child_forms(form_uid),
    enumerator_uid INTEGER NOT NULL REFERENCES enumerators(enumerator_uid),
    location_uid INTEGER REFERENCES locations(location_uid),
	PRIMARY KEY(form_uid, enumerator_uid, location_uid)
);

/*
Table name: targets
Description: This table contains all the survey targets
*/

CREATE TABLE targets (
	target_uid SERIAL PRIMARY KEY,
	target_id VARCHAR NOT NULL,
	form_uid INTEGER NOT NULL REFERENCES parent_forms(form_uid),
	respondent_names VARCHAR[],
    respondent_phone_primary VARCHAR,
    respondent_phone_secondary VARCHAR,
	address VARCHAR,
	gps_latitude VARCHAR,
    gps_longitude VARCHAR,
    prime_location_uid INTEGER REFERENCES locations(location_uid),
    geo_level_n_location_uid INTEGER REFERENCES locations(location_uid),
	active BOOLEAN default 't',
    custom_fields JSONB,
	CONSTRAINT _form_uid_target_id_uc UNIQUE (form_uid, target_id)
); 

/*
 Table name: target_status
 Description: This table contains the status (whether assignable or not) of a target based on number of attempts and last attempt's survey status
 */

CREATE TABLE target_status (
	target_uid INTEGER PRIMARY KEY REFERENCES targets(target_uid),
	completed_flag BOOLEAN,
	refusal_flag BOOLEAN,
	num_attempts INTEGER,
	last_attempt_survey_status INTEGER,
	last_attempt_survey_status_label VARCHAR,
	revisit_sections VARCHAR [],
	target_assignable BOOLEAN,
	webapp_tag_color VARCHAR
);

/*
Table name: surveyor_assignments
Description: This table contains all the assignments for surveyors
*/

CREATE TABLE surveyor_assignments (
    target_uid INTEGER PRIMARY KEY REFERENCES targets(target_uid),
    enumerator_uid INTEGER NOT NULL REFERENCES enumerators(enumerator_uid),
    user_uid INTEGER DEFAULT -1,
    to_delete INTEGER NOT NULL DEFAULT 0
);

/*
Table name: webapp_columns
Description: This table contains metadata for generating dynamic columns on webapp
*/

CREATE TABLE webapp_columns (
    form_uid INTEGER NOT NULL REFERENCES parent_forms(form_uid),
    webapp_table_name VARCHAR NOT NULL,
    group_label VARCHAR,
    column_label VARCHAR NOT NULL,
    column_key VARCHAR NOT NULL,
    column_order INTEGER,
    PRIMARY KEY(form_uid, webapp_table_name, column_key)
);

