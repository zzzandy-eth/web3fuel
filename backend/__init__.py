import os
from flask import Flask
from dotenv import load_dotenv
from backend.routes import register_blueprints

# Load environment variables from .env file
load_dotenv()

def create_app():
    app = Flask(__name__,
                template_folder='../frontend/templates',
                static_folder='../frontend/static')

    # Configure Flask app
    app.config['SECRET_KEY'] = os.getenv('FLASK_SECRET_KEY')
    app.config['ENV'] = os.getenv('FLASK_ENV', 'production')
    app.config['DEBUG'] = os.getenv('FLASK_DEBUG', 'False').lower() == 'true'

    # Register all blueprints
    register_blueprints(app)

    return app

if __name__ == '__main__':
    app = create_app()
    app.run(debug=True)
