"""CLI script to reset the database when confirmed."""

import argparse
import sys

from app.database.connection import reset_database


def main():
    parser = argparse.ArgumentParser(description="Reset POWER-SUB SQLite Database.")
    parser.add_argument(
        "--confirm",
        action="store_true",
        help="Explicit confirmation flag required to reset the database.",
    )
    args = parser.parse_args()

    if not args.confirm:
        print(
            "ERROR: Database reset aborted. You must supply --confirm flag.",
            file=sys.stderr,
        )
        sys.exit(1)

    reset_database(confirmed=True)
    print("SUCCESS: Database has been reset and schema initialized.")


if __name__ == "__main__":
    main()
