# Python Webapp Dashboard

A financial dashboard web application built with Flask and Plaid API integration.

## Features

- User authentication (login/register)
- Bank account linking via Plaid
- Transaction tracking and categorization
- Investment portfolio overview
- Financial analytics and insights

## Local Development

1. Clone the repository:
   ```bash
   git clone https://github.com/noblesavagetech/python-webapp-dashboard.git
   cd python-webapp-dashboard
   ```

2. Create a virtual environment:
   ```bash
   python -m venv venv
   source venv/bin/activate  # On Windows: venv\Scripts\activate
   ```

3. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```

4. Set up environment variables (create `.env` file):
   ```
   SECRET_KEY=your-secret-key
   PLAID_CLIENT_ID=your-plaid-client-id
   PLAID_SECRET=your-plaid-secret
   PLAID_ENV=sandbox
   DATABASE_URL=sqlite:///financial_dashboard.db
   ```

5. Run the application:
   ```bash
   python run.py
   ```

## Deploy to Railway

### One-Click Deploy

[![Deploy on Railway](https://railway.app/button.svg)](https://railway.app/template/python-webapp-dashboard)

### Manual Deployment

1. Install Railway CLI:
   ```bash
   npm install -g @railway/cli
   ```

2. Login to Railway:
   ```bash
   railway login
   ```

3. Initialize and deploy:
   ```bash
   railway init
   railway up
   ```

4. Add a PostgreSQL database:
   - Go to your Railway project dashboard
   - Click "New" → "Database" → "PostgreSQL"
   - Railway will automatically set the `DATABASE_URL` environment variable

5. Set environment variables in Railway dashboard:
   - `SECRET_KEY` - A secure random string
   - `PLAID_CLIENT_ID` - Your Plaid client ID
   - `PLAID_SECRET` - Your Plaid secret key
   - `PLAID_ENV` - `sandbox`, `development`, or `production`

6. Your app will be live at `https://your-app.railway.app`

## Environment Variables

| Variable | Description | Required |
|----------|-------------|----------|
| `SECRET_KEY` | Flask secret key for sessions | Yes |
| `DATABASE_URL` | PostgreSQL connection URL | Yes (auto-set by Railway) |
| `PLAID_CLIENT_ID` | Plaid API client ID | Yes |
| `PLAID_SECRET` | Plaid API secret | Yes |
| `PLAID_ENV` | Plaid environment (sandbox/development/production) | No (defaults to sandbox) |

## Tech Stack

- **Backend**: Flask, SQLAlchemy, Flask-Login
- **Database**: PostgreSQL (production), SQLite (development)
- **API Integration**: Plaid
- **Deployment**: Railway, Docker