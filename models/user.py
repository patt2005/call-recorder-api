from sqlalchemy import Column, String, DateTime, Boolean
from sqlalchemy.dialects.postgresql import UUID
from database import db
import uuid
from datetime import datetime


class User(db.Model):
    __tablename__ = 'call_users'
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    phone_number = Column(String, unique=True, nullable=False)
    country_code = Column(String, nullable=True)
    fcm_token = Column(String, nullable=False)
    push_notifications_enabled = Column(Boolean, nullable=False, default=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    def to_dict(self):
        return {
            'userId': str(self.id),
            'phoneNumber': self.phone_number,
            'countryCode': self.country_code,
            'fcmToken': self.fcm_token,
            'pushNotificationsEnabled': self.push_notifications_enabled,
            'createdAt': self.created_at.isoformat() if self.created_at else None,
            'updatedAt': self.updated_at.isoformat() if self.updated_at else None
        }