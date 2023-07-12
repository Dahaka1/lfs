"""empty message

Revision ID: f3b3153e7c73
Revises: 
Create Date: 2023-07-12 10:44:06.211149

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'f3b3153e7c73'
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    # ### commands auto generated by Alembic - please adjust! ###
    op.create_table('station',
    sa.Column('id', sa.UUID(), nullable=False),
    sa.Column('location', sa.JSON(), nullable=False),
    sa.Column('is_active', sa.Boolean(), nullable=True),
    sa.Column('is_protected', sa.Boolean(), nullable=True),
    sa.Column('hashed_wifi_data', sa.String(), nullable=True),
    sa.Column('created_at', sa.DateTime(), server_default=sa.text('now()'), nullable=True),
    sa.Column('updated_at', sa.DateTime(), nullable=True),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_table('users',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('email', sa.String(length=50), nullable=True),
    sa.Column('first_name', sa.String(length=50), nullable=True),
    sa.Column('last_name', sa.String(length=50), nullable=True),
    sa.Column('role', sa.Enum('SYSADMIN', 'MANAGER', 'INSTALLER', 'LAUNDRY', name='roleenum'), nullable=True),
    sa.Column('disabled', sa.Boolean(), nullable=True),
    sa.Column('hashed_password', sa.String(), nullable=True),
    sa.Column('registered_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=True),
    sa.Column('last_action_at', sa.DateTime(timezone=True), nullable=True),
    sa.Column('email_confirmed', sa.Boolean(), nullable=True),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_users_email'), 'users', ['email'], unique=True)
    op.create_index(op.f('ix_users_id'), 'users', ['id'], unique=False)
    op.create_table('changes_log',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('timestamp', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=True),
    sa.Column('station_id', sa.UUID(), nullable=True),
    sa.Column('user_id', sa.Integer(), nullable=True),
    sa.Column('content', sa.String(), nullable=False),
    sa.ForeignKeyConstraint(['station_id'], ['station.id'], onupdate='CASCADE', ondelete='SET NULL'),
    sa.ForeignKeyConstraint(['user_id'], ['users.id'], onupdate='CASCADE', ondelete='SET NULL'),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_changes_log_station_id'), 'changes_log', ['station_id'], unique=False)
    op.create_table('errors_log',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('station_id', sa.UUID(), nullable=True),
    sa.Column('timestamp', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=True),
    sa.Column('code', sa.Integer(), nullable=True),
    sa.Column('content', sa.String(), nullable=True),
    sa.ForeignKeyConstraint(['station_id'], ['station.id'], onupdate='CASCADE', ondelete='SET NULL'),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_errors_log_station_id'), 'errors_log', ['station_id'], unique=False)
    op.create_table('registration_code',
    sa.Column('user_id', sa.Integer(), nullable=False),
    sa.Column('sended_to', sa.String(), nullable=True),
    sa.Column('sended_from', sa.String(), nullable=True),
    sa.Column('hashed_code', sa.String(), nullable=True),
    sa.Column('sended_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.Column('is_confirmed', sa.Boolean(), nullable=True),
    sa.Column('confirmed_at', sa.DateTime(timezone=True), nullable=True),
    sa.Column('expires_at', sa.DateTime(timezone=True), nullable=True),
    sa.ForeignKeyConstraint(['user_id'], ['users.id'], onupdate='CASCADE', ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('user_id', 'sended_at')
    )
    op.create_index(op.f('ix_registration_code_user_id'), 'registration_code', ['user_id'], unique=False)
    op.create_table('station_control',
    sa.Column('station_id', sa.UUID(), nullable=False),
    sa.Column('status', sa.Enum('AWAITING', 'WORKING', name='stationstatusenum'), nullable=True),
    sa.Column('program_step', sa.JSON(), nullable=True),
    sa.Column('washing_machine', sa.JSON(), nullable=True),
    sa.Column('washing_agents', sa.JSON(), nullable=True),
    sa.Column('updated_at', sa.DateTime(), nullable=True),
    sa.ForeignKeyConstraint(['station_id'], ['station.id'], onupdate='CASCADE', ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('station_id')
    )
    op.create_index(op.f('ix_station_control_station_id'), 'station_control', ['station_id'], unique=False)
    op.create_table('station_program',
    sa.Column('station_id', sa.UUID(), nullable=False),
    sa.Column('program_step', sa.Integer(), nullable=False),
    sa.Column('program_number', sa.Integer(), nullable=False),
    sa.Column('washing_agents', sa.JSON(), nullable=True),
    sa.Column('updated_at', sa.DateTime(), nullable=True),
    sa.ForeignKeyConstraint(['station_id'], ['station.id'], onupdate='CASCADE', ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('station_id', 'program_step')
    )
    op.create_index(op.f('ix_station_program_station_id'), 'station_program', ['station_id'], unique=False)
    op.create_table('station_programs_log',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('timestamp', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=True),
    sa.Column('station_id', sa.UUID(), nullable=True),
    sa.Column('program_step', sa.Integer(), nullable=True),
    sa.Column('washing_agents_dosage', sa.JSON(), nullable=True),
    sa.ForeignKeyConstraint(['station_id'], ['station.id'], onupdate='CASCADE', ondelete='SET NULL'),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_station_programs_log_station_id'), 'station_programs_log', ['station_id'], unique=False)
    op.create_table('station_settings',
    sa.Column('station_id', sa.UUID(), nullable=False),
    sa.Column('station_power', sa.Boolean(), nullable=True),
    sa.Column('teh_power', sa.Boolean(), nullable=True),
    sa.Column('updated_at', sa.DateTime(), nullable=True),
    sa.ForeignKeyConstraint(['station_id'], ['station.id'], onupdate='CASCADE', ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('station_id')
    )
    op.create_index(op.f('ix_station_settings_station_id'), 'station_settings', ['station_id'], unique=False)
    op.create_table('washing_agent',
    sa.Column('station_id', sa.UUID(), nullable=False),
    sa.Column('agent_number', sa.Integer(), nullable=False),
    sa.Column('concentration_rate', sa.Integer(), nullable=True),
    sa.Column('rollback', sa.Boolean(), nullable=True),
    sa.ForeignKeyConstraint(['station_id'], ['station.id'], onupdate='CASCADE', ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('station_id', 'agent_number', name='station_id_agent_number_pkey')
    )
    op.create_index(op.f('ix_washing_agent_agent_number'), 'washing_agent', ['agent_number'], unique=False)
    op.create_index(op.f('ix_washing_agent_station_id'), 'washing_agent', ['station_id'], unique=False)
    op.create_table('washing_agents_using_log',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('timestamp', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=True),
    sa.Column('station_id', sa.UUID(), nullable=True),
    sa.Column('washing_machine_number', sa.Integer(), nullable=True),
    sa.Column('washing_agent_number', sa.Integer(), nullable=True),
    sa.Column('dosage', sa.Integer(), nullable=True),
    sa.ForeignKeyConstraint(['station_id'], ['station.id'], onupdate='CASCADE', ondelete='SET NULL'),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_washing_agents_using_log_station_id'), 'washing_agents_using_log', ['station_id'], unique=False)
    op.create_table('washing_machine',
    sa.Column('station_id', sa.UUID(), nullable=False),
    sa.Column('machine_number', sa.Integer(), nullable=False),
    sa.Column('volume', sa.Integer(), nullable=True),
    sa.Column('is_active', sa.Boolean(), nullable=True),
    sa.ForeignKeyConstraint(['station_id'], ['station.id'], onupdate='CASCADE', ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('station_id', 'machine_number', name='station_id_machine_number_pkey')
    )
    op.create_index(op.f('ix_washing_machine_machine_number'), 'washing_machine', ['machine_number'], unique=False)
    op.create_index(op.f('ix_washing_machine_station_id'), 'washing_machine', ['station_id'], unique=False)
    # ### end Alembic commands ###


def downgrade() -> None:
    # ### commands auto generated by Alembic - please adjust! ###
    op.drop_index(op.f('ix_washing_machine_station_id'), table_name='washing_machine')
    op.drop_index(op.f('ix_washing_machine_machine_number'), table_name='washing_machine')
    op.drop_table('washing_machine')
    op.drop_index(op.f('ix_washing_agents_using_log_station_id'), table_name='washing_agents_using_log')
    op.drop_table('washing_agents_using_log')
    op.drop_index(op.f('ix_washing_agent_station_id'), table_name='washing_agent')
    op.drop_index(op.f('ix_washing_agent_agent_number'), table_name='washing_agent')
    op.drop_table('washing_agent')
    op.drop_index(op.f('ix_station_settings_station_id'), table_name='station_settings')
    op.drop_table('station_settings')
    op.drop_index(op.f('ix_station_programs_log_station_id'), table_name='station_programs_log')
    op.drop_table('station_programs_log')
    op.drop_index(op.f('ix_station_program_station_id'), table_name='station_program')
    op.drop_table('station_program')
    op.drop_index(op.f('ix_station_control_station_id'), table_name='station_control')
    op.drop_table('station_control')
    op.drop_index(op.f('ix_registration_code_user_id'), table_name='registration_code')
    op.drop_table('registration_code')
    op.drop_index(op.f('ix_errors_log_station_id'), table_name='errors_log')
    op.drop_table('errors_log')
    op.drop_index(op.f('ix_changes_log_station_id'), table_name='changes_log')
    op.drop_table('changes_log')
    op.drop_index(op.f('ix_users_id'), table_name='users')
    op.drop_index(op.f('ix_users_email'), table_name='users')
    op.drop_table('users')
    op.drop_table('station')
    # ### end Alembic commands ###
