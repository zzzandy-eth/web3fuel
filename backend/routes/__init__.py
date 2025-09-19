def register_blueprints(app):
    from backend.routes.home import home_bp
    from backend.routes.contact import contact_bp
    from backend.routes.research import research_bp
    from backend.routes.trading_suite import trading_suite_bp
    from backend.routes.blog import blog_bp
    
    app.register_blueprint(home_bp)
    app.register_blueprint(contact_bp)
    app.register_blueprint(research_bp)
    app.register_blueprint(trading_suite_bp)
    app.register_blueprint(blog_bp)
