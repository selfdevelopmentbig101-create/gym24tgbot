"""
Privacy guard: /deleteme deletes the users row and relies on ON DELETE CASCADE
for everything else. This test fails if a future table stores user data
without cascading, so new stages can't silently break /deleteme.
"""
from database.base import Base
from database import models  # noqa: F401


def test_every_user_owned_table_cascades_from_users():
    problems = []
    for table in Base.metadata.sorted_tables:
        for fk in table.foreign_keys:
            if fk.column.table.name == "users" and fk.ondelete != "CASCADE":
                problems.append(f"{table.name}.{fk.parent.name}")
        if "user_id" in table.columns and not any(
                fk.column.table.name == "users" for fk in table.columns["user_id"].foreign_keys):
            problems.append(f"{table.name}.user_id has no foreign key to users")
    assert not problems, problems


def test_child_tables_cascade_from_their_parents():
    # e.g. plan_days -> workout_plans -> users: every link in the chain must cascade.
    problems = [f"{table.name}.{fk.parent.name}"
                for table in Base.metadata.sorted_tables for fk in table.foreign_keys
                if fk.column.table.name != "exercises" and fk.ondelete != "CASCADE"]
    assert not problems, problems
