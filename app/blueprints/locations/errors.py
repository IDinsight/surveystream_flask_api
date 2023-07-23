class InvalidGeoLevelHierarchyError(Exception):
    def __init__(self, geo_level_hierarchy_errors):
        self.geo_level_hierarchy_errors = geo_level_hierarchy_errors


class InvalidGeoLevelMappingError(Exception):
    def __init__(self, geo_level_mapping_errors):
        self.geo_level_mapping_errors = geo_level_mapping_errors


class InvalidLocationsError(Exception):
    def __init__(self, locations_errors):
        self.locations_errors = locations_errors


class HeaderRowEmptyError(Exception):
    def __init__(self, message):
        self.message = [message]
