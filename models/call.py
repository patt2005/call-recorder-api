from database import db

class Call(db.Model):
    __tablename__ = 'calls'
    id = db.Column(db.String(100), primary_key=True)
    from_phone = db.Column(db.String(100))
    call_date = db.Column(db.DateTime, nullable=False)
    title = db.Column(db.String(200), nullable=True)
    summary = db.Column(db.Text, nullable=True)
    
    recording_url = db.Column(db.String(500), nullable=True)
    recording_duration = db.Column(db.Integer, nullable=True)
    recording_status = db.Column(db.String(20), nullable=True)
    
    transcription_text = db.Column(db.Text, nullable=True)
    transcription_status = db.Column(db.String(20), nullable=True)
    
    def __init__(self, id, from_phone, call_date, title=None, summary=None,
                 recording_url=None, recording_duration=None, recording_status=None, 
                 transcription_text=None, transcription_status=None):
        self.id = id
        self.from_phone = from_phone
        self.call_date = call_date
        self.title = title
        self.summary = summary
        self.recording_url = recording_url
        self.recording_duration = recording_duration
        self.recording_status = recording_status
        self.transcription_text = transcription_text
        self.transcription_status = transcription_status
