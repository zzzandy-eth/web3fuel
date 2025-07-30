from flask import Flask
from backend.routes import register_blueprints

def create_app():
    app = Flask(__name__, 
                template_folder='../frontend/templates',
                static_folder='../frontend/static')
    
    # Register all blueprints
    register_blueprints(app)
    
    return app

if __name__ == '__main__':
    app = create_app()
    app.run(debug=True)
