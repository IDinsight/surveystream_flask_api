from app.queries.helper_queries import build_user_level_query


def get_core_user_status(user_uid, survey_query):
    """
    Return a boolean indicating whether the given user
    is a core team user on the given survey
    """

    result = build_user_level_query(user_uid, survey_query).first()

    level = result.level

    if level == 0:
        return True
    else:
        return False
