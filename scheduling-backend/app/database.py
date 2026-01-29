import os
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from sqlalchemy.orm import declarative_base

DATABASE_URL = os.getenv("DATABASE_URL", "sqlite+aiosqlite:///./scheduling.db")

if os.path.exists("/data"):
    DATABASE_URL = "sqlite+aiosqlite:////data/app.db"

engine = create_async_engine(DATABASE_URL, echo=False)
async_session_maker = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

Base = declarative_base()


async def get_db():
    async with async_session_maker() as session:
        try:
            yield session
        finally:
            await session.close()


async def init_db():
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
        
        # Run migrations to add new columns if they don't exist
        await run_migrations(conn)


async def run_migrations(conn):
    """Add missing columns to existing tables"""
    from sqlalchemy import text
    
    # List of migrations: (table_name, column_name, column_definition)
    migrations = [
        ("email_templates", "logo_url", "VARCHAR(1000)"),
        ("bookings", "engineer_attachment_url", "VARCHAR(1000)"),
        ("bookings", "customer_attachment_url", "VARCHAR(1000)"),
        ("bookings", "additional_emails", "JSON"),
        ("bookings", "notes", "TEXT"),
        ("bookings", "cancellation_fee", "FLOAT DEFAULT 0.0"),
        ("bookings", "expedite_fee", "FLOAT DEFAULT 0.0"),
        ("products", "expedite_fee", "FLOAT DEFAULT 0.0"),
        ("products", "expedite_contact_emails", "JSON"),
        ("calendar_event_templates", "is_teams_meeting", "BOOLEAN DEFAULT 0"),
        ("fees", "apply_mode", "VARCHAR(50) DEFAULT 'auto'"),
        ("fees", "apply_on_weekends", "BOOLEAN DEFAULT 0"),
        ("fees", "apply_on_bank_holidays", "BOOLEAN DEFAULT 0"),
        ("fees", "apply_outside_hours", "BOOLEAN DEFAULT 0"),
        ("fees", "outside_hours_start", "VARCHAR(5)"),
        ("fees", "outside_hours_end", "VARCHAR(5)"),
        ("change_types", "minimum_notice_hours", "INTEGER DEFAULT 0"),
        ("change_types", "cancellation_notice_hours", "INTEGER"),
        ("change_types", "amendment_notice_hours", "INTEGER"),
        ("users", "last_login_at", "DATETIME"),
        ("bookings", "engineer_notes", "TEXT"),
        ("bookings", "issue_description", "TEXT"),
        ("bookings", "issue_reported_at", "DATETIME"),
        ("bookings", "issue_resolved", "BOOLEAN DEFAULT 0"),
    ]
    
    for table_name, column_name, column_def in migrations:
        try:
            # Check if column exists by trying to select it
            await conn.execute(text(f"SELECT {column_name} FROM {table_name} LIMIT 1"))
        except Exception:
            # Column doesn't exist, add it
            try:
                await conn.execute(text(f"ALTER TABLE {table_name} ADD COLUMN {column_name} {column_def}"))
                print(f"Added column {column_name} to {table_name}")
            except Exception as e:
                print(f"Could not add column {column_name} to {table_name}: {e}")
    
    # Backfill issues from BookingStatusUpdate to Booking table
    await backfill_issues(conn)


async def backfill_issues(conn):
    """Backfill issue data from BookingStatusUpdate to Booking table"""
    from sqlalchemy import text
    
    try:
        # First, count how many issues exist in BookingStatusUpdate
        count_result = await conn.execute(text("""
            SELECT COUNT(DISTINCT booking_id) as count 
            FROM booking_status_updates 
            WHERE issue_reported = 1 
            AND issue_description IS NOT NULL
        """))
        row = count_result.fetchone()
        total_issues = row[0] if row else 0
        print(f"Found {total_issues} bookings with issues in BookingStatusUpdate table")
        
        # Update ALL bookings that have issues in BookingStatusUpdate (not just those with NULL issue_description)
        # This ensures we capture all issues even if the booking was updated after the initial backfill
        result = await conn.execute(text("""
            UPDATE bookings 
            SET issue_description = (
                SELECT bsu.issue_description 
                FROM booking_status_updates bsu 
                WHERE bsu.booking_id = bookings.id 
                AND bsu.issue_reported = 1 
                AND bsu.issue_description IS NOT NULL
                ORDER BY bsu.created_at DESC 
                LIMIT 1
            ),
            issue_reported_at = (
                SELECT bsu.created_at 
                FROM booking_status_updates bsu 
                WHERE bsu.booking_id = bookings.id 
                AND bsu.issue_reported = 1 
                AND bsu.issue_description IS NOT NULL
                ORDER BY bsu.created_at DESC 
                LIMIT 1
            ),
            issue_resolved = COALESCE(issue_resolved, 0)
            WHERE EXISTS (
                SELECT 1 FROM booking_status_updates bsu 
                WHERE bsu.booking_id = bookings.id 
                AND bsu.issue_reported = 1 
                AND bsu.issue_description IS NOT NULL
            )
        """))
        print(f"Backfilled issues from BookingStatusUpdate to Booking table")
        
        # Count how many bookings now have issues
        count_result2 = await conn.execute(text("""
            SELECT COUNT(*) as count 
            FROM bookings 
            WHERE issue_description IS NOT NULL
        """))
        row2 = count_result2.fetchone()
        bookings_with_issues = row2[0] if row2 else 0
        print(f"Now {bookings_with_issues} bookings have issue_description populated")
    except Exception as e:
        print(f"Could not backfill issues: {e}")
