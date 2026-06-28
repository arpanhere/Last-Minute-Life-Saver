"""
App factory for The Last-Minute Life Saver.
"""
import os

from flask import Flask
from flask_login import LoginManager

from .models import User, db

login_manager = LoginManager()
login_manager.login_view = "auth.login"
login_manager.login_message_category = "info"


def create_app():
    app = Flask(__name__)
    app.config["SECRET_KEY"] = os.environ.get("SECRET_KEY", "dev-secret-change-me")

    basedir = os.path.abspath(os.path.dirname(os.path.dirname(__file__)))
    db_path = os.path.join(basedir, "lifesaver.sqlite3")
    app.config["SQLALCHEMY_DATABASE_URI"] = "sqlite:///" + db_path
    app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False

    db.init_app(app)
    login_manager.init_app(app)

    @login_manager.user_loader
    def load_user(user_id):
        return db.session.get(User, int(user_id))

    from .auth import auth_bp
    from .tasks import tasks_bp
    from .habits import habits_bp
    from .api import api_bp

    app.register_blueprint(auth_bp)
    app.register_blueprint(tasks_bp)
    app.register_blueprint(habits_bp)
    app.register_blueprint(api_bp, url_prefix="/api")

    from . import ai_engine

    @app.context_processor
    def inject_globals():
        return {"ai_configured": ai_engine.ai_is_configured()}

    with app.app_context():
        db.create_all()

    return app
