def register_blueprints(app):
    from backend.routes.home import home_bp
    from backend.routes.contact import contact_bp
    from backend.routes.marketing_solutions import marketing_solutions_bp
    from backend.routes.trading_suite import trading_suite_bp
    
    app.register_blueprint(home_bp)
    app.register_blueprint(contact_bp)
    app.register_blueprint(marketing_solutions_bp)
    app.register_blueprint(trading_suite_bp)
    
    # TODO: Add remaining blueprint after migration:
    # from backend.routes.blog import blog_bp
    # app.register_blueprint(blog_bp)
