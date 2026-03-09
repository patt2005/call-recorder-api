from database.database import db
from datetime import datetime


class CallTranscript(db.Model):
    """Transcript for a call: full text and phrase-level segments from Whisper."""
    __tablename__ = 'call_transcripts'

    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    call_id = db.Column(db.String(100), db.ForeignKey('calls.id', ondelete='CASCADE'), nullable=False, unique=True)

    text = db.Column(db.Text, nullable=True)
    segments = db.Column(db.Text, nullable=True)  # JSON array of {start, end, text}
    status = db.Column(db.String(20), nullable=False, default='pending')  # pending, processing, completed, failed

    language = db.Column(db.String(20), nullable=True)
    duration_seconds = db.Column(db.Float, nullable=True)

    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Optional: backref on Call so we can do call.transcript
    call = db.relationship('Call', backref=db.backref('transcript', uselist=False, cascade='all, delete-orphan'))

    def __init__(self, call_id, text=None, segments=None, status='pending', language=None, duration_seconds=None,
                 created_at=None, updated_at=None):
        self.call_id = call_id
        self.text = text
        self.segments = segments
        self.status = status
        self.language = language
        self.duration_seconds = duration_seconds
        if created_at is not None:
            self.created_at = created_at
        if updated_at is not None:
            self.updated_at = updated_at
