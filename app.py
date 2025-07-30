from flask import Flask, render_template, request, redirect, url_for, session, flash
from werkzeug.security import generate_password_hash, check_password_hash
from model import db, Patient, Doctor

app = Flask(__name__)
app.secret_key = "secret-key"
app.config["SQLALCHEMY_DATABASE_URI"] = "sqlite:///users.db"
db.init_app(app)

with app.app_context():
    db.create_all()

@app.route('/')
def index():
    role = session.get('role')
    user_obj = None
    if role == 'patient':
        user_obj = Patient.query.get(session['user_id'])
        return render_template('index.html', user=user_obj)
    elif role == 'doctor':
        user_obj = Doctor.query.get(session['user_id'])
        return render_template('index.html', doctor=user_obj)
    return render_template('index.html')

# Patient Routes
@app.route('/patient/register', methods=['GET', 'POST'])
def patient_register():
    if request.method == 'POST':
        email = request.form['email']
        if Patient.query.filter_by(email=email).first():
            flash("Email already exists")
            return redirect(url_for('patient_register'))
        user = Patient(
            full_name=request.form['full_name'],
            email=email,
            phone_number=request.form['phone_number'],
            password=generate_password_hash(request.form['password']),
            age=request.form['age'],
            gender=request.form['gender'],
            address=request.form['address']
        )
        db.session.add(user)
        db.session.commit()
        return redirect(url_for('patient_login'))
    return render_template('patient/register.html')

@app.route('/patient/login', methods=['GET', 'POST'])
def patient_login():
    if request.method == 'POST':
        email = request.form['email']
        user = Patient.query.filter_by(email=email).first()
        if user and check_password_hash(user.password, request.form['password']):
            session['user_id'] = user.id
            session['role'] = 'patient'
            return redirect(url_for('patient_dashboard'))
        flash("Invalid credentials")
    return render_template('patient/login.html')

@app.route('/patient/dashboard')
def patient_dashboard():
    if session.get('role') != 'patient':
        return redirect(url_for('index'))
    user = Patient.query.get(session['user_id'])
    return render_template('patient/dashboard.html', user=user)

# Doctor Routes
@app.route('/doctor/register', methods=['GET', 'POST'])
def doctor_register():
    if request.method == 'POST':
        email = request.form['email']
        if Doctor.query.filter_by(email=email).first():
            flash("Email already exists")
            return redirect(url_for('doctor_register'))
        doctor = Doctor(
            full_name=request.form['full_name'],
            email=email,
            specialization=request.form['specialization'],
            clinic=request.form['clinic'],
            password=generate_password_hash(request.form['password'])
        )
        db.session.add(doctor)
        db.session.commit()
        return redirect(url_for('doctor_login'))
    return render_template('doctor/register.html')

@app.route('/doctor/login', methods=['GET', 'POST'])
def doctor_login():
    if request.method == 'POST':
        email = request.form['email']
        doctor = Doctor.query.filter_by(email=email).first()
        if doctor and check_password_hash(doctor.password, request.form['password']):
            session['user_id'] = doctor.id
            session['role'] = 'doctor'
            return redirect(url_for('doctor_dashboard'))
        flash("Invalid credentials")
    return render_template('doctor/login.html')

@app.route('/doctor/dashboard')
def doctor_dashboard():
    if session.get('role') != 'doctor':
        return redirect(url_for('index'))
    doctor = Doctor.query.get(session['user_id'])
    return render_template('doctor/dashboard.html', doctor=doctor)

@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('index'))

@app.context_processor
def inject_user():
    user_id = session.get('user_id')
    role = session.get('role')
    if user_id and role == 'patient':
        user = Patient.query.get(user_id)
        return dict(user=user)
    elif user_id and role == 'doctor':
        doctor = Doctor.query.get(user_id)
        return dict(doctor=doctor)
    return dict()


if __name__ == '__main__':
    app.run(debug=True)

