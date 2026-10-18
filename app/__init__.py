from flask import Flask

def create_app():
    app = Flask(__name__)
    app.config.from_mapping(SECRET_KEY='development-only')
    from app.routes import bp
    app.register_blueprint(bp)
    return app
