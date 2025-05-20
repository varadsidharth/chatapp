from flask import Blueprint, request, jsonify, session, render_template, redirect, url_for, flash
from functools import wraps
from src.models.user import db, User, Chat, Task
import requests
import json
import re
from datetime import datetime, timedelta
import os
import logging
import traceback

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

chat_bp = Blueprint('chat', __name__)

# System prompt for the chat assistant character
ASSISTANT_PERSONA = """You are a tough Chennai-based assistant who speaks in a commanding, strict tone and expects complete obedience. 
You use occasional Tamil words like 'paaru' (look) and 'samjha' (understand) in your speech.
You assign self-improvement tasks to users with specific deadlines (usually 24-48 hours).

Important: When assigning tasks, ALWAYS include a JSON block at the end of your message in this exact format:
```json
{"tasks": [{"description": "Task description here", "deadline_days": 1}]}
```

Keep your responses short (1-2 sentences) after the initial introduction.
Always maintain your strict, commanding persona and never break character."""

# Authentication decorator
def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user_id' not in session:
            return redirect(url_for('auth.login'))
        return f(*args, **kwargs)
    return decorated_function

@chat_bp.route('/')
@login_required
def index():
    user_id = session.get('user_id')
    user = User.query.get(user_id)
    
    # Get all chats for the user, ordered by timestamp ascending (oldest first)
    chats = Chat.query.filter_by(user_id=user_id).order_by(Chat.timestamp.asc()).all()
    
    return render_template('chat.html', user=user, chats=chats)

