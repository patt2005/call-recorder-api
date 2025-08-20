from flask import Flask, jsonify, request, Response
from flask_restful import Api
from flask_cors import CORS
from flask_migrate import Migrate
from twilio.twiml.voice_response import VoiceResponse
from twilio.rest import Client
import uuid
import os
import threading
from datetime import datetime
from database import db
from models.call import Call
from models.user import User
from summary_service import SummaryService
from push_notification_service import push_notification_service

HOST = "https://call-recorder-api-164860087792.us-central1.run.app"
CONNECTION_STRING = "postgresql://postgres:IHaqrKkfZMUkHIfsgotyNPJorsJzgMKP@shortline.proxy.rlwy.net:39111/railway"

# Twilio credentials
TWILIO_ACCOUNT_SID = os.environ.get('TWILIO_ACCOUNT_SID')
TWILIO_AUTH_TOKEN = os.environ.get('TWILIO_AUTH_TOKEN')
twilio_client = Client(TWILIO_ACCOUNT_SID, TWILIO_AUTH_TOKEN)

app = Flask(__name__)
app.config['SQLALCHEMY_DATABASE_URI'] = CONNECTION_STRING

CORS(app, origins=[HOST])

db.init_app(app)
migrate = Migrate(app, db)
api = Api(app)

def process_summary_and_title_background(call_uuid, transcribe_text):
    """Background function to generate summary and title for a call."""
    with app.app_context():
        try:
            print(f"Starting background processing for call UUID: {call_uuid}")
            
            call = db.session.query(Call).filter_by(id=call_uuid).first()
            if not call:
                print(f"Call not found for UUID: {call_uuid}")
                return
            
            summary_service = SummaryService()
            
            call.summary = summary_service.get_summary(transcribe_text)
            print(f"Summary generated for call UUID: {call_uuid}")
            
            call.title = summary_service.get_title(transcribe_text)
            print(f"Title generated for call UUID: {call_uuid}")
            
            db.session.commit()
            print(f"Background processing completed for call UUID: {call_uuid}")
            
        except Exception as e:
            print(f"Error in background processing for call UUID {call_uuid}: {str(e)}")
            try:
                call = db.session.query(Call).filter_by(id=call_uuid).first()
                if call:
                    call.summary = "Summary generation failed. Please review the transcription."
                    call.title = "Call Recording"
                    db.session.commit()
            except Exception as inner_e:
                print(f"Failed to update call with error fallback: {str(inner_e)}")

def get_formated_body():
    if request.is_json:
        body = request.get_json()
        print(f"JSON body: {body}")
    elif request.form:
        body = request.form.to_dict()
        print(f"Form body: {body}")
    else:
        raw_data = request.get_data(as_text=True)
        print(f"Raw data: {raw_data}")
        from urllib.parse import parse_qs
        body = parse_qs(raw_data)
        body = {k: v[0] if len(v) == 1 else v for k, v in body.items()}
        print(f"Parsed body: {body}")
    return body

@app.route('/get_calls_for_user', methods=['POST'])
def get_calls_for_user():
    body = get_formated_body()
    user_phone = body.get('user_phone')
    user_id = body.get('user_id')

    if not user_phone and not user_id:
        return jsonify({'error': 'Either user_phone or user_id parameter is required'}), 400

    if user_id:
        user = db.session.query(User).filter_by(id=user_id).first()
        if not user:
            return jsonify({'error': 'User not found'}), 404
        user_phone = user.phone_number
    
    calls = db.session.query(Call).filter_by(from_phone=user_phone).all()
    calls_list = []
    for call in calls:
        calls_list.append({
            'id': call.id,
            'from_phone': call.from_phone,
            'call_date': call.call_date.isoformat() if call.call_date else None,
            'title': call.title,
            'summary': call.summary,
            'recording_url': call.recording_url,
            'recording_duration': call.recording_duration,
            'recording_status': call.recording_status,
            'transcription_text': call.transcription_text,
            'transcription_status': call.transcription_status
        })

    return jsonify(calls_list), 200

