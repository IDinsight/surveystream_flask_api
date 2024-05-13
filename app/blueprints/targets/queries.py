from app import db
from app.blueprints.locations.queries import build_location_hierarchy_query


def build_bottom_level_locations_with_location_hierarchy_subquery(
    survey_uid, bottom_level_geo_level_uid
):
    """
    Build a subquery that returns the bottom geo level locations for the
    current survey joined to a JSON column that contains each location's
    own and parent location information

    This will be used to join with the targets data on bottom level locations
    """

    location_hierarchy_query = build_location_hierarchy_query(survey_uid)

    # Get the geo level n locations for the current survey
    # and join in the locations array from the recursive query result
    bottom_level_locations_with_location_hierarchy_subquery = (
        db.session.query(
            location_hierarchy_query.c.location_uid.label("location_uid"),
            location_hierarchy_query.c.locations.label("locations"),
        )
        .filter(location_hierarchy_query.c.geo_level_uid == bottom_level_geo_level_uid)
        .subquery()
    )

    return bottom_level_locations_with_location_hierarchy_subquery
