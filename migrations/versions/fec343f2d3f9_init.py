"""init

Revision ID: fec343f2d3f9
Revises: 
Create Date: 2025-03-04 01:50:46.001976

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = 'fec343f2d3f9'
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # ### commands auto generated by Alembic - please adjust! ###
    op.alter_column('crash_games', 'game_id',
               existing_type=sa.TEXT(),
               type_=sa.String(),
               nullable=True)
    op.alter_column('crash_games', 'hash_value',
               existing_type=sa.TEXT(),
               type_=sa.String(),
               nullable=True)
    op.alter_column('crash_games', 'crash_point',
               existing_type=sa.DOUBLE_PRECISION(precision=53),
               nullable=True)
    op.alter_column('crash_games', 'calculated_point',
               existing_type=sa.DOUBLE_PRECISION(precision=53),
               nullable=True)
    op.alter_column('crash_games', 'verified',
               existing_type=sa.BOOLEAN(),
               nullable=True,
               existing_server_default=sa.text('false'))
    op.alter_column('crash_games', 'created_at',
               existing_type=postgresql.TIMESTAMP(precision=3),
               nullable=True,
               existing_server_default=sa.text('CURRENT_TIMESTAMP'))
    op.alter_column('crash_games', 'updated_at',
               existing_type=postgresql.TIMESTAMP(precision=3),
               nullable=True)
    op.drop_index('crash_games_begin_time_end_time_idx', table_name='crash_games')
    op.drop_index('crash_games_crash_point_idx', table_name='crash_games')
    op.drop_index('crash_games_game_id_idx', table_name='crash_games')
    op.drop_index('crash_games_game_id_key', table_name='crash_games')
    op.create_index('ix_crash_games_begin_time', 'crash_games', ['begin_time'], unique=False)
    op.create_index('ix_crash_games_crash_point', 'crash_games', ['crash_point'], unique=False)
    op.create_index('ix_crash_games_created_at', 'crash_games', ['created_at'], unique=False)
    op.create_index('ix_crash_games_end_time', 'crash_games', ['end_time'], unique=False)
    op.create_index('ix_crash_games_verified', 'crash_games', ['verified'], unique=False)
    op.create_unique_constraint(None, 'crash_games', ['game_id'])
    op.alter_column('crash_stats', 'date',
               existing_type=postgresql.TIMESTAMP(precision=3),
               nullable=True)
    op.alter_column('crash_stats', 'games_count',
               existing_type=sa.INTEGER(),
               nullable=True)
    op.alter_column('crash_stats', 'average_crash',
               existing_type=sa.DOUBLE_PRECISION(precision=53),
               nullable=True)
    op.alter_column('crash_stats', 'median_crash',
               existing_type=sa.DOUBLE_PRECISION(precision=53),
               nullable=True)
    op.alter_column('crash_stats', 'max_crash',
               existing_type=sa.DOUBLE_PRECISION(precision=53),
               nullable=True)
    op.alter_column('crash_stats', 'min_crash',
               existing_type=sa.DOUBLE_PRECISION(precision=53),
               nullable=True)
    op.alter_column('crash_stats', 'created_at',
               existing_type=postgresql.TIMESTAMP(precision=3),
               nullable=True,
               existing_server_default=sa.text('CURRENT_TIMESTAMP'))
    op.alter_column('crash_stats', 'updated_at',
               existing_type=postgresql.TIMESTAMP(precision=3),
               nullable=True)
    op.drop_index('crash_stats_date_key', table_name='crash_stats')
    op.create_unique_constraint(None, 'crash_stats', ['date'])
    # ### end Alembic commands ###


def downgrade() -> None:
    # ### commands auto generated by Alembic - please adjust! ###
    op.drop_constraint(None, 'crash_stats', type_='unique')
    op.create_index('crash_stats_date_key', 'crash_stats', ['date'], unique=True)
    op.alter_column('crash_stats', 'updated_at',
               existing_type=postgresql.TIMESTAMP(precision=3),
               nullable=False)
    op.alter_column('crash_stats', 'created_at',
               existing_type=postgresql.TIMESTAMP(precision=3),
               nullable=False,
               existing_server_default=sa.text('CURRENT_TIMESTAMP'))
    op.alter_column('crash_stats', 'min_crash',
               existing_type=sa.DOUBLE_PRECISION(precision=53),
               nullable=False)
    op.alter_column('crash_stats', 'max_crash',
               existing_type=sa.DOUBLE_PRECISION(precision=53),
               nullable=False)
    op.alter_column('crash_stats', 'median_crash',
               existing_type=sa.DOUBLE_PRECISION(precision=53),
               nullable=False)
    op.alter_column('crash_stats', 'average_crash',
               existing_type=sa.DOUBLE_PRECISION(precision=53),
               nullable=False)
    op.alter_column('crash_stats', 'games_count',
               existing_type=sa.INTEGER(),
               nullable=False)
    op.alter_column('crash_stats', 'date',
               existing_type=postgresql.TIMESTAMP(precision=3),
               nullable=False)
    op.drop_constraint(None, 'crash_games', type_='unique')
    op.drop_index('ix_crash_games_verified', table_name='crash_games')
    op.drop_index('ix_crash_games_end_time', table_name='crash_games')
    op.drop_index('ix_crash_games_created_at', table_name='crash_games')
    op.drop_index('ix_crash_games_crash_point', table_name='crash_games')
    op.drop_index('ix_crash_games_begin_time', table_name='crash_games')
    op.create_index('crash_games_game_id_key', 'crash_games', ['game_id'], unique=True)
    op.create_index('crash_games_game_id_idx', 'crash_games', ['game_id'], unique=False)
    op.create_index('crash_games_crash_point_idx', 'crash_games', ['crash_point'], unique=False)
    op.create_index('crash_games_begin_time_end_time_idx', 'crash_games', ['begin_time', 'end_time'], unique=False)
    op.alter_column('crash_games', 'updated_at',
               existing_type=postgresql.TIMESTAMP(precision=3),
               nullable=False)
    op.alter_column('crash_games', 'created_at',
               existing_type=postgresql.TIMESTAMP(precision=3),
               nullable=False,
               existing_server_default=sa.text('CURRENT_TIMESTAMP'))
    op.alter_column('crash_games', 'verified',
               existing_type=sa.BOOLEAN(),
               nullable=False,
               existing_server_default=sa.text('false'))
    op.alter_column('crash_games', 'calculated_point',
               existing_type=sa.DOUBLE_PRECISION(precision=53),
               nullable=False)
    op.alter_column('crash_games', 'crash_point',
               existing_type=sa.DOUBLE_PRECISION(precision=53),
               nullable=False)
    op.alter_column('crash_games', 'hash_value',
               existing_type=sa.String(),
               type_=sa.TEXT(),
               nullable=False)
    op.alter_column('crash_games', 'game_id',
               existing_type=sa.String(),
               type_=sa.TEXT(),
               nullable=False)
    # ### end Alembic commands ###
