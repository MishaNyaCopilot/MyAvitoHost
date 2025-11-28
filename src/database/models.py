"""
Database Models Module

This module defines SQLAlchemy ORM models for the Avito Rental Assistant database.
It includes models for storing Avito tokens, ad descriptions, bookings, chat cache,
and system configuration.

All models inherit from the SQLAlchemy Base class and include timestamps for
tracking creation and modification times.
"""

from sqlalchemy import (
    JSON,
    BigInteger,
    Column,
    Date,
    DateTime,
    ForeignKey,
    Integer,
    Numeric,
    String,
    Text,
    Time,
    func,
)
from sqlalchemy.orm import declarative_base, relationship

from src.constants import BOOKING_SOURCE_AVITO

Base = declarative_base()


class AvitoTokensModel(Base):
    """
    Model for storing Avito API authentication tokens.

    Stores access and refresh tokens with expiration timestamps for
    managing API authentication sessions.
    """

    __tablename__ = "avito_tokens"

    id = Column(Integer, primary_key=True, autoincrement=True)
    access_token = Column(String(1024), nullable=False)
    refresh_token = Column(String(1024), nullable=True)
    expiration_timestamp = Column(DateTime(timezone=True), nullable=False)
    created_at = Column(DateTime(timezone=True), default=func.now())
    updated_at = Column(DateTime(timezone=True), default=func.now(), onupdate=func.now())

    def __repr__(self):
        return f"<AvitoTokensModel(id={self.id})>"


class AdDescriptionsModel(Base):
    """
    Model for storing apartment rental ad descriptions from Avito.

    Stores basic information about rental ads including title, address,
    price, and metadata. Related to bookings and chat caches.
    """

    __tablename__ = "ad_descriptions"

    id = Column(Integer, primary_key=True, autoincrement=True)
    ad_id_avito = Column(BigInteger, unique=True, nullable=False)
    title = Column(String(512), nullable=True)
    address = Column(String(512), nullable=True)
    price = Column(Numeric(10, 2), nullable=True)
    ad_metadata_json = Column(JSON, nullable=True)
    last_fetched_at = Column(DateTime(timezone=True), nullable=True)
    created_at = Column(DateTime(timezone=True), default=func.now())
    updated_at = Column(DateTime(timezone=True), default=func.now(), onupdate=func.now())

    # Relationships
    bookings = relationship("BookingsModel", back_populates="ad_description")
    chat_caches = relationship("ChatCacheModel", back_populates="ad_description")

    def __repr__(self):
        return f"<AdDescriptionsModel(id={self.id}, ad_id_avito={self.ad_id_avito})>"


class SystemConfigModel(Base):
    """
    Model for storing system-wide configuration settings.

    Provides a flexible key-value store for system configuration with
    JSON values and optional descriptions.
    """

    __tablename__ = "system_config"

    id = Column(Integer, primary_key=True, autoincrement=True)
    config_key = Column(String(255), nullable=False, unique=True)
    config_value_json = Column(JSON, nullable=False)
    description = Column(Text, nullable=True)
    created_at = Column(DateTime(timezone=True), default=func.now())
    updated_at = Column(DateTime(timezone=True), default=func.now(), onupdate=func.now())

    def __repr__(self):
        return f"<SystemConfigModel(id={self.id}, config_key='{self.config_key}')>"


class ChatCacheModel(Base):
    """
    Model for caching Avito chat conversations.

    Stores chat history and metadata for conversations between landlords
    and potential guests, including LLM-generated summaries for context.
    """

    __tablename__ = "chat_cache"

    id = Column(Integer, primary_key=True, autoincrement=True)
    chat_id_avito = Column(String(255), nullable=False, unique=True)
    user_id_avito = Column(String(255), nullable=False)
    item_id_avito = Column(BigInteger, ForeignKey("ad_descriptions.ad_id_avito"), nullable=True)
    last_message_id_avito = Column(String(255), nullable=True)
    full_chat_history_json = Column(JSON, nullable=True)
    summary_for_llm = Column(Text, nullable=True)
    last_polled_at = Column(DateTime(timezone=True), nullable=True)
    created_at = Column(DateTime(timezone=True), default=func.now())
    updated_at = Column(DateTime(timezone=True), default=func.now(), onupdate=func.now())

    # Relationship
    ad_description = relationship("AdDescriptionsModel", back_populates="chat_caches")

    def __repr__(self):
        return f"<ChatCacheModel(id={self.id}, chat_id_avito='{self.chat_id_avito}')>"


class BookingsModel(Base):
    """
    Model for storing apartment rental bookings.

    Stores comprehensive booking information including guest details,
    dates, pricing, and status. Related to ad descriptions.

    Attributes:
        avito_booking_id: Unique booking ID from Avito
        ad_id: Foreign key to AdDescriptionsModel
        contact_name: Guest's name
        check_in_date: Booking check-in date
        check_out_date: Booking check-out date
        contact_email: Guest's email address
        contact_phone: Guest's phone number
        check_in_time_intention: Intended check-in time if specified
        base_price: Base rental price
        guest_count: Number of guests
        nights: Number of nights booked
        safe_deposit_*: Safe deposit related amounts
        status: Booking status (active, pending, canceled, etc.)
        source: Source of the booking (avito, manual, etc.)
        raw_booking_details_json: Complete raw booking data from Avito
    """

    __tablename__ = "bookings"

    id = Column(Integer, primary_key=True, autoincrement=True)
    avito_booking_id = Column(String(255), unique=True, nullable=False)
    ad_id = Column(Integer, ForeignKey("ad_descriptions.id"), nullable=False)
    contact_name = Column(String(255), nullable=True)  # Renamed from guest_name
    # guest_contact_info = Column(JSON, nullable=True) # Removed
    check_in_date = Column(Date, nullable=False)
    check_out_date = Column(Date, nullable=False)
    contact_email = Column(String(255), nullable=True)  # New
    contact_phone = Column(String(50), nullable=True)  # New
    check_in_time_intention = Column(Time, nullable=True)
    base_price = Column(Numeric(10, 2), nullable=True)  # Renamed from total_price
    # prepayment_amount = Column(Numeric(10, 2), nullable=True) # Removed
    guest_count = Column(Integer, nullable=True)  # Renamed from number_of_guests
    nights = Column(Integer, nullable=True)  # New
    safe_deposit_owner_amount = Column(Numeric(10, 2), nullable=True)  # New
    safe_deposit_tax = Column(Numeric(10, 2), nullable=True)  # New
    safe_deposit_total_amount = Column(Numeric(10, 2), nullable=True)  # New
    status = Column(String(50), nullable=True)
    source = Column(String(50), default=BOOKING_SOURCE_AVITO)
    raw_booking_details_json = Column(JSON, nullable=True)
    created_at = Column(DateTime(timezone=True), default=func.now())
    updated_at = Column(DateTime(timezone=True), default=func.now(), onupdate=func.now())

    # Relationship
    ad_description = relationship("AdDescriptionsModel", back_populates="bookings")

    def __repr__(self):
        return f"<BookingsModel(id={self.id}, avito_booking_id='{self.avito_booking_id}')>"
