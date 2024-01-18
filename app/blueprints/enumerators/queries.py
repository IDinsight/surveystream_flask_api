from app import db
from app.blueprints.locations.models import Location
from app.blueprints.locations.queries import build_location_hierarchy_query


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