@app.route('/delete_recording', methods=['POST'])
def delete_recording():
    try:
        body = get_formated_body()
        
        recording_id = body.get('recording_id')
        user_id = body.get('user_id')
        
        if not recording_id:
            return jsonify({'error': 'recording_id is required'}), 400
        
        if not user_id:
            return jsonify({'error': 'user_id is required'}), 400

        user = db.session.query(User).filter_by(id=user_id).first()
        if not user:
            return jsonify({'error': 'User not found'}), 404
        
        call = db.session.query(Call).filter_by(id=recording_id).first()
        if not call:
            return jsonify({'error': 'Recording not found'}), 404
        
        if call.from_phone != user.phone_number:
            return jsonify({'error': 'Unauthorized: You do not own this recording'}), 403
        
        db.session.delete(call)
        db.session.commit()
        
        return jsonify({
            'message': 'Recording deleted successfully',
            'recording_id': recording_id
        }), 200
        
    except Exception as e:
        db.session.rollback()
        return jsonify({'error': str(e)}), 500

@app.route('/api/users/register', methods=['POST'])
def register_user():
    try:
        body = get_formated_body()
        
        phone_number = body.get('phoneNumber')
        country_code = body.get('countryCode')
        fcm_token = body.get('fcmToken')
        
        if not phone_number:
            return jsonify({'error': 'phoneNumber is required'}), 400
        
        if not fcm_token:
            return jsonify({'error': 'fcmToken is required'}), 400
        
        existing_user = db.session.query(User).filter_by(phone_number=phone_number).first()
        
        if existing_user:
            existing_user.fcm_token = fcm_token
            if country_code:
                existing_user.country_code = country_code
            existing_user.updated_at = datetime.now()
            db.session.commit()
            
            return jsonify({
                'userId': str(existing_user.id),
                'message': 'User updated successfully'
            }), 200
        else:
            new_user = User(
                phone_number=phone_number,
                fcm_token=fcm_token
            )
            if country_code:
                new_user.country_code = country_code
            db.session.add(new_user)
            db.session.commit()
            
            return jsonify({
                'userId': str(new_user.id),
                'message': 'User registered successfully'
            }), 201
            
    except Exception as e:
        db.session.rollback()
        return jsonify({'error': str(e)}), 500

@app.route('/api/users/<user_id>', methods=['GET'])
def get_user(user_id):
    try:
        user = db.session.query(User).filter_by(id=user_id).first()
        
        if not user:
            return jsonify({'error': 'User not found'}), 404
        
        return jsonify({
            'phoneNumber': user.phone_number,
            'countryCode': user.country_code if user.country_code else '',
            'notificationsEnabled': user.push_notifications_enabled
        }), 200
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/users/update-phone', methods=['PUT'])
def update_user_phone():
    try:
        body = get_formated_body()
        
        user_id = body.get('userId')
        phone_number = body.get('phoneNumber')
        country_code = body.get('countryCode')
        
        if not user_id:
            return jsonify({'error': 'userId is required'}), 400
        
        if not phone_number:
            return jsonify({'error': 'phoneNumber is required'}), 400
            
        if not country_code:
            return jsonify({'error': 'countryCode is required'}), 400
        
        user = db.session.query(User).filter_by(id=user_id).first()
        
        if not user:
            return jsonify({'error': 'User not found'}), 404
        
        existing_phone = db.session.query(User).filter_by(phone_number=phone_number).first()
        if existing_phone and str(existing_phone.id) != user_id:
            return jsonify({'error': 'Phone number already in use'}), 409
        
        user.phone_number = phone_number
        user.country_code = country_code
        user.updated_at = datetime.utcnow()
        db.session.commit()
        
        return jsonify({
            'message': 'Phone number updated successfully',
            'userId': str(user.id)
        }), 200
        
    except Exception as e:
        db.session.rollback()
        return jsonify({'error': str(e)}), 500

