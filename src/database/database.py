"""
Database Module

This module manages database connections and provides utility functions for
common database operations. It uses SQLAlchemy for ORM functionality and
supports operations on bookings, ad descriptions, and other rental-related data.

The module includes functions for querying, creating, and updating database
records related to apartment rentals and bookings.
"""

import datetime
import os

from dotenv import load_dotenv
from sqlalchemy import create_engine, func
from sqlalchemy.orm import joinedload, sessionmaker

from src.database.models import AdDescriptionsModel, BookingsModel

# Determine the correct path to the .env file for database.py
dotenv_path = os.path.join(os.path.dirname(__file__), "..", ".env")
if not os.path.exists(dotenv_path):
    dotenv_path = ".env"  # Fallback to CWD

load_dotenv(dotenv_path=dotenv_path)

DATABASE_URL = os.getenv("DATABASE_URL")

if not DATABASE_URL:
    error_message = (
        "Critical: DATABASE_URL is not set in the .env file. "
        "Please define it in your .env file. "
        'Example for PostgreSQL: DATABASE_URL="postgresql://user:password@host:port/dbname"'
    )
    print(error_message)  # Print to console
    raise ValueError(error_message)  # Raise an error to halt execution if not set


engine = create_engine(DATABASE_URL)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


def get_db():
    """
    Provides a database session for dependency injection.

    Yields:
        Session: SQLAlchemy database session

    Note:
        This is a generator function that ensures the session is properly
        closed after use, even if an exception occurs.
    """
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def init_db():
    """
    Initializes the database by creating all tables defined in models.

    This function imports all model definitions and creates the corresponding
    database tables if they don't already exist. It's idempotent - running it
    multiple times won't cause issues.

    Raises:
        Exception: If there's an error creating database tables
    """
    # Import all modules here that define models before calling Base.metadata.create_all(engine)
    # This ensures that Base has all model definitions registered.
    # For now, we know models are in src.models
    try:
        from src.database.models import Base

        Base.metadata.create_all(bind=engine)
        print(f"Database tables created successfully for {DATABASE_URL}")
    except Exception as e:
        print(f"Error creating database tables: {e}")
        print("Please ensure all SQLAlchemy models are correctly defined and imported.")


if __name__ == "__main__":
    print(f"Attempting to initialize database at: {DATABASE_URL}")
    # The following line should be run consciously by the user,
    # e.g. via a separate script or a CLI command.
    # init_db()
    # print("If no errors, database schema should be initialized (if not already).")
    # print("To actually create tables, uncomment 'init_db()' call or run it separately.")

    # For quick check, try to connect
    try:
        with engine.connect() as connection:
            print("Successfully connected to the database.")
    except Exception as e:
        print(f"Failed to connect to the database: {e}")


def get_ad_description_by_avito_ad_id(db, avito_ad_id: int) -> AdDescriptionsModel | None:
    """
    Retrieves an ad description by its Avito ad ID.

    Args:
        db: SQLAlchemy database session
        avito_ad_id: The Avito ad ID to search for

    Returns:
        AdDescriptionsModel instance if found, None otherwise
    """
    return (
        db.query(AdDescriptionsModel).filter(AdDescriptionsModel.ad_id_avito == avito_ad_id).first()
    )


