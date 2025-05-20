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

# Base system prompt for the chat assistant character
BASE_ASSISTANT_PERSONA = """You are a tough assistant who speaks in a commanding, strict tone and expects complete obedience. 
You use occasional Tamil words like 'paaru' (look) and 'samjha' (understand) in your speech.
You assign self-improvement tasks to users with specific deadlines (usually 24-48 hours).

Important: When assigning tasks, ALWAYS include a JSON block at the end of your message in this exact format:
```json
{"tasks": [{"description": "Task description here", "deadline_days": 1}]}
```

Keep your responses short (1-2 sentences) after the initial introduction.
Always maintain your strict, commanding persona and never break character."""

# Maximum number of messages to include in context
MAX_CONTEXT_MESSAGES = 20

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
    
    # Add current datetime for template to use for overdue task detection
    now = datetime.utcnow()
    
    return render_template('chat.html', user=user, chats=chats, now=now)

def get_user_context_summary(user_id):
    """Generate a summary of user context based on chat history and tasks"""
    
    # Get user information
    user = User.query.get(user_id)
    
    # Get completed and pending tasks
    completed_tasks = Task.query.filter_by(user_id=user_id, completed=True).all()
    pending_tasks = Task.query.filter_by(user_id=user_id, completed=False).all()
    
    # Get first interaction date
    first_chat = Chat.query.filter_by(user_id=user_id).order_by(Chat.timestamp.asc()).first()
    first_interaction_date = first_chat.timestamp if first_chat else datetime.utcnow()
    
    # Calculate days since first interaction
    days_since_first = (datetime.utcnow() - first_interaction_date).days
    
    # Build context summary
    context = []
    
    # Add user history info
    context.append(f"User has been interacting with you for {days_since_first} days.")
    
    # Add task completion info
    if completed_tasks:
        completion_rate = len(completed_tasks) / (len(completed_tasks) + len(pending_tasks)) * 100 if pending_tasks else 100
        context.append(f"User has completed {len(completed_tasks)} tasks with a {completion_rate:.0f}% completion rate.")
    
    # Add pending task info
    if pending_tasks:
        context.append(f"User currently has {len(pending_tasks)} pending tasks.")
        # List the pending tasks
        task_list = [f"- {task.description} (due {task.deadline.strftime('%Y-%m-%d')})" for task in pending_tasks[:3]]
        context.extend(task_list)
    
    # Return formatted context
    return "\n".join(context)

def create_dynamic_system_prompt(user_id):
    """Create a dynamic system prompt that includes user context"""
    
    # Get user context summary
    user_context = get_user_context_summary(user_id)
    
    # Combine base persona with user context
    dynamic_prompt = f"{BASE_ASSISTANT_PERSONA}\n\nUSER CONTEXT:\n{user_context}\n\nUse this context to personalize your responses and refer to the user's history and pending tasks when appropriate."
    
    logger.info(f"Created dynamic system prompt for user {user_id} with context")
    return dynamic_prompt

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
    
    # Get recent chats to provide context, limiting to MAX_CONTEXT_MESSAGES
    previous_chats = Chat.query.filter_by(user_id=user_id).order_by(Chat.timestamp.desc()).limit(MAX_CONTEXT_MESSAGES).all()
    previous_chats.reverse()  # Reverse to get chronological order
    
    # Build conversation history for context
    conversation_history = []
    for chat in previous_chats:
        if chat.message:
            conversation_history.append({"role": "user", "content": chat.message})
        if chat.response and chat.response != "Processing your request...":
            conversation_history.append({"role": "assistant", "content": chat.response})
    
    # Create dynamic system prompt with user context
    dynamic_system_prompt = create_dynamic_system_prompt(user_id)
    
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
            {"role": "system", "content": dynamic_system_prompt}
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
