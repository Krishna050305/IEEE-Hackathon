from flask_sqlalchemy import SQLAlchemy

db = SQLAlchemy()

class Patient(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    full_name = db.Column(db.String(100))
    email = db.Column(db.String(120), unique=True, nullable=False)
    phone_number = db.Column(db.String(15))
    password = db.Column(db.String(200))
    age = db.Column(db.Integer)
    gender = db.Column(db.String(10))
    address = db.Column(db.String(200))

class Doctor(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    full_name = db.Column(db.String(100))
    email = db.Column(db.String(120), unique=True, nullable=False)
    specialization = db.Column(db.String(100))
    clinic = db.Column(db.String(100))
    password = db.Column(db.String(200))





