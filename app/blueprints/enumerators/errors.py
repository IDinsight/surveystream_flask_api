class InvalidColumnMappingError(Exception):
    def __init__(self, column_mapping_errors):
        self.column_mapping_errors = column_mapping_errors


class InvalidEnumeratorsError(Exception):
    def __init__(self, enumerators_errors):
        self.enumerators_errors = enumerators_errors


class HeaderRowEmptyError(Exception):
    def __init__(self, message):
        self.message = [message]
