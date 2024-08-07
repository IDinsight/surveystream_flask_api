from sqlalchemy.sql.functions import func

from app import db
from app.blueprints.auth.models import User
from app.blueprints.locations.models import GeoLevel, Location
from app.blueprints.targets.models import Target
from app.blueprints.user_management.models import UserLanguage, UserLocation


def build_lower_level_locations_to_prime_geo_level_location_mapping(
    survey_uid, prime_geo_level_uid
):
    """
    Build a query that returns all the locations for the current survey
    that are below the prime geo level mapped to the prime geo level location

    This will be used as an input to other queries that need this mapping
    """

    # Assemble the first part of the recursive query
    # This returns all the prime geo level level locations for the survey
    # mapped to themselves
    top_query = (
        db.session.query(
            Location.location_uid.label("location_uid"),
            GeoLevel.geo_level_uid.label("geo_level_uid"),
            Location.location_uid.label("prime_geo_level_location_uid"),
        )
        .join(
            GeoLevel,
            Location.geo_level_uid == GeoLevel.geo_level_uid,
        )
        .filter(GeoLevel.geo_level_uid == prime_geo_level_uid)
        .filter(GeoLevel.survey_uid == survey_uid)
        .cte(recursive=True)
    )

    # Assemble the second part of the recursive query
    # This will descend down the location hierarchy tree and map each
    # location to its prime geo level location
    bottom_query = (
        db.session.query(
            Location.location_uid.label("location_uid"),
            GeoLevel.geo_level_uid.label("geo_level_uid"),
            top_query.c.prime_geo_level_location_uid.label(
                "prime_geo_level_location_uid"
            ),
        )
        .join(
            GeoLevel,
            Location.geo_level_uid == GeoLevel.geo_level_uid,
        )
        .join(top_query, Location.parent_location_uid == top_query.c.location_uid)
    )

    location_hierarchy_query = top_query.union(bottom_query)

    return location_hierarchy_query


def build_targets_with_mapping_criteria_values_subquery(
    survey_uid, form_uid, prime_geo_level_uid, mapping_criteria
):
    """
    Build a subquery that returns the targets for the given form along with mapping criteria values in JSON format

    """
    locations_subquery = (
        build_lower_level_locations_to_prime_geo_level_location_mapping(
            survey_uid, prime_geo_level_uid
        )
    )

    # Build list of columns based on the mapping criteria
    target_columns = []
    for criteria in mapping_criteria:
        if criteria == "Gender":
            target_columns.append(Target.gender)
        elif criteria == "Language":
            target_columns.append(Target.language)
        elif criteria == "Location":
            target_columns.append(
                locations_subquery.c.prime_geo_level_location_uid.label("location_uid")
            )
        elif criteria == "manual":
            target_columns.append("manual".label("manual"))

    # If location is in the mapping criteria, we need to add location id and name columns to the json object
    if "Location" in mapping_criteria:
        target_columns.append(Location.location_id.label("location_id"))
        target_columns.append(Location.location_name.label("location_name"))
        mapping_criteria.append("location_id")
        mapping_criteria.append("location_name")

    # This query returns one row per target
    targets_query = (
        db.session.query(
            Target.target_uid,
            Target.target_id,
            Target.gender,
            Target.language,
            Location.location_id.label("location_id"),
            Location.location_name.label("location_name"),
            func.jsonb_build_object(
                *[
                    (criteria, column)
                    for criteria, column in zip(mapping_criteria, target_columns)
                ]
            ).label("mapping_criteria_values"),
        )
        .outerjoin(
            locations_subquery,
            Target.location_uid == locations_subquery.c.location_uid,
        )
        .outerjoin(
            Location,
            locations_subquery.c.prime_geo_level_location_uid == Location.location_uid,
        )
        .filter(Target.form_uid == form_uid)
    )

    return targets_query


def build_supervisors_with_mapping_criteria_values_subquery(
    survey_uid, bottom_level_role_uid, mapping_criteria
):
    """
    Build a subquery that returns the smallest supervisors for a given survey along with mapping criteria values in JSON format

    """
    user_subquery = (
        db.session.query(
            User.user_uid,
            User.gender,
            User.languages.label("language"),
            func.unnest(User.roles).label("role_uid"),
        )
        .filter(User.active.is_(True))
        .subquery()
    )
    # Filter to only get the smallest supervisors
    user_subquery = user_subquery.filter(
        user_subquery.c.role_uid == bottom_level_role_uid
    )

    if "Language" in mapping_criteria:
        # Separate each language into its own row
        user_subquery = db.session.query(
            user_subquery.c.user_uid,
            user_subquery.c.gender,
            func.unnest(user_subquery.c.language).label("language"),
        ).subquery()

    # Build list of columns based on the mapping criteria
    supervisor_columns = []
    for criteria in mapping_criteria:
        if criteria == "Gender":
            supervisor_columns.append(user_subquery.c.gender)
        elif criteria == "Language":
            supervisor_columns.append(user_subquery.c.language)
        elif criteria == "Location":
            supervisor_columns.append(UserLocation.location_uid.label("location_uid"))
        elif criteria == "manual":
            supervisor_columns.append("manual".label("manual"))

    # If location is in the mapping criteria, we need to add location id and name columns to the json object
    if "Location" in mapping_criteria:
        supervisor_columns.append(Location.location_id.label("location_id"))
        supervisor_columns.append(Location.location_name.label("location_name"))
        mapping_criteria.append("location_id")
        mapping_criteria.append("location_name")

    # Since a supervisor can be assigned to multiple languages and locations, the results of this query can
    # have more than one row per supervisor if the mapping criteria includes language or location
    # It is expected to have one row per user per mapping criteria value
    supervisors_query = db.session.query(
        user_subquery.c.user_uid,
        func.jsonb_build_object(
            *[
                (criteria, column)
                for criteria, column in zip(mapping_criteria, supervisor_columns)
            ]
        ).label("mapping_criteria_values"),
    )

    # Join tables only based on need as per the mapping criteria
    if "Location" in mapping_criteria:
        supervisors_query = supervisors_query.outerjoin(
            UserLocation,
            user_subquery.c.user_uid == UserLocation.user_uid,
            UserLocation.survey_uid == survey_uid,
        ).outerjoin(
            Location,
            UserLocation.location_uid == Location.location_uid,
        )

    if "Language" in mapping_criteria:
        supervisors_query = supervisors_query.outerjoin(
            UserLanguage,
            user_subquery.c.user_uid == UserLanguage.user_uid,
            UserLanguage.survey_uid == survey_uid,
        )

    return supervisors_query
