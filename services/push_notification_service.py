import os
import json
import firebase_admin
from firebase_admin import credentials, messaging
from typing import Optional, List, Dict, Any

class PushNotificationService:
    def __init__(self):
        self.initialized = False
        self.app = None
        self.initialize_firebase()
    
    def initialize_firebase(self):
        """Initialize Firebase Admin SDK with service account credentials"""
        try:
            firebase_creds = os.environ.get('FIREBASE_SERVICE_CREDENTIALS')
            
            if not firebase_creds:
                print("Warning: FIREBASE_SERVICE_CREDENTIALS not set. Push notifications will not work.")
                return

            if firebase_creds.startswith('{'):
                cred_dict = json.loads(firebase_creds)
                cred = credentials.Certificate(cred_dict)
            elif os.path.exists(firebase_creds):
                cred = credentials.Certificate(firebase_creds)
            else:
                print(f"Error: FIREBASE_SERVICE_CREDENTIALS is neither a valid JSON nor a valid file path")
                return
            
            self.app = firebase_admin.initialize_app(cred)
            self.initialized = True
            print("Firebase Admin SDK initialized successfully")
            
        except json.JSONDecodeError as e:
            print(f"Error parsing Firebase credentials JSON: {str(e)}")
            self.initialized = False
        except Exception as e:
            print(f"Error initializing Firebase Admin SDK: {str(e)}")
            self.initialized = False
    
    def send_notification(self, fcm_token: str, title: str, body: str, 
                         data: Optional[Dict[str, str]] = None) -> bool:
        """
        Send a push notification to a single device
        
        Args:
            fcm_token: The FCM registration token for the device
            title: Notification title
            body: Notification body text
            data: Optional data payload
            
        Returns:
            bool: True if notification was sent successfully, False otherwise
        """
        if not self.initialized:
            print("Firebase not initialized. Cannot send notification.")
            return False
        
        try:
            message = messaging.Message(
                notification=messaging.Notification(
                    title=title,
                    body=body
                ),
                token=fcm_token,
                data=data or {}
            )
            
            response = messaging.send(message)
            print(f"Successfully sent notification: {response}")
            return True
            
        except messaging.UnregisteredError:
            print(f"Token {fcm_token} is invalid or unregistered")
            return False
        except Exception as e:
            print(f"Error sending notification: {str(e)}")
            return False
    
    def send_multicast_notification(self, fcm_tokens: List[str], title: str, 
                                   body: str, data: Optional[Dict[str, str]] = None) -> Dict[str, Any]:
        """
        Send push notification to multiple devices
        
        Args:
            fcm_tokens: List of FCM registration tokens
            title: Notification title
            body: Notification body text
            data: Optional data payload
            
        Returns:
            dict: Results of the multicast send operation
        """
        if not self.initialized:
            print("Firebase not initialized. Cannot send notifications.")
            return {"success_count": 0, "failure_count": len(fcm_tokens)}
        
        if not fcm_tokens:
            return {"success_count": 0, "failure_count": 0}
        
        try:
            message = messaging.MulticastMessage(
                notification=messaging.Notification(
                    title=title,
                    body=body
                ),
                tokens=fcm_tokens,
                data=data or {}
            )
            
            response = messaging.send_multicast(message)
            
            results = {
                "success_count": response.success_count,
                "failure_count": response.failure_count,
                "failed_tokens": []
            }
            
            if response.failure_count > 0:
                for idx, resp in enumerate(response.responses):
                    if not resp.success:
                        results["failed_tokens"].append({
                            "token": fcm_tokens[idx],
                            "error": str(resp.exception)
                        })
            
            print(f"Multicast result - Success: {response.success_count}, Failures: {response.failure_count}")
            return results
            
        except Exception as e:
            print(f"Error sending multicast notification: {str(e)}")
            return {
                "success_count": 0,
                "failure_count": len(fcm_tokens),
                "error": str(e)
            }
    
    def send_call_notification(self, fcm_token: str, caller_name: str, 
                              phone_number: str, call_id: str) -> bool:
        """
        Send a notification about an incoming call
        
        Args:
            fcm_token: The FCM registration token for the device
            caller_name: Name of the caller
            phone_number: Phone number of the caller
            call_id: Unique identifier for the call
            
        Returns:
            bool: True if notification was sent successfully
        """
        title = "Incoming Call"
        body = f"Call from {caller_name} ({phone_number})"
        
        data = {
            "type": "incoming_call",
            "call_id": str(call_id),
            "caller_name": caller_name,
            "phone_number": phone_number
        }
        
        return self.send_notification(fcm_token, title, body, data)
    
    def send_call_summary_notification(self, fcm_token: str, call_id: str) -> bool:
        """
        Send a notification when call summary is ready
        
        Args:
            fcm_token: The FCM registration token for the device
            call_id: Unique identifier for the call
            
        Returns:
            bool: True if notification was sent successfully
        """
        title = "Call Summary Ready"
        body = "Your call summary has been generated and is ready to view"
        
        data = {
            "type": "call_summary_ready",
            "call_id": str(call_id)
        }
        
        return self.send_notification(fcm_token, title, body, data)
    
    def send_recording_complete_notification(self, fcm_token: str, call_data: Dict[str, Any]) -> bool:
        """
        Send a notification when recording is complete with full call data
        
        Args:
            fcm_token: The FCM registration token for the device
            call_data: Dictionary containing all call information for the Recording struct
            
        Returns:
            bool: True if notification was sent successfully
        """
        title = "Recording Complete"
        body = f"Your call recording from is ready!"

        data = {
            "type": "recording_complete",
            "id": str(call_data.get('id', '')),
            "callDate": str(call_data.get('callDate', '')),
            "fromPhone": str(call_data.get('fromPhone', '')),
            "toPhone": str(call_data.get('toPhone', '')),
            "recordingDuration": str(call_data.get('recordingDuration', 0)),
            "recordingStatus": str(call_data.get('recordingStatus', '')),
            "recordingUrl": str(call_data.get('recordingUrl', '')),
            "summary": str(call_data.get('summary', '')),
            "title": str(call_data.get('title', '')),
            "transcriptionStatus": str(call_data.get('transcriptionStatus', '')),
            "transcriptionText": str(call_data.get('transcriptionText', ''))
        }
        
        return self.send_notification(fcm_token, title, body, data)

push_notification_service = PushNotificationService()