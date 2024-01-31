class InvalidTableConfigError(Exception):
    def __init__(self, invalid_column_errors):
        self.invalid_column_errors = invalid_column_errors