@app.route('/api/users/notifications', methods=['PUT'])
def update_notification_settings():
    try:
        body = get_formated_body()
        
        user_id = body.get('userId')
        push_notifications_enabled = body.get('pushNotificationsEnabled')
        
        if not user_id:
            return jsonify({'error': 'userId is required'}), 400
        
        if push_notifications_enabled is None:
            return jsonify({'error': 'pushNotificationsEnabled is required'}), 400
        
        user = db.session.query(User).filter_by(id=user_id).first()
        
        if not user:
            return jsonify({'error': 'User not found'}), 404
        
        user.push_notifications_enabled = push_notifications_enabled
        user.updated_at = datetime.utcnow()
        db.session.commit()
        
        return jsonify({
            'userId': str(user.id),
            'pushNotificationsEnabled': user.push_notifications_enabled,
            'message': 'Notification settings updated successfully'
        }), 200
        
    except Exception as e:
        db.session.rollback()
        return jsonify({'error': str(e)}), 500

@app.route('/api/service/phone', methods=['GET'])
def get_service_phone_number():
    """Get the service phone number for the application."""
    SERVICE_PHONE_NUMBER = "+19865294217"
    
    return jsonify({
        'phoneNumber': SERVICE_PHONE_NUMBER
    }), 200

@app.route('/test/twilio-env', methods=['GET'])
def test_twilio_env():
    """Test endpoint to check if Twilio environment variables are set."""
    account_sid = os.environ.get('TWILIO_ACCOUNT_SID')
    auth_token = os.environ.get('TWILIO_AUTH_TOKEN')
    
    return jsonify({
        'TWILIO_ACCOUNT_SID': 'SET' if account_sid else 'NOT SET',
        'TWILIO_AUTH_TOKEN': 'SET' if auth_token else 'NOT SET',
        'account_sid_prefix': account_sid[:10] + '...' if account_sid else None,
        'auth_token_prefix': auth_token[:6] + '...' if auth_token else None,
        'twilio_client_initialized': twilio_client is not None
    }), 200

@app.route('/delete_all_recordings', methods=['POST'])
def delete_all_recordings():
    try:
        body = get_formated_body()
        
        user_id = body.get('user_id')
        
        if not user_id:
            return jsonify({'error': 'user_id is required'}), 400
        
        user = db.session.query(User).filter_by(id=user_id).first()
        if not user:
            return jsonify({'error': 'User not found'}), 404
        
        deleted_count = db.session.query(Call).filter_by(from_phone=user.phone_number).delete()
        db.session.commit()
        
        return jsonify({
            'message': f'Successfully deleted {deleted_count} recordings',
            'deleted_count': deleted_count
        }), 200
        
    except Exception as e:
        db.session.rollback()
        return jsonify({'error': str(e)}), 500

@app.route('/transcribe-complete', methods=['POST'])
def transcribe_complete():
    call_uuid = request.args.get('call-uuid')
    try:
        if not call_uuid:
            return jsonify({'error': 'call-uuid parameter is required'}), 400

        body = get_formated_body()

        transcribe_text = body.get("TranscriptionText")
        transcribe_status = body.get("TranscriptionStatus")

        call = db.session.query(Call).filter_by(id=call_uuid).first()

        if not call:
            return jsonify({'error': 'Call not found'}), 404

        call.transcription_text = transcribe_text
        call.transcription_status = transcribe_status

        db.session.commit()

        if transcribe_status == "completed" and transcribe_text:
            background_thread = threading.Thread(
                target=process_summary_and_title_background,
                args=(call_uuid, transcribe_text)
            )
            background_thread.daemon = True
            background_thread.start()
            print(f"Started background processing for call UUID: {call_uuid}")

        user = db.session.query(User).filter_by(phone_number=call.from_phone).first()
        if user and user.push_notifications_enabled and user.fcm_token:
            call_data = {
                'id': call.id,
                'callDate': call.call_date.isoformat() if call.call_date else '',
                'fromPhone': call.from_phone or '',
                'toPhone': '',
                'recordingDuration': call.recording_duration or 0,
                'recordingStatus': call.recording_status or '',
                'recordingUrl': call.recording_url or '',
                'summary': call.summary or '',
                'title': call.title or '',
                'transcriptionStatus': call.transcription_status or 'pending',
                'transcriptionText': call.transcription_text or ''
            }

            success = push_notification_service.send_recording_complete_notification(
                user.fcm_token,
                call_data
            )

            if success:
                print(f"Recording complete notification sent to user {user.id} for call {call.id}")
            else:
                print(f"Failed to send recording complete notification to user {user.id}")

        return jsonify("Transcribe was successfully saved."), 200
    except Exception as e:
        print(f"Error generating summary/title for call UUID {call_uuid}: {str(e)}")
        return jsonify({'error': str(e)}), 500

