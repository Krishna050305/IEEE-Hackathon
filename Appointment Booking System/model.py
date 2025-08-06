from flask_sqlalchemy import SQLAlchemy
from datetime import time
from sqlalchemy import Time, Column

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
    specialization = db.Column(db.String(100))
    doctor_phone = db.Column(db.Integer, primary_key = True)
    opening_hours = db.Column(Time)
    closing_hours = db.Column(Time)
    email = db.Column(db.String(120), unique=True, nullable=False)
    password = db.Column(db.String(200))

class Clients(db.Model):
    clinic = db.Column(db.String(100))
    address = db.Column(db.String(500))
    






