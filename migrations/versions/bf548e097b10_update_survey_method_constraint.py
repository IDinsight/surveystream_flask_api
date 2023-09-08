"""Update survey method constraint

Revision ID: bf548e097b10
Revises: 
Create Date: 2023-09-08 12:26:45.172707

"""

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = 'bf548e097b10'
down_revision = None
branch_labels = None
depends_on = None

def upgrade():
    # Modify the constraint condition to include 'mixed-mode'
    op.create_check_constraint(
        "ck_surveys_surveying_method",
        "surveys",
        sa.text(
            "surveying_method IN ('phone', 'in-person', 'mixed-mode')"
        ),
    )

def downgrade():
    # Remove the constraint
    op.drop_constraint("ck_surveys_surveying_method", "surveys")
