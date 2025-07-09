import sys
import os

# Add your application directory to the Python path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# Import the Flask application
from routes.home import app

# For Gunicorn
application = app

if __name__ == "__main__":
    app.run()