import os
from flask import Flask, request
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

    # Set cache headers for static files (1 week for returning visitors)
    @app.after_request
    def add_cache_headers(response):
        if request.path.startswith('/static/'):
            # Cache static files for 1 week (604800 seconds)
            response.headers['Cache-Control'] = 'public, max-age=604800'
        return response

    # Register all blueprints
    register_blueprints(app)

    return app

if __name__ == '__main__':
    app = create_app()
    app.run(debug=True)
