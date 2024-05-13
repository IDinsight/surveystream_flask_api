import random
import string
from app import mail
from flask_mail import Message
from flask import current_app


def generate_invite_code():
    """Generate a random 8-character invite code."""
    return "".join(random.choices(string.ascii_uppercase + string.digits, k=8))


def send_invite_email(email, invite_code):
    """Send an invitation email to the user with the invite code."""
    rp_message = Message(
        subject="Welcome to SurveyStream - Invitation",
        html="Welcome to SurveyStream! Your invitation link is <a href='%s/complete-registration/%s'>here</a>.<br><br>Click on the link to complete your registration. The link will expire in 24 hours."
        % (
            current_app.config["REACT_BASE_URL"],
            invite_code,
        ),
        recipients=[email],
    )
    mail.send(rp_message)
