import os
import sys
sys.stdout.reconfigure(encoding='utf-8')
from sqlalchemy import inspect
from app import create_app
from app.models import db

app = create_app()

with app.app_context():
    inspector = inspect(db.engine)
    tables = inspector.get_table_names()

    print("=======================================================")
    print(f"DATABASE ENGINE: {db.engine.name}")
    print(f"URL: {db.engine.url}")
    print(f"TOTAL TABLES DETECTED: {len(tables)}")
    print("=======================================================\n")

    for table_name in tables:
        print(f"TABLE: {table_name}")
        
        # Primary Key
        pk = inspector.get_pk_constraint(table_name)
        print(f"  Primary Key: {pk.get('constrained_columns', [])}")

        # Columns
        columns = inspector.get_columns(table_name)
        print(f"  Columns ({len(columns)}):")
        for col in columns:
            nullable_str = "NULL" if col.get('nullable') else "NOT NULL"
            print(f"    - {col['name']} ({col['type']}) {nullable_str}")

        # Foreign Keys
        fks = inspector.get_foreign_keys(table_name)
        print(f"  Foreign Keys ({len(fks)}):")
        for fk in fks:
            print(f"    - {fk.get('constrained_columns')} -> {fk.get('referred_table')}.{fk.get('referred_columns')}")

        # Unique Constraints
        uqs = inspector.get_unique_constraints(table_name)
        print(f"  Unique Constraints ({len(uqs)}):")
        for uq in uqs:
            print(f"    - {uq.get('name')}: {uq.get('column_names')}")

        # Indexes
        indexes = inspector.get_indexes(table_name)
        print(f"  Indexes ({len(indexes)}):")
        for idx in indexes:
            print(f"    - {idx.get('name')}: columns={idx.get('column_names')}, unique={idx.get('unique')}")

        print("-" * 55)
