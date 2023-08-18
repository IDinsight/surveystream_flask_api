from app import db
from app.blueprints.locations.models import GeoLevel, Location
from sqlalchemy.sql.functions import func


def build_location_hierarchy_query(survey_uid):
    """
    Build a query that returns the locations for the current survey
    joined to an array column that contains the location's own and parent
    location information

    This will be used as an input to other queries that need specific subsets
    of the location records with their location hierarchy information
    """

    # Assemble the first part of the recursive query
    # This returns all the top level locations for the survey and
    # a JSON object that will hold the accumulated location information
    top_query = (
        db.session.query(
            Location.location_uid.label("location_uid"),
            func.jsonb_build_array(
                func.jsonb_build_object(
                    "geo_level_name",
                    GeoLevel.geo_level_name,
                    "geo_level_uid",
                    GeoLevel.geo_level_uid,
                    "location_name",
                    Location.location_name,
                    "location_id",
                    Location.location_id,
                    "location_uid",
                    Location.location_uid,
                )
            ).label("locations"),
        )
        .join(
            GeoLevel,
            Location.geo_level_uid == GeoLevel.geo_level_uid,
        )
        .filter(GeoLevel.parent_geo_level_uid.is_(None))
        .filter(GeoLevel.survey_uid == survey_uid)
        .cte(recursive=True)
    )

    # Assemble the second part of the recursive query
    # This will descend down the location hierarchy tree and accumulate
    # the location information in the locations JSON object
    bottom_query = (
        db.session.query(
            Location.location_uid.label("location_uid"),
            top_query.c.locations.concat(
                func.jsonb_build_object(
                    "geo_level_name",
                    GeoLevel.geo_level_name,
                    "geo_level_uid",
                    GeoLevel.geo_level_uid,
                    "location_name",
                    Location.location_name,
                    "location_id",
                    Location.location_id,
                    "location_uid",
                    Location.location_uid,
                )
            ).label("locations"),
        )
        .join(
            GeoLevel,
            Location.geo_level_uid == GeoLevel.geo_level_uid,
        )
        .join(top_query, Location.parent_location_uid == top_query.c.location_uid)
    )

    location_hierarchy_query = top_query.union(bottom_query)

    return location_hierarchy_query


def build_prime_locations_with_location_hierarchy_subquery(
    survey_uid, prime_geo_level_uid
):
    """
    Build a subquery that returns the prime geo level locations for the
    current survey joined to an array column that contains the location's
    own and parent region information

    This will be used to join with the enumerators data on prime location uid
    to get the enumerators' working locations
    """

    location_hierarchy_query = build_location_hierarchy_query(survey_uid)

    # Get the prime geo level locations for the current survey
    # and join in the ancestors array from the recursive query result
    prime_locations_with_location_hierarchy_subquery = (
        db.session.query(
            Location.location_uid.label("location_uid"),
            Location.location_name.label("location_name"),
            location_hierarchy_query.c.locations.label("locations"),
        )
        .join(
            location_hierarchy_query,
            Location.location_uid == location_hierarchy_query.c.location_uid,
            isouter=True,
        )
        .filter(Location.survey_uid == survey_uid)
        .filter(Location.geo_level_uid == prime_geo_level_uid)
        .subquery()
    )

    return prime_locations_with_location_hierarchy_subquery
