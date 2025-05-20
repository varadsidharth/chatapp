# Chennai Chat Assistant - Deployment Guide

## Overview
This document provides instructions for deploying the Chennai Chat Assistant on Render.

## Application Structure
- Flask web application with MySQL database
- User authentication system
- Chat functionality powered by Grok API
- Task management system
- Admin dashboard

## Deployment Steps on Render

### 1. Create a MySQL Database
- Sign up for a MySQL database service on Render or use an external MySQL provider
- Create a new database named `mydb` (or your preferred name)
- Note down the database credentials (host, port, username, password)

### 2. Deploy the Web Service
- Log in to your Render account
- Click "New" and select "Web Service"
- Connect your GitHub/GitLab repository or upload the code directly
- Configure the service:
  - Name: chennai-chat-assistant
  - Runtime: Python 3
  - Build Command: `pip install -r requirements.txt`
  - Start Command: `gunicorn src.main:app`
  - Instance Type: Select appropriate plan based on your needs

### 3. Set Environment Variables
Navigate to the "Environment" tab and add the following variables:
- `SECRET_KEY`: Generate a secure random string (e.g., `python -c "import secrets; print(secrets.token_hex(24))"`)
- `GROK_API_KEY`: Your Grok API key
- `DB_USERNAME`: MySQL database username
- `DB_PASSWORD`: MySQL database password
- `DB_HOST`: MySQL database host
- `DB_PORT`: MySQL database port (usually 3306)
- `DB_NAME`: Database name (e.g., mydb)

### 4. Deploy and Monitor
- Click "Create Web Service" to deploy
- Monitor the deployment logs for any errors
- Once deployed, the app will be available at the provided Render URL

### 5. First-time Setup
- Access the application using the provided URL
- Log in with the default admin credentials:
  - Email: admin@example.com
  - Password: admin123
- Change the admin password immediately for security

## Troubleshooting
- If the application fails to connect to the database, verify the database credentials in environment variables
- If Grok API responses fail, check the API key and ensure it's valid
- For other issues, check the application logs in the Render dashboard

## Security Notes
- The default admin credentials should be changed immediately after deployment
- All sensitive information is stored in environment variables
- Regular backups of the database are recommended
