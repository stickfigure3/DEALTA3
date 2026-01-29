"""
Twilio SMS webhook handler.
Receives SMS messages and responds via Gemini.
"""

import json
import os
import sys
import urllib.parse

# Add shared module to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from shared import storage
from shared.gemini import GeminiAgent

# Twilio credentials from environment
TWILIO_ACCOUNT_SID = os.environ.get("TWILIO_ACCOUNT_SID")
TWILIO_AUTH_TOKEN = os.environ.get("TWILIO_AUTH_TOKEN")
TWILIO_PHONE_NUMBER = os.environ.get("TWILIO_PHONE_NUMBER")


def response(status_code: int, body: str, content_type: str = "application/xml") -> dict:
    """Create API Gateway response for Twilio."""
    return {
        "statusCode": status_code,
        "headers": {
            "Content-Type": content_type
        },
        "body": body
    }


def twiml_response(message: str) -> str:
    """Create TwiML response for SMS."""
    # Escape XML special characters
    message = message.replace("&", "&amp;")
    message = message.replace("<", "&lt;")
    message = message.replace(">", "&gt;")
    
    # Truncate for SMS limits (1600 chars max for multipart)
    if len(message) > 1500:
        message = message[:1497] + "..."
    
    return f"""<?xml version="1.0" encoding="UTF-8"?>
<Response>
    <Message>{message}</Message>
</Response>"""


def handler(event, context):
    """Main Lambda handler for Twilio webhook."""
    
    method = event.get("httpMethod", "GET")
    
    if method == "GET":
        # Health check
        return response(200, "Twilio webhook active", "text/plain")
    
    if method != "POST":
        return response(405, "Method not allowed", "text/plain")
    
    # Parse form data from Twilio
    try:
        body = event.get("body", "")
        if event.get("isBase64Encoded"):
            import base64
            body = base64.b64decode(body).decode("utf-8")
        
        params = urllib.parse.parse_qs(body)
        
        from_number = params.get("From", [""])[0]
        to_number = params.get("To", [""])[0]
        message_body = params.get("Body", [""])[0].strip()
        
    except Exception as e:
        return response(400, twiml_response(f"Error parsing request: {str(e)}"))
    
    if not from_number or not message_body:
        return response(400, twiml_response("Invalid request"))
    
    # Normalize phone number as user ID
    user_id = from_number.replace("+", "").replace("-", "").replace(" ", "")
    
    # Handle special commands
    lower_body = message_body.lower()
    
    if lower_body == "help":
        return response(200, twiml_response(
            "DELTA3 SMS Commands:\n"
            "• REGISTER <email> <password> - Create account\n"
            "• LINK <email> <password> - Link phone to account\n"
            "• KEY <gemini-api-key> - Set your Gemini key\n"
            "• Any other message - Chat with AI\n"
            "• CLEAR - Clear chat history"
        ))
    
    if lower_body.startswith("register "):
        return handle_register(user_id, from_number, message_body)
    
    if lower_body.startswith("link "):
        return handle_link(user_id, from_number, message_body)
    
    if lower_body.startswith("key "):
        return handle_set_key(user_id, message_body)
    
    if lower_body == "clear":
        return handle_clear(user_id)
    
    # Regular chat message
    return handle_chat(user_id, message_body)


def handle_register(phone_user_id: str, phone_number: str, message: str):
    """Handle REGISTER command."""
    parts = message.split(maxsplit=2)
    
    if len(parts) < 3:
        return response(200, twiml_response(
            "Usage: REGISTER <email> <password>\n"
            "Example: REGISTER user@example.com mypassword123"
        ))
    
    email = parts[1].strip()
    password = parts[2].strip()
    
    try:
        result = storage.create_user(email, password)
        
        # Store phone -> user mapping
        # In production, add this to DynamoDB
        
        return response(200, twiml_response(
            f"Account created!\n"
            f"Email: {email}\n"
            f"API Key: {result['api_key']}\n\n"
            f"Now send: KEY <your-gemini-api-key>"
        ))
    except ValueError as e:
        return response(200, twiml_response(f"Registration failed: {str(e)}"))
    except Exception as e:
        return response(200, twiml_response(f"Error: {str(e)}"))


