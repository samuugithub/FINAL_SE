from flask_sqlalchemy import SQLAlchemy
from os import getenv
from dotenv import load_dotenv

load_dotenv()

db = SQLAlchemy()

def init_db(app):
    """Initialize the database with the Flask app"""
    app.config['SQLALCHEMY_DATABASE_URI'] = getenv(
        'DATABASE_URL',
        'mysql+mysqlconnector://cpumetric_user:StrongPassword123@192.168.0.130/CPUMETRIC'
    )

    app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

    db.init_app(app)

    with app.app_context():
        db.create_all()
    print("✅ Database initialized and connected.")
