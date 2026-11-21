import sys
import os
from pathlib import Path

# Add backend directory to path
backend_path = Path(__file__).resolve().parent.parent / "backend"
sys.path.insert(0, str(backend_path))

from app.db.session import engine, init_db, Base
from app.core.config import settings

def reset_db():
    print(f"Resetting database at {settings.DATABASE_URL}...")
    
    # Drop all existing tables
    Base.metadata.drop_all(bind=engine)
    print("Dropped all existing tables.")
    
    # Initialize all tables afresh
    init_db(engine)
    print("Initialized all tables cleanly.")

if __name__ == "__main__":
    reset_db()
