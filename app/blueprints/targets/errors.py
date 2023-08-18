class InvalidColumnMappingError(Exception):
    def __init__(self, column_mapping_errors):
        self.column_mapping_errors = column_mapping_errors


class InvalidTargetRecordsError(Exception):
    def __init__(self, record_errors):
        self.record_errors = record_errors


class HeaderRowEmptyError(Exception):
    def __init__(self, message):
        self.message = [message]


class InvalidFileStructureError(Exception):
    def __init__(self, file_structure_errors):
        self.file_structure_errors = file_structure_errors
