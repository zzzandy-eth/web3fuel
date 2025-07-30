from flask import Flask, render_template, Blueprint

# Create blueprint for contact page
contact_bp = Blueprint('contact', __name__, url_prefix='/contact', 
                      template_folder='../frontend/templates', 
                      static_folder='../frontend/static')
@contact_bp.route('/')
def contact():
    return render_template('contact.html')

# For standalone testing
if __name__ == '__main__':
    app = Flask(__name__)
    app.register_blueprint(contact_bp)
    app.run(debug=True)