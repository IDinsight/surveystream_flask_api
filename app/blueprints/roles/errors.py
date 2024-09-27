class InvalidRoleHierarchyError(Exception):
    def __init__(self, role_hierarchy_errors):
        self.role_hierarchy_errors = role_hierarchy_errors
