from fastapi import FastAPI, Request, Form, status
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from starlette.middleware.sessions import SessionMiddleware
from passlib.hash import bcrypt
from pymongo import MongoClient
from bson import ObjectId

app = FastAPI()
app.add_middleware(SessionMiddleware, secret_key="your-very-secret-key")

# MongoDB Setup
conn = MongoClient("mongodb+srv://apoorvmk457:apoorv.m.k@apoorv.bicllhf.mongodb.net/")
db = conn["AppointmentBooking"]
patient_collection = db["Patients"]
doctor_collection = db["Doctors"]


# Templates
templates = Jinja2Templates(directory="templates")
app.mount("/static", StaticFiles(directory="static"), name="static")


# Homepage with Role Selection
@app.get("/", response_class=HTMLResponse)
async def home(request: Request):
    user_id = request.session.get("user")
    role = request.session.get("role")
    user_name = None

    if user_id:
        if role == "patient":
            user = db["Patients"].find_one({"_id": ObjectId(user_id)})
            user_name = user["full_name"] if user else None
        elif role == "doctor":
            doctor = db["Doctors"].find_one({"_id": ObjectId(user_id)})
            user_name = doctor["full_name"] if doctor else None

    return templates.TemplateResponse("index.html", {
        "request": request,
        "user_name": user_name,
        "role": role
    })

@app.get("/auth", response_class=HTMLResponse)
async def choose_role(request: Request):
    return templates.TemplateResponse("select_role.html", {"request": request})

@app.get("/patient/register", response_class=HTMLResponse)
async def get_patient_register(request: Request):
    return templates.TemplateResponse("patient/register.html", {"request": request})

@app.post("/patient/register", response_class=HTMLResponse)
async def post_patient_register(
        request: Request,
        full_name: str = Form(...),
        email: str = Form(...),
        phone_number: str = Form(...),
        password: str = Form(...),
        age: int = Form(...),
        gender: str = Form(...),
        address: str = Form(...)
):
    if patient_collection.find_one({"email": email}):
        return templates.TemplateResponse("patient/register.html",
                                          {"request": request, "error": "Email already registered"})

    patient_collection.insert_one({
        "full_name": full_name,
        "email": email,
        "phone_number": phone_number,
        "password": bcrypt.hash(password),
        "age": age,
        "gender": gender,
        "address": address
    })
    return RedirectResponse("/patient/login", status_code=status.HTTP_302_FOUND)

@app.get("/patient/login", response_class=HTMLResponse)
async def get_patient_login(request: Request):
    return templates.TemplateResponse("patient/login.html", {"request": request})

@app.post("/patient/login", response_class=HTMLResponse)
async def post_patient_login(
        request: Request,
        email: str = Form(...),
        password: str = Form(...)
):
    user = patient_collection.find_one({"email": email})
    if not user or not bcrypt.verify(password, user["password"]):
        return templates.TemplateResponse("patient/login.html", {"request": request, "error": "Invalid credentials"})

    request.session["user"] = str(user["_id"])
    request.session["role"] = "patient"
    request.session["user_name"] = user["full_name"]

    return RedirectResponse("/", status_code=302)

@app.get("/patient/dashboard", response_class=HTMLResponse)
async def patient_dashboard(request: Request):
    if request.session.get("role") != "patient":
        return RedirectResponse("/", status_code=status.HTTP_302_FOUND)

    patient_id = request.session.get("user")
    if not patient_id:
        return RedirectResponse("/login", status_code=status.HTTP_302_FOUND)

    appointments = list(db["Appointments"].find({"patient_id": ObjectId(patient_id)}))

    for appt in appointments:
        doctor = db["Doctors"].find_one({"_id": appt["doctor_id"]})
        clinic = db["Clinics"].find_one({"_id": appt["clinic_id"]})

        appt["doctor_name"] = doctor.get("full_name", "Unknown") if doctor else "Unknown"
        appt["clinic_name"] = clinic["name"] if clinic else "Unknown"
        appt["clinic_location"] = clinic["location"] if clinic else "Unknown"

    return templates.TemplateResponse("patient/dashboard.html", {
        "request": request,
        "appointments": appointments
    })

