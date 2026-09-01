from sqlalchemy import Column, String, DateTime, Text
from sqlalchemy.dialects.postgresql import UUID
from database.database import db
import uuid
from datetime import datetime


class TelnyxErrorLog(db.Model):
    __tablename__ = 'telnyx_error_logs'

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(String, nullable=True)
    error_type = Column(String, nullable=False)
    message = Column(Text, nullable=True)
    platform = Column(String, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