@app.route('/record-complete', methods=['POST'])
def record_complete():
    print(f"=== RECORD-COMPLETE ENDPOINT ===")
    print(f"Request body: {request.get_data(as_text=True)}")
    print(f"Request form: {request.form.to_dict()}")
    print(f"Request JSON: {request.get_json() if request.is_json else 'Not JSON'}")
    print(f"Request args: {request.args.to_dict()}")
    print(f"Request headers: {dict(request.headers)}")
    print(f"=== END REQUEST INFO ===")
    
    call_uuid = request.args.get('call-uuid')
    
    if not call_uuid:
        return jsonify({'error': 'call-uuid parameter is required'}), 400

    body = get_formated_body()
    
    # Check if this is already processed to avoid duplicates
    recording_status = body.get('RecordingStatus')
    if recording_status != 'completed':
        print(f"Ignoring recording status: {recording_status}")
        return jsonify("Recording status not completed, ignoring."), 200
    
    recording_url = body.get('RecordingUrl')
    recording_sid = body.get('RecordingSid')
    recording_length = body.get('RecordingDuration')
    
    call = db.session.query(Call).filter_by(id=call_uuid).first()
    
    if not call:
        return jsonify({'error': 'Call not found'}), 404
    
    # Check if recording is already processed to avoid duplicates
    if call.recording_status == 'completed' and call.recording_url:
        print(f"Recording already processed for call UUID: {call_uuid}")
        return jsonify("Recording already processed."), 200

    # Handle recording URL - convert to MP3 format for better compatibility
    if recording_url:
        # Ensure we have the full URL
        if recording_url.startswith('/'):
            recording_url = f"https://api.twilio.com{recording_url}"
        
        # Convert to MP3 format (Twilio returns WAV by default, MP3 with .mp3 suffix)
        if not recording_url.endswith('.mp3'):
            recording_url = f"{recording_url}.mp3"
        
        print(f"Recording URL (MP3 format): {recording_url}")
    else:
        print("Warning: No RecordingUrl provided in webhook")
        
    # Optional: Try to get media_url from Twilio API if needed (requires auth)
    if recording_sid and TWILIO_ACCOUNT_SID and TWILIO_AUTH_TOKEN and not recording_url:
        try:
            print(f"Attempting to fetch recording with SID: {recording_sid}")
            recording = twilio_client.recordings(recording_sid).fetch()
            recording_url = f"https://api.twilio.com{recording.media_url}.mp3"
            print(f"Retrieved recording URL from API: {recording_url}")
        except Exception as e:
            print(f"Error fetching recording from Twilio API: {str(e)}")
    
    call.recording_url = recording_url
    call.recording_duration = int(recording_length) if recording_length else None
    call.recording_status = 'completed'

    db.session.commit()

    return jsonify("Recording successfully completed."), 200

@app.route("/answer", methods=["GET", "POST"])
def answer():
    """Handle incoming call and connect to a conference with beep and recording."""
    call_uuid = str(uuid.uuid4())

    body = get_formated_body()
    user_phone = body.get('From')

    call = Call(call_uuid, user_phone, datetime.now())
    db.session.add(call)
    db.session.commit()

    response = VoiceResponse()

    response.say("You are being connected. This call will be recorded.")

    response.pause(length=15)

    response.say("The recording has started.")

    response.record(
        play_beep=True,
        max_length = 5400,
        transcribe = True,
        transcribe_callback = f"{HOST}/transcribe-complete?call-uuid={call_uuid}",
        recording_status_callback = f"{HOST}/record-complete?call-uuid={call_uuid}",
        recording_status_callback_event = "completed"
    )

    return Response(str(response), mimetype='text/xml')

if __name__ == "__main__":
    with app.app_context():
        db.create_all()
    port = int(os.environ.get('PORT', 8080))
    app.run(host='0.0.0.0', port=port, debug=False)