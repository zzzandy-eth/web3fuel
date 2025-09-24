import sys
import os

# Add your application directory to the Python path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# Import the Flask application
from backend import create_app

# Create the Flask application instance
application = create_app()

if __name__ == "__main__":
    application.run()