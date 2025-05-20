import sys
import os
from flask import Flask, render_template
from flask_sqlalchemy import SQLAlchemy
from src.models.user import db
from src.routes.auth import auth_bp
from src.routes.chat import chat_bp
from src.routes.task import task_bp
from src.routes.admin import admin_bp
import logging

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Import path setup required by the template
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

def create_app():
    app = Flask(__name__)
    
    # Configuration
    app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY', os.urandom(24))
    
    # Database configuration with better error handling
    db_uri = f"postgresql://{os.getenv('DB_USERNAME', 'postgres')}:{os.getenv('DB_PASSWORD', 'password')}@{os.getenv('DB_HOST', 'localhost')}:{os.getenv('DB_PORT', '5432')}/{os.getenv('DB_NAME', 'postgres')}"
    app.config['SQLALCHEMY_DATABASE_URI'] = db_uri
    app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
    
    # Log database connection details (without password)
    safe_db_uri = db_uri.replace(os.getenv('DB_PASSWORD', 'password'), '********')
    logger.info(f"Connecting to database: {safe_db_uri}")
    
    # Initialize extensions
    db.init_app(app)
    
    # Register blueprints
    app.register_blueprint(auth_bp)
    app.register_blueprint(chat_bp, url_prefix='/chat')
    app.register_blueprint(task_bp, url_prefix='/task')
    app.register_blueprint(admin_bp, url_prefix='/admin')
    
    # Create database tables with error handling
    with app.app_context():
        try:
            logger.info("Attempting to create database tables...")
            db.create_all()
            logger.info("Database tables created successfully")
            
            # Create admin user if not exists
            from src.models.user import User
            admin = User.query.filter_by(email='admin@example.com').first()
            if not admin:
                admin = User(email='admin@example.com', is_admin=True)
                admin.set_password('admin123')
                db.session.add(admin)
                db.session.commit()
                logger.info("Admin user created: admin@example.com / admin123")
            else:
                logger.info("Admin user already exists")
        except Exception as e:
            logger.error(f"Error during database initialization: {str(e)}")
            logger.error("Database connection failed. Please check your environment variables and database configuration.")
            # Continue execution to allow the app to start even if DB fails
            # This prevents the app from getting stuck in a loading state
    
    @app.route('/')
    def index():
        return render_template('index.html')
    
    # Add error handlers
    @app.errorhandler(500)
    def server_error(e):
        logger.error(f"Server error: {str(e)}")
        return render_template('error.html', error=str(e)), 500
    
    @app.errorhandler(404)
    def not_found(e):
        return render_template('error.html', error="Page not found"), 404
    
    return app

app = create_app()

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    logger.info(f"Starting application on port {port}")
    app.run(host='0.0.0.0', port=port, debug=False)
else:
    # For gunicorn
    gunicorn_logger = logging.getLogger('gunicorn.error')
    app.logger.handlers = gunicorn_logger.handlers
    app.logger.setLevel(gunicorn_logger.level)
    logger.info("Application initialized for gunicorn")
