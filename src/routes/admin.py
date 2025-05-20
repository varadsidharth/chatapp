from flask import Blueprint, render_template, request, redirect, url_for, flash, session, jsonify
from src.models.user import db, User, Chat, Task
from functools import wraps
from datetime import datetime, timedelta
import json

admin_bp = Blueprint('admin', __name__, url_prefix='/admin')

# Admin authentication decorator
def admin_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user_id' not in session:
            return redirect(url_for('auth.login'))
        
        user = User.query.get(session['user_id'])
        if not user or not user.is_admin:
            flash('Admin access required', 'error')
            return redirect(url_for('chat.index'))
            
        return f(*args, **kwargs)
    return decorated_function

@admin_bp.route('/')
@admin_required
def index():
    # Dashboard statistics
    total_users = User.query.count()
    total_chats = Chat.query.count()
    total_tasks = Task.query.count()
    
    # Active users in last 24 hours
    yesterday = datetime.utcnow() - timedelta(days=1)
    active_users = User.query.filter(User.last_login >= yesterday).count()
    
    # Recent users
    recent_users = User.query.order_by(User.last_login.desc()).limit(5).all()
    
    return render_template('admin/dashboard.html', 
                          total_users=total_users,
                          total_chats=total_chats,
                          total_tasks=total_tasks,
                          active_users=active_users,
                          recent_users=recent_users)

@admin_bp.route('/users')
@admin_required
def users():
    all_users = User.query.all()
    return render_template('admin/users.html', users=all_users)

@admin_bp.route('/user/<int:user_id>')
@admin_required
def user_detail(user_id):
    user = User.query.get_or_404(user_id)
    chats = Chat.query.filter_by(user_id=user_id).order_by(Chat.timestamp.asc()).all()
    tasks = Task.query.filter_by(user_id=user_id).order_by(Task.deadline.asc()).all()
    
    return render_template('admin/user_detail.html', user=user, chats=chats, tasks=tasks)

@admin_bp.route('/user/<int:user_id>/delete', methods=['POST'])
@admin_required
def delete_user(user_id):
    user = User.query.get_or_404(user_id)
    
    # Don't allow deleting yourself
    if user_id == session['user_id']:
        flash('You cannot delete your own account', 'error')
        return redirect(url_for('admin.users'))
    
    # Delete all user data
    Chat.query.filter_by(user_id=user_id).delete()
    Task.query.filter_by(user_id=user_id).delete()
    
    db.session.delete(user)
    db.session.commit()
    
    flash(f'User {user.email} has been deleted', 'success')
    return redirect(url_for('admin.users'))

@admin_bp.route('/chat/<int:chat_id>/delete', methods=['POST'])
@admin_required
def delete_chat(chat_id):
    chat = Chat.query.get_or_404(chat_id)
    user_id = chat.user_id
    
    db.session.delete(chat)
    db.session.commit()
    
    flash('Chat message deleted', 'success')
    return redirect(url_for('admin.user_detail', user_id=user_id))

@admin_bp.route('/system-prompt', methods=['GET', 'POST'])
@admin_required
def system_prompt():
    from src.routes.chat import ASSISTANT_PERSONA
    
    if request.method == 'POST':
        new_prompt = request.form.get('system_prompt')
        
        # Update the system prompt in a config file
        with open('src/config/system_prompt.txt', 'w') as f:
            f.write(new_prompt)
        
        flash('System prompt updated successfully', 'success')
        return redirect(url_for('admin.system_prompt'))
    
    # Create the config directory and file if it doesn't exist
    import os
    os.makedirs('src/config', exist_ok=True)
    
    try:
        with open('src/config/system_prompt.txt', 'r') as f:
            current_prompt = f.read()
    except FileNotFoundError:
        # If file doesn't exist, use the default prompt and create the file
        current_prompt = ASSISTANT_PERSONA
        with open('src/config/system_prompt.txt', 'w') as f:
            f.write(current_prompt)
    
    return render_template('admin/system_prompt.html', system_prompt=current_prompt)

@admin_bp.route('/user/<int:user_id>/send-message', methods=['GET', 'POST'])
@admin_required
def send_message(user_id):
    user = User.query.get_or_404(user_id)
    
    if request.method == 'POST':
        message = request.form.get('message')
        
        if message:
            # Create a system message from the assistant
            new_chat = Chat(
                user_id=user_id,
                message=None,
                response=message,
                timestamp=datetime.utcnow(),
                is_system_message=True
            )
            
            db.session.add(new_chat)
            db.session.commit()
            
            flash('Message sent successfully', 'success')
            return redirect(url_for('admin.user_detail', user_id=user_id))
        else:
            flash('Message cannot be empty', 'error')
    
    return render_template('admin/send_message.html', user=user)

@admin_bp.route('/user/<int:user_id>/assign-task', methods=['GET', 'POST'])
@admin_required
def assign_task(user_id):
    user = User.query.get_or_404(user_id)
    
    if request.method == 'POST':
        description = request.form.get('description')
        days = int(request.form.get('days', 1))
        
        if description:
            # Create a new task for the user
            deadline = datetime.utcnow() + timedelta(days=days)
            
            new_task = Task(
                user_id=user_id,
                description=description,
                deadline=deadline,
                completed=False
            )
            
            db.session.add(new_task)
            db.session.commit()
            
            # Also send a system message about the task
            task_message = f"I've assigned you a new task: {description}. You have {days} days to complete it. Don't disappoint me, paaru!"
            
            new_chat = Chat(
                user_id=user_id,
                message=None,
                response=task_message,
                timestamp=datetime.utcnow(),
                is_system_message=True
            )
            
            db.session.add(new_chat)
            db.session.commit()
            
            flash('Task assigned successfully', 'success')
            return redirect(url_for('admin.user_detail', user_id=user_id))
        else:
            flash('Task description cannot be empty', 'error')
    
    return render_template('admin/assign_task.html', user=user)
