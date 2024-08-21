from .errors import InvalidRoleHierarchyError
from .models import SurveyAdmin


class RoleHierarchy:
    """
    Class to represent the role hierarchy and run validations on it
    """

    def __init__(self, roles):
        self.roles = roles

        try:
            self.__validate_hierarchy()
        except:
            raise

        self.ordered_roles = self.__get_ordered_roles()

    def __get_ordered_roles(self):
        """
        Method to create an ordered list of roles based on the role hierarchy
        This method assumes that the role hierarchy has been validated
        """
        ordered_roles = [
            role for role in self.roles if role["reporting_role_uid"] is None
        ]

        for i in range(len(self.roles) - 1):
            for role in self.roles:
                if role["reporting_role_uid"] == ordered_roles[i]["role_uid"]:
                    ordered_roles.append(role)

        return ordered_roles

    def __validate_hierarchy(self):
        """
        Function to run validations on the role hierarchy and return a list of errors

        :param roles: List of roles for the survey
        """
        errors_list = []

        # Prechecks before we validate the tree

        # There should be no duplicates on role_uid
        role_uids = [role["role_uid"] for role in self.roles]
        for role_uid in role_uids:
            if role_uids.count(role_uid) > 1:
                error_message = f"Each role unique id defined in the role hierarchy should appear exactly once in the hierarchy. Role with role_uid='{role_uid}' appears {role_uids.count(role_uid)} times in the hierarchy."

                if error_message not in errors_list:
                    errors_list.append(error_message)

        # There should be no duplicates on role_name
        role_names = [role["role_name"] for role in self.roles]
        for role_name in role_names:
            if role_names.count(role_name) > 1:
                error_message = f"Each role name defined in the role hierarchy should appear exactly once in the hierarchy. Role with role_name='{role_name}' appears {role_names.count(role_name)} times in the hierarchy."

                if error_message not in errors_list:
                    errors_list.append(error_message)

        if len(errors_list) > 0:
            raise InvalidRoleHierarchyError(errors_list)

        # Now validate the tree

        # Exactly one role should have no parent
        root_nodes = [role for role in self.roles if role["reporting_role_uid"] is None]

        if len(root_nodes) == 0:
            errors_list.append(
                f"The hierarchy should have exactly one top level role (ie, a role with no parent). The current hierarchy has 0 roles with no parent."
            )
        elif len(root_nodes) > 1:
            errors_list.append(
                f"The hierarchy should have exactly one top level role (ie, a role with no parent). The current hierarchy has {len(root_nodes)} roles with no parent:\n{', '.join([role['role_name'] for role in root_nodes])}"
            )

        if len(errors_list) > 0:
            raise InvalidRoleHierarchyError(errors_list)

        # Traverse the tree to validate the following:
        # 1. Each role should have at most one child role
        # 2. The role hierarchy should not have any cycles
        # 3. There are no roles that couldn't be visited from the top level role (graph is connected)
        root_node = root_nodes[0]
        visited_nodes = [root_node]

        while True:
            child_nodes = [
                role
                for role in self.roles
                if role["reporting_role_uid"] == visited_nodes[-1]["role_uid"]
            ]
            if len(child_nodes) > 1:
                errors_list.append(
                    f"Each role should have at most one child role. Role '{visited_nodes[-1]['role_name']}' has {len(child_nodes)} child roles:\n{', '.join([role['role_name'] for role in child_nodes])}"
                )
                break
            elif len(child_nodes) == 1:
                if child_nodes[0]["role_uid"] in [
                    role["role_uid"] for role in visited_nodes
                ]:
                    errors_list.append(
                        f"The role hierarchy should not have any cycles. The current hierarchy has a cycle starting with role '{child_nodes[0]['role_name']}'."
                    )
                    break
                visited_nodes.append(child_nodes[0])
            elif len(child_nodes) == 0:
                break

        if len(errors_list) > 0:
            raise InvalidRoleHierarchyError(errors_list)

        # Now check that all nodes were visited
        if len(visited_nodes) != len(self.roles):
            unvisited_nodes = [
                role
                for role in self.roles
                if role["role_uid"]
                not in [visited_node["role_uid"] for visited_node in visited_nodes]
            ]

            errors_list.append(
                f"All roles in the hierarchy should be able to be connected back to the top level role via a chain of parent role references. The current hierarchy has {len(unvisited_nodes)} roles that cannot be connected:\n{', '.join([role['role_name'] for role in unvisited_nodes])}"
            )

            # Attempt to diagnose the unvisited nodes
            # Not exhaustive of all issues
            for role in unvisited_nodes:
                # Check for self-referencing
                if role["reporting_role_uid"] == role["role_uid"]:
                    errors_list.append(
                        f"Role '{role['role_name']}' is referenced as its own parent. Self-referencing is not allowed."
                    )

                # Check for parent referencing a non-existent role
                elif role["reporting_role_uid"] not in [
                    role["role_uid"] for role in self.roles
                ]:
                    errors_list.append(
                        f"Role '{role['role_name']}' references a parent role with unique id '{role['reporting_role_uid']}' that is not found in the hierarchy."
                    )

        if len(errors_list) > 0:
            raise InvalidRoleHierarchyError(errors_list)

        return


def check_if_survey_admin(user_uid, survey_uid):
    """
    Return a boolean indicating whether the given user
    is a survey admin for the given survey
    """

    # Check if the user is survey admin
    survey_admin_entry = SurveyAdmin.query.filter_by(
        user_uid=user_uid, survey_uid=survey_uid
    ).first()

    if survey_admin_entry:
        return True
    return False
