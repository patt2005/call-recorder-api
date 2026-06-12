from flask import Flask, jsonify, request, Response
from flask_restful import Api
from flask_cors import CORS
from flask_migrate import Migrate
import json
import os
import threading
from datetime import datetime
import requests
from sqlalchemy.orm import joinedload
from database.database import db
from models.call import Call
from models.call_transcript import CallTranscript
from models.user import User
from services.push_notification_service import push_notification_service
from services.transcript_service import TranscriptService
from services.file_service import upload_recording, get_recording_url
from services.notification_scheduler import NotificationScheduler
from services.notification_copy_data import pick_random_coherent

HOST = os.environ.get('HOST', 'https://call-recorder-api-production-bc8d.up.railway.app')
CONNECTION_STRING = os.environ.get('DATABASE_URL')

TELNYX_API_KEY = os.environ.get('TELNYX_API_KEY')

app = Flask(__name__)
app.config['SQLALCHEMY_DATABASE_URI'] = CONNECTION_STRING
app.config['SQLALCHEMY_ENGINE_OPTIONS'] = {
    'pool_pre_ping': True,
    'pool_recycle': 300,
}

CORS(app, origins=[HOST])

db.init_app(app)
migrate = Migrate(app, db)
api = Api(app)

def process_transcript_background(call_uuid, download_url=None):
    """Background: transcribe recording with Whisper and save to CallTranscript.

    download_url: direct URL to fetch audio from (e.g. pre-signed S3).
                  Falls back to call.recording_url if not provided.
    """
    with app.app_context():
        try:
            print(f"Starting Whisper transcription for call UUID: {call_uuid}")
            call = db.session.query(Call).filter_by(id=call_uuid).first()
            if not call:
                print(f"Call not found for UUID: {call_uuid}")
                return
            audio_url = download_url or call.recording_url
            if not audio_url:
                print(f"No recording URL for UUID: {call_uuid}")
                return
            transcript = db.session.query(CallTranscript).filter_by(call_id=call_uuid).first()
            if not transcript:
                transcript = CallTranscript(call_id=call_uuid, status='processing')
                db.session.add(transcript)
            else:
                transcript.status = 'processing'
            db.session.commit()

            transcript_service = TranscriptService(api_key=os.environ.get("OPENAI_API_KEY"))
            result = transcript_service.get_transcript(audio_url)

            transcript.text = result.get("text") or ""
            transcript.segments = json.dumps(result["segments"]) if result.get("segments") else None
            transcript.status = "completed"
            transcript.language = result.get("language")
            transcript.duration_seconds = result.get("duration")
            transcript.updated_at = datetime.utcnow()

            db.session.commit()
            print(f"Whisper transcription completed for call UUID: {call_uuid}")
        except Exception as e:
            print(f"Error transcribing call {call_uuid}: {str(e)}")
            try:
                transcript = db.session.query(CallTranscript).filter_by(call_id=call_uuid).first()
                if transcript:
                    transcript.status = "failed"
                    transcript.updated_at = datetime.utcnow()
                db.session.commit()
            except Exception as inner_e:
                print(f"Failed to update call with error fallback: {str(inner_e)}")

