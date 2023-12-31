"""empty message

Revision ID: c53c56ff083c
Revises: 
Create Date: 2023-09-16 11:16:59.405632

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'c53c56ff083c'
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    # ### commands auto generated by Alembic - please adjust! ###
    op.create_table('station',
    sa.Column('id', sa.UUID(), nullable=False),
    sa.Column('serial', sa.String(), nullable=True),
    sa.Column('name', sa.String(), nullable=True),
    sa.Column('is_active', sa.Boolean(), nullable=True),
    sa.Column('is_protected', sa.Boolean(), nullable=True),
    sa.Column('hashed_wifi_data', sa.String(), nullable=True),
    sa.Column('created_at', sa.TIMESTAMP(timezone=True), nullable=True),
    sa.Column('updated_at', sa.TIMESTAMP(timezone=True), nullable=True),
    sa.Column('region', sa.Enum('CENTRAL', 'NORTHWEST', 'SOUTH', 'SIBERIA', name='regionenum'), nullable=True),
    sa.Column('comment', sa.String(), nullable=True),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('serial')
    )
    op.create_table('users',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('email', sa.String(length=50), nullable=True),
    sa.Column('first_name', sa.String(length=50), nullable=True),
    sa.Column('last_name', sa.String(length=50), nullable=True),
    sa.Column('role', sa.Enum('SYSADMIN', 'MANAGER', 'REGION_MANAGER', 'INSTALLER', 'LAUNDRY', name='roleenum'), nullable=True),
    sa.Column('disabled', sa.Boolean(), nullable=True),
    sa.Column('hashed_password', sa.String(), nullable=True),
    sa.Column('registered_at', sa.TIMESTAMP(timezone=True), server_default=sa.text('now()'), nullable=True),
    sa.Column('last_action_at', sa.TIMESTAMP(timezone=True), nullable=True),
    sa.Column('region', sa.Enum('CENTRAL', 'NORTHWEST', 'SOUTH', 'SIBERIA', name='regionenum'), nullable=True),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_users_email'), 'users', ['email'], unique=True)
    op.create_table('errors',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('station_id', sa.UUID(), nullable=True),
    sa.Column('code', sa.Float(), nullable=False),
    sa.Column('event', sa.String(), nullable=False),
    sa.Column('content', sa.String(), nullable=False),
    sa.Column('sended_from', sa.Enum('STATION', 'SERVER', name='logfromenum'), nullable=False),
    sa.Column('timestamp', sa.TIMESTAMP(timezone=True), server_default=sa.text('now()'), nullable=True),
    sa.Column('action', sa.Enum('ERROR_STATION_CONTROL_STATUS_START', 'ERROR_STATION_CONTROL_STATUS_END', 'STATION_TURN_OFF', 'STATION_TURN_ON', 'WASHING_MACHINE_TURN_ON', 'WASHING_MACHINE_TURN_OFF', 'WASHING_AGENTS_CHANGE_VOLUME', 'STATION_SETTINGS_CHANGE', 'STATION_START_MANUAL_WORKING', 'STATION_WORKING_PROCESS', 'STATION_MAINTENANCE_START', 'STATION_MAINTENANCE_END', 'STATION_ACTIVATE', name='logactionenum'), nullable=True),
    sa.Column('scope', sa.Enum('PUBLIC', 'SERVICE', 'ALL', name='errortypeenum'), nullable=False),
    sa.ForeignKeyConstraint(['station_id'], ['station.id'], onupdate='CASCADE', ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_table('logs',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('station_id', sa.UUID(), nullable=True),
    sa.Column('code', sa.Float(), nullable=False),
    sa.Column('event', sa.String(), nullable=False),
    sa.Column('content', sa.String(), nullable=False),
    sa.Column('sended_from', sa.Enum('STATION', 'SERVER', name='logfromenum'), nullable=False),
    sa.Column('timestamp', sa.TIMESTAMP(timezone=True), server_default=sa.text('now()'), nullable=True),
    sa.Column('action', sa.Enum('ERROR_STATION_CONTROL_STATUS_START', 'ERROR_STATION_CONTROL_STATUS_END', 'STATION_TURN_OFF', 'STATION_TURN_ON', 'WASHING_MACHINE_TURN_ON', 'WASHING_MACHINE_TURN_OFF', 'WASHING_AGENTS_CHANGE_VOLUME', 'STATION_SETTINGS_CHANGE', 'STATION_START_MANUAL_WORKING', 'STATION_WORKING_PROCESS', 'STATION_MAINTENANCE_START', 'STATION_MAINTENANCE_END', 'STATION_ACTIVATE', name='logactionenum'), nullable=True),
    sa.ForeignKeyConstraint(['station_id'], ['station.id'], onupdate='CASCADE', ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_table('refresh_token',
    sa.Column('user_id', sa.Integer(), nullable=False),
    sa.Column('data', sa.String(), nullable=True),
    sa.Column('created_at', sa.TIMESTAMP(timezone=True), server_default=sa.text('now()'), nullable=True),
    sa.Column('expires_at', sa.TIMESTAMP(timezone=True), nullable=True),
    sa.ForeignKeyConstraint(['user_id'], ['users.id'], onupdate='CASCADE', ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('user_id'),
    sa.UniqueConstraint('data')
    )
    op.create_table('station_control',
    sa.Column('station_id', sa.UUID(), nullable=False),
    sa.Column('status', sa.Enum('AWAITING', 'WORKING', 'MAINTENANCE', 'ERROR', name='stationstatusenum'), nullable=True),
    sa.Column('program_step', sa.JSON(), nullable=True),
    sa.Column('washing_machine', sa.JSON(), nullable=True),
    sa.Column('washing_agents', sa.JSON(), nullable=True),
    sa.Column('washing_machines_queue', sa.JSON(), nullable=True),
    sa.Column('updated_at', sa.TIMESTAMP(timezone=True), nullable=True),
    sa.ForeignKeyConstraint(['station_id'], ['station.id'], onupdate='CASCADE', ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('station_id'),
    sa.UniqueConstraint('station_id')
    )
    op.create_table('station_program',
    sa.Column('station_id', sa.UUID(), nullable=False),
    sa.Column('name', sa.String(), nullable=False),
    sa.Column('program_step', sa.Integer(), nullable=False),
    sa.Column('program_number', sa.Integer(), nullable=False),
    sa.Column('washing_agents', sa.JSON(), nullable=True),
    sa.Column('updated_at', sa.TIMESTAMP(timezone=True), nullable=True),
    sa.ForeignKeyConstraint(['station_id'], ['station.id'], onupdate='CASCADE', ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('station_id', 'program_step')
    )
    op.create_table('station_settings',
    sa.Column('station_id', sa.UUID(), nullable=False),
    sa.Column('station_power', sa.Boolean(), nullable=True),
    sa.Column('teh_power', sa.Boolean(), nullable=True),
    sa.Column('updated_at', sa.TIMESTAMP(timezone=True), nullable=True),
    sa.ForeignKeyConstraint(['station_id'], ['station.id'], onupdate='CASCADE', ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('station_id'),
    sa.UniqueConstraint('station_id')
    )
    op.create_table('users_stations',
    sa.Column('user_id', sa.Integer(), nullable=False),
    sa.Column('station_id', sa.UUID(), nullable=False),
    sa.ForeignKeyConstraint(['station_id'], ['station.id'], onupdate='CASCADE', ondelete='CASCADE'),
    sa.ForeignKeyConstraint(['user_id'], ['users.id'], onupdate='CASCADE', ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('user_id', 'station_id'),
    sa.UniqueConstraint('station_id')
    )
    op.create_table('washing_agent',
    sa.Column('station_id', sa.UUID(), nullable=False),
    sa.Column('agent_number', sa.Integer(), nullable=False),
    sa.Column('volume', sa.Integer(), nullable=True),
    sa.Column('rollback', sa.Boolean(), nullable=True),
    sa.ForeignKeyConstraint(['station_id'], ['station.id'], onupdate='CASCADE', ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('station_id', 'agent_number', name='station_id_agent_number_pkey')
    )
    op.create_table('washing_machine',
    sa.Column('station_id', sa.UUID(), nullable=False),
    sa.Column('machine_number', sa.Integer(), nullable=False),
    sa.Column('volume', sa.Integer(), nullable=True),
    sa.Column('is_active', sa.Boolean(), nullable=True),
    sa.Column('track_length', sa.Float(), nullable=True),
    sa.ForeignKeyConstraint(['station_id'], ['station.id'], onupdate='CASCADE', ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('station_id', 'machine_number', name='station_id_machine_number_pkey')
    )
    # ### end Alembic commands ###


def downgrade() -> None:
    # ### commands auto generated by Alembic - please adjust! ###
    op.drop_table('washing_machine')
    op.drop_table('washing_agent')
    op.drop_table('users_stations')
    op.drop_table('station_settings')
    op.drop_table('station_program')
    op.drop_table('station_control')
    op.drop_table('refresh_token')
    op.drop_table('logs')
    op.drop_table('errors')
    op.drop_index(op.f('ix_users_email'), table_name='users')
    op.drop_table('users')
    op.drop_table('station')
    # ### end Alembic commands ###
