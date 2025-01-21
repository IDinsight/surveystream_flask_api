from app.blueprints.forms.models import Form, SCTOQuestion


def validate_dq_check(
    form_uid,
    type_id,
    all_questions,
    question_name,
    dq_scto_form_uid,
    check_components,
    filters,
    active,
):
    """
    Function to validate DQ Check data

    """

    # Raise error if both all_questions and question_name are not provided
    if not all_questions and not question_name:
        raise Exception(
            "Question name is required if check is not applied on all questions."
        )

    # all_questions are only allowed for missing (4), don't knows (5) and refusals (6) checks
    if all_questions and type_id not in [4, 5, 6]:
        raise Exception(
            "All questions is only allowed for missing, don't knows and refusals checks"
        )

    # Raise error if both all_questions and question_name are provided
    if all_questions and question_name:
        raise Exception(
            "Question name cannot be provided if all questions is selected."
        )

    # Check if the question name is valid, when check is active
    # For protocol (8) and spotcheck (9) checks, question name is from DQ form which is checked later
    if question_name and active is True and type_id not in [8, 9]:
        scto_question = SCTOQuestion.query.filter(
            SCTOQuestion.form_uid == form_uid,
            SCTOQuestion.question_name == question_name,
        ).first()

        if scto_question is None:
            raise Exception(
                f"Question name '{question_name}' not found in form definition. Active checks must have a valid question name."
            )

    # Check if the filter question names are valid, when check is active
    if filters and active is True and type_id not in [7, 8, 9]:
        for filter_group in filters:
            for filter_item in filter_group.get("filter_group"):
                filter_question_name = filter_item["question_name"]
                filter_question = SCTOQuestion.query.filter(
                    SCTOQuestion.form_uid == form_uid,
                    SCTOQuestion.question_name == filter_question_name,
                ).first()

                if filter_question is None:
                    raise Exception(
                        f"Question name '{filter_question_name}' used in filters not found in form definition. Active checks must have valid question names in filters."
                    )

    # for mismatch (7), protocol (8) and spotcheck (9), check if dq question form is valid
    if type_id in [7, 8, 9]:
        if dq_scto_form_uid is None:
            raise Exception(
                "DQ SCTO Form UID is required for mismatch, protocol and spotcheck checks"
            )

        dq_form = Form.query.filter(
            Form.form_uid == dq_scto_form_uid, Form.form_type == "dq"
        ).first()

        if dq_form is None:
            raise Exception(f"DQ Form with form_uid {dq_scto_form_uid} not found")

    else:
        if dq_scto_form_uid is not None:
            raise Exception("DQ SCTO Form UID is not allowed for this type of check")

    # for mismatch (7), protocol (8) and spotcheck (9), check if question name is present in dq form
    if type_id in [7, 8, 9] and active is True:
        dq_scto_question = SCTOQuestion.query.filter(
            SCTOQuestion.form_uid == dq_scto_form_uid,
            SCTOQuestion.question_name == question_name,
        ).first()

        if dq_scto_question is None:
            raise Exception(
                f"Question name '{question_name}' not found in DQ form definition. Active checks must have a valid question name."
            )

    # for mismatch (7), protocol (8) and spotcheck (9), check if question name used in filters is present in dq form
    if type_id in [7, 8, 9] and filters and active is True:
        for filter_group in filters:
            for filter_item in filter_group.get("filter_group"):
                filter_question_name = filter_item["question_name"]
                filter_question = SCTOQuestion.query.filter(
                    SCTOQuestion.form_uid == dq_scto_form_uid,
                    SCTOQuestion.question_name == filter_question_name,
                ).first()

                if filter_question is None:
                    raise Exception(
                        f"Question name '{filter_question_name}' used in filters not found in DQ form definition. Active checks must have valid question names in filters."
                    )

    # Check if check components are valid based on type of check
    # 1.a For missing (4), don't knows (5) and refusals checks (6), value field is required
    if type_id in [4, 5, 6]:
        if check_components.get("value") is None or check_components.get("value") == []:
            raise Exception(
                "Value field is required for missing, don't knows and refusals checks"
            )
    else:
        # 1.b For other checks, value field is not required
        if (
            check_components.get("value") is not None
            and check_components.get("value") != []
        ):
            raise Exception("Value field is not allowed for this type of check")

    # 2. For outlier (3), outlier_metric and outlier_value fields are required
    if type_id == 3:
        if check_components.get("outlier_metric") is None:
            raise Exception("Outlier metric field is required for outlier checks")

        if check_components.get("outlier_value") is None:
            raise Exception("Outlier value field is required for outlier checks")
    else:
        # 2. For other checks, outlier_metric and outlier_value fields are not required
        if check_components.get("outlier_metric") is not None:
            raise Exception(
                "Outlier metric field is not allowed for this type of check"
            )

        if check_components.get("outlier_value") is not None:
            raise Exception("Outlier value field is not allowed for this type of check")

    # 3. For constraint (2), one of hard_min, hard_max, soft_min, soft_max fields is required
    if type_id == 2:
        if (
            check_components.get("hard_min") is None
            and check_components.get("hard_max") is None
            and check_components.get("soft_min") is None
            and check_components.get("soft_max") is None
        ):
            raise Exception(
                "At least one of hard_min, hard_max, soft_min, soft_max fields is required for constraint checks"
            )
    else:
        # 3. For other checks, one of hard_min, hard_max, soft_min, soft_max fields is not required
        if (
            check_components.get("hard_min") is not None
            or check_components.get("hard_max") is not None
            or check_components.get("soft_min") is not None
            or check_components.get("soft_max") is not None
        ):
            raise Exception(
                "The hard_min, hard_max, soft_min, soft_max fields are not allowed for this type of check"
            )

    # 4. For any check other than spotcheck (9), spotcheck_score_name is not allowed
    # For spotcheck (9), spotcheck_score_name is an optional field, hence no validation required
    if type_id != 9:
        if check_components.get("spotcheck_score_name") is not None:
            raise Exception(
                "Spotcheck score name is not allowed for this type of check"
            )

    # 5. For GPS checks (10), threshold with either gps variable or grid_id fields is required
    if type_id == 10:
        if check_components.get("threshold") is None:
            raise Exception("Threshold field is required for gps checks")

        gps_variable = check_components.get("gps_variable")
        grid_id = check_components.get("grid_id")

        # Check gps_variable or grid_id field is present or not
        if ( gps_variable is None and grid_id is None ):
            raise Exception(
                "Either gps_variable or grid_id field is required for gps checks"
            )

        # Check both should not be present at same time
        if gps_variable and grid_id:
            raise Exception(
                "Either gps_variable or grid_id field is required for gps checks, not both"
            )

        # If gps_variable is present then check if it is a valid question in form definition
        if gps_variable is not None and active is True:
            scto_question = SCTOQuestion.query.filter(
                SCTOQuestion.form_uid == form_uid,
                SCTOQuestion.question_name == gps_variable,
            ).first()

            if scto_question is None:
                raise Exception(
                    f"Question name '{gps_variable}' not found in form definition. Active checks must have a valid question name for GPS checks."
                )


        # If grid_id is present then check if it is a valid question in form definition
        if grid_id is not None and active is True:
            scto_question = SCTOQuestion.query.filter(
                SCTOQuestion.form_uid == form_uid,
                SCTOQuestion.question_name == grid_id,
            ).first()

            if scto_question is None:
                raise Exception(
                    f"Question name '{grid_id}' not found in form definition. Active checks must have a valid question name for GPS checks."
                )

    else:
        # For other checks, threshold, gps variable and grid id fields are not required
        if check_components.get("threshold") is not None:
            raise Exception("Threshold field is not allowed for this type of check")

        if check_components.get("gps_variable") is not None:
            raise Exception(
                "GPS variable field is not allowed for this type of check"
            )

        if check_components.get("grid_id") is not None:
            raise Exception("Grid id field is not allowed for this type of check")

    return True