def get_formated_body():
    # Always include query string params (Telnyx TeXML sends GET with params in URL)
    query_params = request.args.to_dict()

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

    # Merge query params — they take lower priority than body fields
    merged = {**query_params, **body}
    if query_params:
        print(f"Query params: {query_params}")
    return merged

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
    
    calls = (
        db.session.query(Call)
        .options(joinedload(Call.transcript))
        .filter_by(from_phone=user_phone)
        .all()
    )
    calls_list = []
    for call in calls:
        transcript = getattr(call, 'transcript', None)
        if transcript:
            segments_parsed = None
            if transcript.segments:
                try:
                    segments_parsed = json.loads(transcript.segments)
                except (TypeError, ValueError):
                    pass
            transcript_json = {
                'id': transcript.id,
                'call_id': transcript.call_id,
                'text': transcript.text,
                'segments': segments_parsed,
                'status': transcript.status,
                'language': transcript.language,
                'duration_seconds': transcript.duration_seconds,
                'created_at': transcript.created_at.isoformat() if transcript.created_at else None,
                'updated_at': transcript.updated_at.isoformat() if transcript.updated_at else None,
            }
        else:
            transcript_json = None
        calls_list.append({
            'id': call.id,
            'from_phone': call.from_phone,
            'call_date': call.call_date.isoformat() if call.call_date else None,
            'title': call.title,
            'summary': call.summary,
            'recording_url': call.recording_url,
            'recording_duration': call.recording_duration,
            'recording_status': call.recording_status,
            'transcript': transcript_json,
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

        id = body.get('id')
        phone_number = body.get('phoneNumber')
        country_code = body.get('countryCode')
        fcm_token = body.get('fcmToken')
        language = body.get('language')
        
        if not phone_number:
            return jsonify({'error': 'phoneNumber is required'}), 400
        
        if not country_code:
            return jsonify({'error': 'country code is required'}), 400
        
        existing_user = db.session.query(User).filter_by(id=id).first()
        
        if existing_user:
            existing_user.fcm_token = fcm_token
            if country_code:
                existing_user.country_code = country_code
            if language is not None:
                existing_user.language = language
            existing_user.updated_at = datetime.now()
            existing_user.phone_number = phone_number
            db.session.commit()
            
            return jsonify({
                'userId': str(existing_user.id),
                'message': 'User updated successfully'
            }), 200
        else:
            new_user = User(
                id=id,
                phone_number=phone_number,
                fcm_token=fcm_token,
                language=language
            )
            if country_code:
                new_user.country_code = country_code
            db.session.add(new_user)
            db.session.commit()
            
            return jsonify({
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
            'name': user.name,
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
        name = body.get('name')

        if not user_id:
            return jsonify({'error': 'userId is required'}), 400

        if not phone_number:
            return jsonify({'error': 'phoneNumber is required'}), 400

        if not country_code:
            return jsonify({'error': 'countryCode is required'}), 400

        user = db.session.query(User).filter_by(id=user_id).first()

        if not user:
            return jsonify({'error': 'User not found'}), 404

        user.phone_number = phone_number
        user.country_code = country_code

        # Update name if provided
        if name is not None:
            user.name = name

        user.updated_at = datetime.utcnow()
        db.session.commit()

        return jsonify({
            'message': 'User updated successfully',
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

@app.route('/api/notifications/test', methods=['POST'])
def send_test_notification():
    """Send a test promotional notification to the given FCM token using localized copy."""
    body = get_formated_body()

    fcm_token = body.get('fcmToken')
    language = body.get('language')

    if not fcm_token:
        return jsonify({'error': 'fcmToken is required'}), 400

    title, notification_body = pick_random_coherent(language=language)
    ok = push_notification_service.send_notification(fcm_token, title, notification_body)

    if ok:
        return jsonify({'success': True, 'title': title, 'body': notification_body}), 200
    else:
        return jsonify({'success': False, 'error': 'Failed to send notification'}), 500


@app.route('/api/service/phone/<country_code>', methods=['GET'])
def get_service_phone_number(country_code):
    """Get the service phone number for the application."""

    us_number = "+16063938208"
    kr_number = "+82308640190"

    if country_code == "KR":
        phone_number = kr_number
    else:
        phone_number = us_number

    return jsonify({
        'phoneNumber': phone_number
    }), 200

@app.route('/recording/<recording_id>', methods=['GET'])
def get_recording(recording_id):
    """Redirect to a fresh presigned S3 URL for the recording."""
    from flask import redirect as flask_redirect
    print(f"get_recording: fetching presigned URL for recording_id={recording_id}")
    url = get_recording_url(recording_id)
    if not url:
        return jsonify({'error': 'Recording not found'}), 404
    print(f"get_recording: redirecting to {url}")
    return flask_redirect(url, code=302)

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

@app.route('/api/transcribe', methods=['POST'])
def transcribe_recording():
    """Transcribe a recording by URL using OpenAI Whisper. Returns text by phrases (segments)."""
    try:
        body = get_formated_body()
        recording_url = body.get('recording_url')
        if not recording_url or not str(recording_url).strip():
            return jsonify({'error': 'recording_url is required'}), 400
        if not os.environ.get('OPENAI_API_KEY'):
            return jsonify({'error': 'OPENAI_API_KEY is not configured'}), 500
        transcript_service = TranscriptService(api_key=os.environ.get('OPENAI_API_KEY'))
        result = transcript_service.get_transcript(str(recording_url).strip())
        return jsonify({
            'text': result.get('text', ''),
            'segments': result.get('segments', []),
            'language': result.get('language'),
            'duration': result.get('duration'),
        }), 200
    except requests.RequestException as e:
        return jsonify({'error': f'Failed to fetch recording: {str(e)}'}), 400
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route("/answer", methods=["GET", "POST"])
def answer():
    """Handle inbound call via TeXML. Telnyx POSTs JSON with event_type/payload, we return TeXML to record."""
    body = get_formated_body()
    print(f"RAW /answer: method={request.method} content_type={request.content_type} body={str(body)[:400]}")

    empty_xml = '<?xml version="1.0" encoding="UTF-8"?><Response></Response>'

    event_type = body.get('event_type', '')
    payload = body.get('payload', {}) if isinstance(body.get('payload'), dict) else {}

    # Only handle call_initiated — ignore hangup and other events
    if event_type != 'call_initiated':
        print(f"Answer webhook: ignoring event_type={event_type}")
        return Response(empty_xml, mimetype='text/xml')

    user_phone = payload.get('from')
    call_sid = payload.get('call_leg_id')

    print(f"Answer webhook call_initiated: from={user_phone}, call_leg_id={call_sid}")

    if not user_phone or not call_sid:
        print("Answer webhook: missing from or call_leg_id")
        return Response(empty_xml, mimetype='text/xml')

    existing_call = db.session.query(Call).filter_by(id=call_sid).first()
    user = db.session.query(User).filter_by(phone_number=user_phone).first()

    if not existing_call:
        call = Call(call_sid, user_phone, datetime.now(), user_id=user.id if user else None)
        db.session.add(call)
        db.session.commit()
        print(f"Created new call record: {call_sid}")
    else:
        print(f"Duplicate call_initiated for {call_sid}, returning empty response")
        return Response(empty_xml, mimetype='text/xml')

    callback_url = f"{HOST}/record-complete?call-uuid={call_sid}"
    texml = f'''<?xml version="1.0" encoding="UTF-8"?>
<Response>
    <Record maxLength="5400" playBeep="false" recordingStatusCallback="{callback_url}" recordingStatusCallbackEvent="completed" timeout="50"/>
</Response>'''

    print(f"Returning TeXML for call {call_sid}")
    return Response(texml, mimetype='text/xml')


@app.route("/record-complete", methods=["GET", "POST"])
def record_complete():
    """Handle TeXML recording completion callback."""
    body = get_formated_body()
    print(f"record-complete full payload: {body}")

    call_sid = request.args.get('call-uuid') or body.get('CallSid')
    recording_status = body.get('RecordingStatus')
    recording_url = body.get('RecordingUrl')
    recording_sid = body.get('RecordingSid')
    recording_duration = body.get('RecordingDuration')

    print(f"record-complete: call_sid={call_sid}, status={recording_status}, recording_sid={recording_sid}, url={recording_url}, duration={recording_duration}")

    if recording_status != 'completed':
        print(f"record-complete: status is '{recording_status}', ignoring")
        return Response('<?xml version="1.0" encoding="UTF-8"?><Response></Response>', mimetype='text/xml')

    if not call_sid:
        print("record-complete: missing call_sid")
        return Response('<?xml version="1.0" encoding="UTF-8"?><Response></Response>', mimetype='text/xml')

    call = db.session.query(Call).filter_by(id=call_sid).first()
    if not call:
        print(f"record-complete: call not found for {call_sid}")
        return Response('<?xml version="1.0" encoding="UTF-8"?><Response></Response>', mimetype='text/xml')

    if call.recording_status == 'completed' and call.recording_url:
        print(f"Recording already processed for call: {call_sid}")
        return Response('<?xml version="1.0" encoding="UTF-8"?><Response></Response>', mimetype='text/xml')

    duration = int(recording_duration) if recording_duration else None

    # Upload to S3 for permanent storage
    if recording_sid and recording_url:
        s3_url = upload_recording(recording_sid, recording_url)
        if s3_url:
            print(f"Recording {recording_sid} uploaded to S3")
        else:
            print(f"S3 upload failed or not configured for recording {recording_sid}")

    # Store our stable proxy URL (generates fresh presigned S3 URL on each request)
    final_url = f"{HOST}/recording/{recording_sid}" if recording_sid else recording_url
    call.recording_url = final_url
    call.recording_duration = duration
    call.recording_status = 'completed'

    # Resolve user for push notification
    user = db.session.query(User).filter_by(id=call.user_id).first() if call.user_id else None
    if user is None and call.from_phone:
        user = db.session.query(User).filter_by(phone_number=call.from_phone).order_by(User.created_at.asc()).first()
        if user:
            call.user_id = user.id

    if not db.session.query(CallTranscript).filter_by(call_id=call_sid).first():
        db.session.add(CallTranscript(call_id=call_sid, status='processing'))
    db.session.commit()

    if user and user.push_notifications_enabled and user.fcm_token:
        transcript = db.session.query(CallTranscript).filter_by(call_id=call_sid).first()
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
            'transcriptionStatus': transcript.status if transcript else 'pending',
            'transcriptionText': transcript.text if transcript else '',
        }
        success = push_notification_service.send_recording_complete_notification(user.fcm_token, call_data)
        print(f"Push notification {'sent' if success else 'failed'} for call {call_sid}")

    # Use the raw recording URL for Whisper transcription
    background_thread = threading.Thread(
        target=process_transcript_background,
        args=(call_sid, recording_url)
    )
    background_thread.daemon = True
    background_thread.start()
    print(f"Started Whisper transcription for call: {call_sid}")

    return Response('<?xml version="1.0" encoding="UTF-8"?><Response></Response>', mimetype='text/xml')

if __name__ == "__main__":
    with app.app_context():
        from flask_migrate import upgrade
        try:
            # Apply any pending migrations automatically
            upgrade()
            print("Database migrations applied successfully")
        except Exception as e:
            print(f"Migration error: {e}")
            # Fallback to create_all if migrations haven't been initialized
            db.create_all()
            print("Database tables created using create_all()")

    port = int(os.environ.get('PORT', 8080))
    app.run(host='0.0.0.0', port=port, debug=False)