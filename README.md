# Chennai Chat Assistant - Deployment Ready

This repository contains a web application that allows users to chat with a Chennai-based assistant character powered by the Grok API. The application includes user authentication, chat functionality, task management, and an admin dashboard.

## Features

- User authentication (signup/login)
- Chat with a tough Chennai-based assistant character
- Task assignment and tracking
- Admin dashboard for user management
- System prompt customization
- Dark-themed UI

## Technical Stack

- **Backend**: Flask
- **Database**: PostgreSQL
- **API**: Grok API for chat responses
- **Frontend**: HTML, CSS, JavaScript

## Deployment

This application is configured for deployment on Render. See [DEPLOYMENT.md](DEPLOYMENT.md) for detailed instructions.

## Environment Variables

The following environment variables need to be configured:

- `SECRET_KEY`: A secure random string for Flask sessions
- `GROK_API_KEY`: Your Grok API key
- `DB_USERNAME`: PostgreSQL database username
- `DB_PASSWORD`: PostgreSQL database password
- `DB_HOST`: PostgreSQL database host
- `DB_PORT`: PostgreSQL database port (typically 5432)
- `DB_NAME`: PostgreSQL database name

## Admin Access

After deployment, an admin user is automatically created with:
- Email: admin@example.com
- Password: admin123

It's recommended to change this password after the first login.

## Local Development

1. Clone the repository
2. Create a virtual environment: `python -m venv venv`
3. Activate the virtual environment:
   - Windows: `venv\Scripts\activate`
   - macOS/Linux: `source venv/bin/activate`
4. Install dependencies: `pip install -r requirements.txt`
5. Set up environment variables
6. Run the application: `python -m src.main`

## License

This project is proprietary and confidential.
