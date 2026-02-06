def register_blueprints(app):
    from backend.routes.home import home_bp
    from backend.routes.contact import contact_bp
    from backend.routes.about import about_bp
    from backend.routes.research import research_bp

    # Tools blueprints (all in backend.routes.tools package)
    from backend.routes.tools import tools_bp
    from backend.routes.tools.reply_assistant import reply_assistant_bp, limiter
    from backend.routes.tools.crypto_prices import crypto_prices_bp
    from backend.routes.tools.polymarket_monitor import polymarket_monitor_bp

    app.register_blueprint(home_bp)
    app.register_blueprint(contact_bp)
    app.register_blueprint(about_bp)
    app.register_blueprint(tools_bp)
    app.register_blueprint(research_bp)
    app.register_blueprint(reply_assistant_bp)
    app.register_blueprint(crypto_prices_bp)
    app.register_blueprint(polymarket_monitor_bp)

    # Initialize rate limiter with the Flask app
    limiter.init_app(app)