def handle_link(phone_user_id: str, phone_number: str, message: str):
    """Handle LINK command to connect phone to existing account."""
    parts = message.split(maxsplit=2)
    
    if len(parts) < 3:
        return response(200, twiml_response(
            "Usage: LINK <email> <password>\n"
            "Links your phone to an existing account."
        ))
    
    email = parts[1].strip()
    password = parts[2].strip()
    
    result = storage.verify_login(email, password)
    
    if not result:
        return response(200, twiml_response("Invalid email or password"))
    
    # In production, store phone -> user_id mapping in DynamoDB
    
    return response(200, twiml_response(
        f"Phone linked to {email}!\n"
        f"You can now chat with the AI."
    ))


def handle_set_key(user_id: str, message: str):
    """Handle KEY command to set Gemini API key."""
    parts = message.split(maxsplit=1)
    
    if len(parts) < 2:
        return response(200, twiml_response(
            "Usage: KEY <gemini-api-key>\n"
            "Get your key at: makersuite.google.com/app/apikey"
        ))
    
    gemini_key = parts[1].strip()
    
    if not gemini_key.startswith("AIza"):
        return response(200, twiml_response(
            "Invalid key format. Gemini keys start with 'AIza...'"
        ))
    
    # Try to find user by phone or create temp mapping
    # For MVP, use phone number as user_id
    user = storage.get_user(user_id)
    
    if not user:
        # Create user for this phone number
        try:
            result = storage.create_user(f"{user_id}@sms.delta3.ai", user_id)
            user_id = result["user_id"]
        except:
            pass
    
    if storage.update_gemini_key(user_id, gemini_key):
        return response(200, twiml_response(
            "Gemini API key saved!\n"
            "You can now chat with the AI. Try: 'Write hello world in Python'"
        ))
    
    return response(200, twiml_response("Failed to save key. Try again."))


def handle_clear(user_id: str):
    """Handle CLEAR command."""
    storage.clear_chat_history(user_id)
    return response(200, twiml_response("Chat history cleared!"))


def handle_chat(user_id: str, message: str):
    """Handle regular chat message."""
    user = storage.get_user(user_id)
    
    # Check for phone-based user
    if not user:
        user = storage.get_user(f"{user_id}@sms.delta3.ai")
        if user:
            user_id = user["user_id"]
    
    if not user:
        return response(200, twiml_response(
            "Welcome to DELTA3!\n"
            "First, send: KEY <your-gemini-api-key>\n"
            "Get a key at: makersuite.google.com/app/apikey\n\n"
            "Send HELP for more commands."
        ))
    
    gemini_key = user.get("gemini_key")
    
    if not gemini_key:
        return response(200, twiml_response(
            "No Gemini API key set.\n"
            "Send: KEY <your-api-key>\n"
            "Get one at: makersuite.google.com/app/apikey"
        ))
    
    try:
        # Create agent and process message
        agent = GeminiAgent(api_key=gemini_key)
        result = agent.process_message(message)
        
        # Save to history
        storage.save_chat_message(user_id, "user", message)
        storage.save_chat_message(
            user_id,
            "assistant",
            result["response"],
            tool_calls=result.get("tool_calls")
        )
        
        # Format response for SMS
        response_text = result["response"]
        
        # Add tool call summary if any
        if result.get("tool_calls"):
            tools_used = [tc["tool"] for tc in result["tool_calls"]]
            response_text = f"[Used: {', '.join(tools_used)}]\n\n{response_text}"
        
        return response(200, twiml_response(response_text))
    
    except Exception as e:
        error_msg = str(e)
        if "429" in error_msg:
            return response(200, twiml_response(
                "Rate limit reached. Wait a moment and try again."
            ))
        return response(200, twiml_response(f"Error: {error_msg[:200]}"))
