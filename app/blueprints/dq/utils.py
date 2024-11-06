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

    # Raise error if both all_questions and question_name are provided
    if all_questions and question_name:
        raise Exception(
            "Question name cannot be provided if all questions is selected."
        )

    # Check if the question name is valid, when check is active
    if question_name and active is True:
        scto_question = SCTOQuestion.query.filter(
            SCTOQuestion.form_uid == form_uid,
            SCTOQuestion.question_name == question_name,
        ).first()

        if scto_question is None:
            raise Exception(
                f"Question name '{question_name}' not found in form definition. Active checks must have a valid question name."
            )

    # Check if the filter question names are valid, when check is active
    if filters and active is True:
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

    # Check if check components are valid based on type of check

    # 1. For missing (4), don't knows (5) and refusals checks (6), value field is required
    if type_id in [4, 5, 6]:
        if check_components.get("value") is None:
            raise Exception(
                "Value field is required for missing, don't knows and refusals checks"
            )

    # To do: Add check components validation for other check types

    return True
