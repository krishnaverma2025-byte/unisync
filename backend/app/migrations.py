"""Non-destructive v1 -> v2 migration. Only additive, literal trusted DDL.
New databases get normal SQLAlchemy constraints; old databases get defaults and
new foreign keys without resetting registrations, accounts or timetable entries.
"""
from sqlalchemy import inspect, text
from .db import Base
UPGRADE = {
    'faculty': {'max_classes_day':'INTEGER NOT NULL DEFAULT 6 CHECK (max_classes_day > 0)', 'max_classes_week':'INTEGER NOT NULL DEFAULT 24 CHECK (max_classes_week > 0)'},
    'subjects': {'credits':'INTEGER NOT NULL DEFAULT 3 CHECK (credits >= 0)', 'difficulty':'INTEGER NOT NULL DEFAULT 3 CHECK (difficulty >= 1 AND difficulty <= 5)'},
    'sections': {'semester_id':'INTEGER REFERENCES semesters(id)'},
    'availability': {'status':"VARCHAR NOT NULL DEFAULT 'available' CHECK (status IN ('available','preferred','unavailable'))"},
}
def migrate(engine):
    Base.metadata.create_all(engine)
    with engine.begin() as conn:
        for table, columns in UPGRADE.items():
            existing={c['name'] for c in inspect(conn).get_columns(table)}
            for name, ddl in columns.items():
                if name not in existing:
                    conn.execute(text(f'ALTER TABLE {table} ADD COLUMN {name} {ddl}'))
        conn.execute(text('CREATE TABLE IF NOT EXISTS schema_versions (version INTEGER PRIMARY KEY)'))
        upgraded=conn.execute(text('SELECT COUNT(*) FROM schema_versions WHERE version = 2')).scalar()==0
        conn.execute(text('INSERT INTO schema_versions(version) SELECT 2 WHERE NOT EXISTS (SELECT 1 FROM schema_versions WHERE version = 2)'))
    return upgraded
