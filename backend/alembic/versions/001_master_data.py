"""001_master_data_tables

Revision ID: 001_master_data
Revises: 
Create Date: 2026-09-25 22:40:00

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = '001_master_data'
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Create locations table
    op.create_table(
        'locations',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column('name', sa.String(), nullable=False, unique=True),
        sa.Column('region', sa.String(), nullable=False),
        sa.Column('latitude', sa.Numeric(9, 6), nullable=False),
        sa.Column('longitude', sa.Numeric(9, 6), nullable=False),
        sa.Column('role_hint', sa.String(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )
    
    # Create commodities table
    op.create_table(
        'commodities',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column('name', sa.String(), nullable=False, unique=True),
        sa.Column('unit', sa.String(), nullable=False, server_default='kg'),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )
    
    # Create suppliers table
    op.create_table(
        'suppliers',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column('name', sa.String(), nullable=False),
        sa.Column('location_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('locations.id'), nullable=False),
        sa.Column('reliability_score', sa.Numeric(3, 2), nullable=False, server_default='0.80'),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.CheckConstraint('reliability_score >= 0 AND reliability_score <= 1', name='check_reliability'),
    )
    
    # Create users table
    op.create_table(
        'users',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column('name', sa.String(), nullable=False),
        sa.Column('email', sa.String(), nullable=False, unique=True),
        sa.Column('password_hash', sa.String(), nullable=False),
        sa.Column('role', sa.String(), nullable=False),
        sa.Column('location_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('locations.id'), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.CheckConstraint("role IN ('sppg_staff', 'dinas_admin')", name='check_user_role'),
    )
    
    # Create indexes
    op.create_index('idx_locations_name', 'locations', ['name'])
    op.create_index('idx_commodities_name', 'commodities', ['name'])
    op.create_index('idx_suppliers_location', 'suppliers', ['location_id'])
    op.create_index('idx_users_email', 'users', ['email'])
    op.create_index('idx_users_location', 'users', ['location_id'])


def downgrade() -> None:
    op.drop_index('idx_users_location', table_name='users')
    op.drop_index('idx_users_email', table_name='users')
    op.drop_index('idx_suppliers_location', table_name='suppliers')
    op.drop_index('idx_commodities_name', table_name='commodities')
    op.drop_index('idx_locations_name', table_name='locations')
    op.drop_table('users')
    op.drop_table('suppliers')
    op.drop_table('commodities')
    op.drop_table('locations')
