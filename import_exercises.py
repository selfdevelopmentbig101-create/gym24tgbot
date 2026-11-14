"""
Import (or re-import) data/core_exercises.json into the database.

    python import_exercises.py               # validate and import
    python import_exercises.py --check       # only validate, don't touch the database
    python import_exercises.py --build-media # also pre-build animations and report missing images

The bot also runs the import automatically on startup.
"""
import argparse
import asyncio
import sys

from config import config
from database.base import create_tables, make_engine, make_session_factory
from services.exercise_import import (
    ExerciseDataError,
    import_exercises,
    load_exercises_file,
    load_injury_rules,
)
from services.exercise_media import build_media, find_images
from utils.logging_setup import setup_logging


async def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawTextHelpFormatter)
    parser.add_argument("--check", action="store_true", help="validate only")
    parser.add_argument("--build-media", action="store_true", help="pre-build exercise media")
    args = parser.parse_args()
    setup_logging(config.log_level)

    try:
        records = load_exercises_file()
        load_injury_rules({r["id"] for r in records})
    except ExerciseDataError as error:
        print(f"❌ {error}")
        return 1
    print(f"✅ {len(records)} exercises are valid; all substitute IDs exist.")

    if args.build_media:
        missing = []
        for record in records:
            if find_images(record["id"]).kind is None:
                missing.append(record["id"])
            else:
                build_media(record["id"])
        print(f"🖼  Media ready for {len(records) - len(missing)} exercises.")
        if missing:
            print(f"⚠️  No images for {len(missing)}: {', '.join(missing)}")

    if args.check:
        return 0

    engine = make_engine(config.database_url)
    await create_tables(engine)
    async with make_session_factory(engine)() as session:
        report = await import_exercises(session, records)
    await engine.dispose()

    print(f"✅ Imported: {report.created} new, {report.updated} updated, {report.unchanged} unchanged.")
    if report.deactivated:
        print(f"ℹ️  No longer in the file (hidden, not deleted): {', '.join(report.deactivated)}")
    return 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
