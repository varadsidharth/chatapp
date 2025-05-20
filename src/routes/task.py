from flask import Blueprint, request, jsonify, session, render_template, redirect, url_for, flash
from src.models.user import db, User, Task
from functools import wraps
from datetime import datetime, timedelta

task_bp = Blueprint('task', __name__)

# Authentication decorator
def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user_id' not in session:
            return redirect(url_for('auth.login'))
        return f(*args, **kwargs)
    return decorated_function

@task_bp.route('/')
@login_required
def index():
    user_id = session.get('user_id')
    user = User.query.get(user_id)
    
    # Get all tasks for the user
    tasks = Task.query.filter_by(user_id=user_id).order_by(Task.deadline.asc()).all()
    
    # Get current time for comparison
    now = datetime.utcnow()
    
    return render_template('tasks.html', user=user, tasks=tasks, now=now)

@task_bp.route('/complete/<int:task_id>', methods=['POST'])
@login_required
def complete_task(task_id):
    user_id = session.get('user_id')
    
    # Get the task
    task = Task.query.filter_by(id=task_id, user_id=user_id).first_or_404()
    
    # Mark as completed
    task.completed = True
    task.completed_at = datetime.utcnow()
    
    db.session.commit()
    
    flash('Task marked as completed!', 'success')
    return redirect(url_for('task.index'))

@task_bp.route('/add', methods=['POST'])
@login_required
def add_task():
    user_id = session.get('user_id')
    description = request.form.get('description')
    days = int(request.form.get('days', 1))
    
    if not description:
        flash('Task description cannot be empty', 'error')
        return redirect(url_for('task.index'))
    
    # Set deadline to specified number of days from now
    deadline = datetime.utcnow() + timedelta(days=days)
    
    # Create new task
    new_task = Task(
        user_id=user_id,
        description=description,
        deadline=deadline,
        completed=False
    )
    
    db.session.add(new_task)
    db.session.commit()
    
    flash('Task added successfully', 'success')
    return redirect(url_for('task.index'))

@task_bp.route('/delete/<int:task_id>', methods=['POST'])
@login_required
def delete_task(task_id):
    user_id = session.get('user_id')
    
    # Get the task
    task = Task.query.filter_by(id=task_id, user_id=user_id).first_or_404()
    
    db.session.delete(task)
    db.session.commit()
    
    flash('Task deleted successfully', 'success')
    return redirect(url_for('task.index'))