# Logout
@app.get("/doctor/register", response_class=HTMLResponse)
async def get_doctor_register(request: Request):
    return templates.TemplateResponse("doctor/register.html", {"request": request})


@app.post("/doctor/register", response_class=HTMLResponse)
async def post_doctor_register(
        request: Request,
        full_name: str = Form(...),
        email: str = Form(...),
        specialization: str = Form(...),
        clinic: str = Form(...),
        password: str = Form(...)
):
    if doctor_collection.find_one({"email": email}):
        return templates.TemplateResponse("doctor/register.html",
                                          {"request": request, "error": "Email already registered"})

    doctor_collection.insert_one({
        "full_name": full_name,
        "email": email,
        "specialization": specialization,
        "clinic": clinic,
        "password": bcrypt.hash(password)
    })
    return RedirectResponse("/doctor/login", status_code=status.HTTP_302_FOUND)


@app.get("/doctor/login", response_class=HTMLResponse)
async def get_doctor_login(request: Request):
    return templates.TemplateResponse("doctor/login.html", {"request": request})


@app.post("/doctor/login", response_class=HTMLResponse)
async def post_doctor_login(
        request: Request,
        email: str = Form(...),
        password: str = Form(...)
):
    doctor = doctor_collection.find_one({"email": email})
    if not doctor or not bcrypt.verify(password, doctor["password"]):
        return templates.TemplateResponse("doctor/login.html", {"request": request, "error": "Invalid credentials"})

    request.session["user"] = str(doctor["_id"])
    request.session["role"] = "doctor"
    request.session["user_name"] = doctor["full_name"]

    return RedirectResponse("/", status_code=302)



@app.get("/doctor/dashboard", response_class=HTMLResponse)
async def doctor_dashboard(request: Request):
    doctor_id = request.session.get("user")
    if not doctor_id or request.session.get("role") != "doctor":
        return RedirectResponse("/login", status_code=status.HTTP_302_FOUND)

    appointments = list(db["Appointments"].find({"doctor_id": ObjectId(doctor_id)}))
    for appt in appointments:
        patient = db["Patients"].find_one({"_id": appt["patient_id"]})
        clinic = db["Clinics"].find_one({"_id": appt["clinic_id"]})
        appt["patient_name"] = patient["full_name"] if patient else "Unknown"
        appt["clinic_name"] = clinic["name"] if clinic else "Unknown"
        appt["clinic_location"] = clinic["location"] if clinic else "Unknown"

    return templates.TemplateResponse("doctor/dashboard.html", {
        "request": request,
        "appointments": appointments
    })


@app.get("/logout")
async def logout(request: Request):
    request.session.clear()
    return RedirectResponse("/", status_code=status.HTTP_302_FOUND)


@app.get("/Cardiology", response_class=HTMLResponse)
async def cardiology_page(request: Request):
    user_name = request.session.get("user_name")
    role = request.session.get("role")
    return templates.TemplateResponse("cardio.html", {
        "request": request,
        "user_name": user_name,
        "role": role
    })

@app.get("/Gynecology", response_class=HTMLResponse)
async def gynecology_page(request: Request):
    user_name = request.session.get("user_name")
    role = request.session.get("role")
    return templates.TemplateResponse("gyneaco.html", {
        "request": request,
        "user_name": user_name,
        "role": role
    })

@app.get("/Dental", response_class=HTMLResponse)
async def gynecology_page(request: Request):
    user_name = request.session.get("user_name")
    role = request.session.get("role")
    return templates.TemplateResponse("dental.html", {
        "request": request,
        "user_name": user_name,
        "role": role
    })