def save_booking(db, booking_data: dict) -> BookingsModel | None:
    """
    Saves a new booking to the database from Avito booking data.

    Args:
        db: SQLAlchemy database session
        booking_data: Dictionary containing booking information matching Avito's
                     RealtyBooking schema. Must include 'item_id' field.

    Returns:
        BookingsModel instance if successful, None if there's an error

    Note:
        The function expects the associated ad description to already exist
        in the database. If not found, the booking won't be saved.
    """
    avito_ad_id = booking_data.get("item_id")  # Assuming item_id in booking_data is the ad_id_avito
    if not avito_ad_id:
        # Or handle as an error, depending on requirements
        print("Error: avito_ad_id (item_id) missing in booking_data")
        return None

    ad_description = get_ad_description_by_avito_ad_id(db, avito_ad_id)
    if not ad_description:
        print(f"Error: AdDescription not found for avito_ad_id {avito_ad_id}")
        return None  # Or create one if that's the desired behavior

    contact_info = booking_data.get("contact", {})
    safe_deposit_info = booking_data.get("safe_deposit", {})

    new_booking = BookingsModel(
        avito_booking_id=str(booking_data.get("avito_booking_id")),  # Ensure it's a string
        ad_id=ad_description.id,
        base_price=booking_data.get("base_price"),
        check_in_date=(
            datetime.date.fromisoformat(booking_data["check_in"])
            if booking_data.get("check_in")
            else None
        ),
        check_out_date=(
            datetime.date.fromisoformat(booking_data["check_out"])
            if booking_data.get("check_out")
            else None
        ),
        contact_email=contact_info.get("email"),
        contact_name=contact_info.get("name"),  # Maps to guest_name
        contact_phone=contact_info.get("phone"),
        guest_count=booking_data.get("guest_count"),
        nights=booking_data.get("nights"),
        safe_deposit_owner_amount=safe_deposit_info.get("owner_amount"),
        safe_deposit_tax=safe_deposit_info.get("tax"),
        safe_deposit_total_amount=safe_deposit_info.get("total_amount"),
        status=booking_data.get("status"),
        raw_booking_details_json=booking_data,  # Store the whole thing
        # check_in_time_intention and source will use defaults or can be added if present in booking_data
    )

    try:
        db.add(new_booking)
        db.commit()
        db.refresh(new_booking)
        return new_booking
    except Exception as e:
        db.rollback()
        print(f"Error saving booking: {e}")
        return None


def get_booking_by_avito_id(db, avito_booking_id: str) -> BookingsModel | None:
    """
    Retrieves a booking by its Avito booking ID.

    Args:
        db: SQLAlchemy database session
        avito_booking_id: The Avito booking ID to search for

    Returns:
        BookingsModel instance if found, None otherwise
    """
    return (
        db.query(BookingsModel).filter(BookingsModel.avito_booking_id == avito_booking_id).first()
    )


def get_bookings_for_ad(
    db, ad_id_internal: int, date_start: datetime.date, date_end: datetime.date
) -> list[BookingsModel]:
    """
    Retrieves all bookings for an ad that overlap with a date range.

    Args:
        db: SQLAlchemy database session
        ad_id_internal: Internal database ID of the ad (AdDescriptionsModel.id)
        date_start: Start date of the range to check
        date_end: End date of the range to check

    Returns:
        List of BookingsModel instances that overlap with the date range

    Note:
        Overlap condition: check_in_date < date_end AND check_out_date > date_start
    """
    return (
        db.query(BookingsModel)
        .filter(
            BookingsModel.ad_id == ad_id_internal,
            BookingsModel.check_in_date < date_end,
            BookingsModel.check_out_date > date_start,
        )
        .all()
    )


def get_upcoming_check_ins(
    db, from_date: datetime.date, to_date: datetime.date, status_filter: list[str] | None = None
) -> list[BookingsModel]:
    """
    Retrieves bookings with check-in dates in a specified date range.

    Args:
        db: SQLAlchemy database session
        from_date: Start date of the range (inclusive)
        to_date: End date of the range (inclusive)
        status_filter: Optional list of booking statuses to filter by
                      (e.g., ["active", "pending"])

    Returns:
        List of BookingsModel instances with ad_description eagerly loaded
    """
    query = (
        db.query(BookingsModel)
        .options(joinedload(BookingsModel.ad_description))
        .filter(BookingsModel.check_in_date >= from_date, BookingsModel.check_in_date <= to_date)
    )
    if status_filter:
        query = query.filter(BookingsModel.status.in_(status_filter))
    return query.all()


def update_booking_status(db, avito_booking_id: str, new_status: str) -> BookingsModel | None:
    """
    Updates the status of a booking.

    Args:
        db: SQLAlchemy database session
        avito_booking_id: The Avito booking ID to update
        new_status: The new status value to set

    Returns:
        Updated BookingsModel instance if successful, None if booking not found
        or if an error occurs
    """
    booking = get_booking_by_avito_id(db, avito_booking_id)
    if booking:
        try:
            booking.status = new_status
            booking.updated_at = func.now()  # Ensure updated_at is set by SQLAlchemy
            db.commit()
            db.refresh(booking)
            return booking
        except Exception as e:
            db.rollback()
            print(f"Error updating booking status for {avito_booking_id}: {e}")
            return None
    return None


def get_all_ad_descriptions(db) -> list[AdDescriptionsModel]:
    """
    Retrieves all ad descriptions from the database.

    Args:
        db: SQLAlchemy database session

    Returns:
        List of all AdDescriptionsModel instances
    """
    return db.query(AdDescriptionsModel).all()
