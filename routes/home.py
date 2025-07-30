from flask import Flask, render_template
import sys
import os

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from routes.blog import blog_bp
from routes.contact import contact_bp
from routes.trading_suite import trading_suite_bp
from routes.marketing_solutions import marketing_solutions_bp

app = Flask(__name__, template_folder='../frontend/templates', static_folder='../frontend/static')

# Register blueprints
app.register_blueprint(blog_bp)
app.register_blueprint(contact_bp)
app.register_blueprint(trading_suite_bp)
app.register_blueprint(marketing_solutions_bp)
@app.route('/')
def home():
    return render_template('index.html')

if __name__ == '__main__':
    app.run(debug=True)