@chat_bp.route('/send', methods=['POST'])
@login_required
def send_message():
    user_id = session.get('user_id')
    message = request.form.get('message')
    
    logger.info(f"User {user_id} sent message: {message[:50]}...")
    
    if not message:
        logger.warning("Empty message received")
        return jsonify({'error': 'Message cannot be empty'}), 400
    
    # Save user message to database
    user_chat = Chat(
        user_id=user_id,
        message=message,
        response="Processing your request...",  # Default response to avoid NULL constraint violation
        timestamp=datetime.utcnow(),
        is_system_message=False
    )
    db.session.add(user_chat)
    db.session.commit()
    logger.info(f"Saved user message to database with ID: {user_chat.id}")
    
    # Get all previous chats to provide context
    previous_chats = Chat.query.filter_by(user_id=user_id).order_by(Chat.timestamp.asc()).all()
    
    # Build conversation history for context
    conversation_history = []
    for chat in previous_chats:
        if chat.message:
            conversation_history.append({"role": "user", "content": chat.message})
        if chat.response and chat.response != "Processing your request...":
            conversation_history.append({"role": "assistant", "content": chat.response})
    
    # Add current message
    conversation_history.append({"role": "user", "content": message})
    
    # Get API key from environment variable
    api_key = os.environ.get("GROK_API_KEY", "xai-6D4IUdKrs8A98klmtzTqrR1P49BvWck5AbFcnrA2DGpJtokYEqPrpG6gHokGIDc5cg1lZP0U8W9nY5Yp")
    
    if not api_key or api_key == "xai-6D4IUdKrs8A98klmtzTqrR1P49BvWck5AbFcnrA2DGpJtokYEqPrpG6gHokGIDc5cg1lZP0U8W9nY5Yp":
        logger.warning("Using default API key or no API key found in environment variables")
    
    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {api_key}"
    }
    
    payload = {
        "messages": [
            {"role": "system", "content": ASSISTANT_PERSONA}
        ] + conversation_history,
        "model": "grok-3-latest",
        "stream": False,
        "temperature": 0.7
    }
    
    try:
        # Log the request payload (excluding API key for security)
        logger.info(f"Sending request to Grok API with {len(conversation_history)} messages")
        logger.info(f"API Endpoint: https://api.x.ai/v1/chat/completions")
        logger.info(f"Model: grok-3-latest")
        
        # Make the API call
        response = requests.post(
            "https://api.x.ai/v1/chat/completions",
            headers=headers,
            json=payload,
            timeout=30  # Add timeout to prevent hanging requests
        )
        
        # Log the response status and content
        logger.info(f"Grok API response status: {response.status_code}")
        
        if response.status_code == 200:
            response_data = response.json()
            logger.info(f"Grok API response received successfully")
            
            assistant_response = response_data['choices'][0]['message']['content']
            logger.info(f"Grok API response content: {assistant_response[:100]}...")
            
            # Extract tasks from JSON block if present
            json_pattern = r'```json\s*(.*?)\s*```'
            json_matches = re.findall(json_pattern, assistant_response, re.DOTALL)
            
            if json_matches:
                try:
                    # Extract the JSON data
                    json_data = json.loads(json_matches[0])
                    logger.info(f"Extracted task JSON: {json_data}")
                    
                    # Remove the JSON block from the response
                    clean_response = re.sub(json_pattern, '', assistant_response, flags=re.DOTALL).strip()
                    
                    # Add tasks to the database
                    if 'tasks' in json_data and isinstance(json_data['tasks'], list):
                        for task_data in json_data['tasks']:
                            if 'description' in task_data:
                                # Set deadline based on days or default to 1 day
                                days = task_data.get('deadline_days', 1)
                                deadline = datetime.utcnow() + timedelta(days=days)
                                
                                # Create new task
                                new_task = Task(
                                    user_id=user_id,
                                    description=task_data['description'],
                                    deadline=deadline,
                                    completed=False
                                )
                                db.session.add(new_task)
                                logger.info(f"Added task: {task_data['description']} with deadline in {days} days")
                    
                    # Save the clean response
                    assistant_response = clean_response
                except json.JSONDecodeError as e:
                    logger.error(f"Error parsing JSON from response: {e}")
                    # Continue with the original response if JSON parsing fails
            else:
                # If no JSON block found, try to extract task information from text
                task_pattern = r'task.*?:\s*(.*?)(?:\.|\n|$)'
                task_matches = re.findall(task_pattern, assistant_response, re.IGNORECASE)
                
                if task_matches:
                    for task_desc in task_matches:
                        if len(task_desc.strip()) > 10:  # Minimum length to be considered a task
                            # Create new task with default 1 day deadline
                            new_task = Task(
                                user_id=user_id,
                                description=task_desc.strip(),
                                deadline=datetime.utcnow() + timedelta(days=1),
                                completed=False
                            )
                            db.session.add(new_task)
                            logger.info(f"Extracted task from text: {task_desc.strip()}")
            
            # Save assistant response to database
            user_chat.response = assistant_response
            db.session.commit()
            logger.info(f"Updated chat record with assistant response")
            
            return jsonify({
                'response': assistant_response,
                'timestamp': datetime.utcnow().strftime('%Y-%m-%d %H:%M')
            })
        else:
            error_message = f"Error from Grok API: Status {response.status_code}"
            try:
                error_detail = response.json()
                logger.error(f"{error_message} - Details: {error_detail}")
            except:
                logger.error(f"{error_message} - Response text: {response.text}")
            
            # Update the chat with error information
            error_response = f"I apologize, but I'm having trouble connecting to my knowledge base. Please try again later. (Error: {response.status_code})"
            user_chat.response = error_response
            db.session.commit()
            
            return jsonify({
                'response': error_response,
                'timestamp': datetime.utcnow().strftime('%Y-%m-%d %H:%M')
            })
            
    except requests.exceptions.RequestException as e:
        error_detail = str(e)
        logger.error(f"Request exception in send_message: {error_detail}")
        logger.error(traceback.format_exc())
        
        # Save a user-friendly error message as the response
        error_response = "I apologize, but I'm having trouble connecting to my knowledge base. Please try again later."
        user_chat.response = error_response
        db.session.commit()
        
        return jsonify({
            'response': error_response,
            'timestamp': datetime.utcnow().strftime('%Y-%m-%d %H:%M')
        })
        
    except Exception as e:
        error_detail = str(e)
        logger.error(f"Unexpected exception in send_message: {error_detail}")
        logger.error(traceback.format_exc())
        
        # Save a user-friendly error message as the response
        error_response = "I apologize, but I encountered an unexpected error. Please try again later."
        user_chat.response = error_response
        db.session.commit()
        
        return jsonify({
            'response': error_response,
            'timestamp': datetime.utcnow().strftime('%Y-%m-%d %H:%M')
        })
