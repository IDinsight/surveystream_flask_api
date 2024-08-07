class MappingError(Exception):
    def __init__(self, mapping_errors):
        self.mapping_errors = mapping_errors


class InvalidMappingRecordsError(Exception):
    def __init__(self, record_errors):
        self.record_errors = record_errors
