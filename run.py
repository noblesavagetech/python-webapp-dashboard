#!/usr/bin/env python3
# run.py

import os
from dotenv import load_dotenv
load_dotenv()

from app import create_app

# Use production config if RAILWAY_ENVIRONMENT is set
config_name = 'production' if os.environ.get('RAILWAY_ENVIRONMENT') else 'development'
app = create_app(config_name)

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    debug = not os.environ.get('RAILWAY_ENVIRONMENT')
    app.run(host='0.0.0.0', port=port, debug=debug)