@app.get("/Neurology", response_class=HTMLResponse)
async def gynecology_page(request: Request):
    user_name = request.session.get("user_name")
    role = request.session.get("role")
    return templates.TemplateResponse("neurology.html", {
        "request": request,
        "user_name": user_name,
        "role": role
    })

@app.get("/Orthopedic", response_class=HTMLResponse)
async def gynecology_page(request: Request):
    user_name = request.session.get("user_name")
    role = request.session.get("role")
    return templates.TemplateResponse("ortho.html", {
        "request": request,
        "user_name": user_name,
        "role": role
    })

@app.get("/Pediatrician", response_class=HTMLResponse)
async def gynecology_page(request: Request):
    user_name = request.session.get("user_name")
    role = request.session.get("role")
    return templates.TemplateResponse("pediatrics.html", {
        "request": request,
        "user_name": user_name,
        "role": role
    })

@app.get("/Psychiatrist", response_class=HTMLResponse)
async def gynecology_page(request: Request):
    user_name = request.session.get("user_name")
    role = request.session.get("role")
    return templates.TemplateResponse("psychiatry.html", {
        "request": request,
        "user_name": user_name,
        "role": role
    })


# Show doctors by specialization
@app.get("/specialty/{specialization}", response_class=HTMLResponse)
async def show_specialty_page(request: Request, specialization: str):
    doctors = list(db["Doctors"].find({"specialization": specialization.capitalize()}))

    for doc in doctors:
        clinic = db["Clinics"].find_one({"_id": doc["clinic_id"]})
        doc["clinic_name"] = clinic["name"] if clinic else "Unknown"
        doc["clinic_location"] = clinic["location"] if clinic else "Unknown"

    return templates.TemplateResponse("specialty/choose_doctor.html", {
        "request": request,
        "specialization": specialization.capitalize(),
        "doctors": doctors
    })


# Booking page for specific doctor
@app.get("/book/{doctor_id}", response_class=HTMLResponse)
async def show_booking_page(request: Request, doctor_id: str):
    patient_id = request.session.get("user")
    if not patient_id:
        return RedirectResponse("/auth", status_code=status.HTTP_302_FOUND)

    doctor = db["Doctors"].find_one({"_id": ObjectId(doctor_id)})
    clinic = db["Clinics"].find_one({"_id": doctor["clinic_id"]})

    all_slots = [
        "10:00 AM", "10:30 AM", "11:00 AM", "11:30 AM",
        "12:00 PM", "12:30 PM", "2:00 PM", "2:30 PM"
    ]
    booked = db["Appointments"].find({"doctor_id": ObjectId(doctor_id)})
    booked_slots = [appt["slot"] for appt in booked]
    available_slots = [slot for slot in all_slots if slot not in booked_slots]

    return templates.TemplateResponse("book/appointment.html", {
        "request": request,
        "doctor": doctor,
        "clinic": clinic,
        "available_slots": available_slots
    })


# Confirm booking
@app.post("/book/{doctor_id}", response_class=HTMLResponse)
async def confirm_booking(request: Request, doctor_id: str, slot: str = Form(...)):
    patient_id = request.session.get("user")
    if not patient_id:
        return RedirectResponse("/auth", status_code=status.HTTP_302_FOUND)

    existing = db["Appointments"].find_one({
        "doctor_id": ObjectId(doctor_id),
        "slot": slot
    })
    if existing:
        return HTMLResponse(content="Slot already booked. Please go back and pick another.", status_code=400)

    doctor = db["Doctors"].find_one({"_id": ObjectId(doctor_id)})

    db["Appointments"].insert_one({
        "doctor_id": ObjectId(doctor_id),
        "clinic_id": doctor["clinic_id"],
        "patient_id": ObjectId(patient_id),
        "slot": slot
    })

    return RedirectResponse("/dashboard", status_code=status.HTTP_302_FOUND)














