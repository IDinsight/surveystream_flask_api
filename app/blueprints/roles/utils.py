def run_role_hierarchy_validations(roles):
    """
    Function to run validations on the role hierarchy and return a list of errors

    :param roles: List of roles for the survey
    """
    errors_list = []

    # Prechecks before we validate the tree

    # There should be no duplicates on role_uid
    role_uids = [role["role_uid"] for role in roles]
    for role_uid in role_uids:
        if role_uids.count(role_uid) > 1:
            error_message = f"Each role unique id defined in the role hierarchy should appear exactly once in the hierarchy. Role with role_uid='{role_uid}' appears {role_uids.count(role_uid)} times in the hierarchy."

            if error_message not in errors_list:
                errors_list.append(error_message)

    # There should be no duplicates on role_name
    role_names = [role["role_name"] for role in roles]
    for role_name in role_names:
        if role_names.count(role_name) > 1:
            error_message = f"Each role name defined in the role hierarchy should appear exactly once in the hierarchy. Role with role_name='{role_name}' appears {role_names.count(role_name)} times in the hierarchy."

            if error_message not in errors_list:
                errors_list.append(error_message)

    if len(errors_list) > 0:
        return errors_list

    # Now validate the tree

    # Exactly one role should have no parent
    root_nodes = [role for role in roles if role["reporting_role_uid"] is None]

    if len(root_nodes) == 0:
        errors_list.append(
            f"The hierarchy should have exactly one top level role (ie, a role with no parent). The current hierarchy has 0 roles with no parent."
        )
        return errors_list
    elif len(root_nodes) > 1:
        errors_list.append(
            f"The hierarchy should have exactly one top level role (ie, a role with no parent). The current hierarchy has {len(root_nodes)} roles with no parent:\n{', '.join([role['role_name'] for role in root_nodes])}"
        )
        return errors_list

    # Traverse the tree to validate the following:
    # 1. Each role should have at most one child role
    # 2. The role hierarchy should not have any cycles
    # 3. There are no roles that couldn't be visited from the top level role (graph is connected)
    root_node = root_nodes[0]
    visited_nodes = [root_node]

    while True:
        child_nodes = [
            role
            for role in roles
            if role["reporting_role_uid"] == visited_nodes[-1]["role_uid"]
        ]

        if len(child_nodes) > 1:
            errors_list.append(
                f"Each role should have at most one child role. Role '{visited_nodes[-1]['role_name']}' has {len(child_nodes)} child roles:\n{', '.join([role['role_name'] for role in child_nodes])}"
            )
            return errors_list
        elif len(child_nodes) == 1:
            if child_nodes[0]["role_uid"] in [
                role["role_uid"] for role in visited_nodes
            ]:
                errors_list.append(
                    f"The role hierarchy should not have any cycles. The current hierarchy has a cycle starting with role '{child_nodes[0]['role_name']}'."
                )
                return errors_list
            visited_nodes.append(child_nodes[0])
        elif len(child_nodes) == 0:
            break

    # Now check that all nodes were visited
    if len(visited_nodes) != len(roles):
        unvisited_nodes = [
            role
            for role in roles
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
            elif role["reporting_role_uid"] not in [role["role_uid"] for role in roles]:
                errors_list.append(
                    f"Role '{role['role_name']}' references a parent role with unique id '{role['reporting_role_uid']}' that is not found in the hierarchy."
                )

    return errors_list
