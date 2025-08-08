from fastapi import FastAPI, Request, Form, status, Query, Depends
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from starlette.middleware.sessions import SessionMiddleware
from passlib.hash import bcrypt
from passlib.context import CryptContext
from pymongo import MongoClient
from bson import ObjectId
from datetime import datetime


app = FastAPI()
app.add_middleware(SessionMiddleware, secret_key="your-very-secret-key")

# MongoDB Setup
conn = MongoClient("mongodb+srv://apoorvmk457:apoorv.m.k@apoorv.bicllhf.mongodb.net/")
db = conn["ApoointmentBooking"]
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
    user_id = request.session.get("user")
    role = request.session.get("role")

    if user_id and role:
        # Already logged in, redirect to appropriate dashboard
        if role == "patient":
            return RedirectResponse("/patient/dashboard", status_code=302)
        elif role == "doctor":
            return RedirectResponse("/doctor/dashboard", status_code=302)
    else:
        return RedirectResponse("/", status_code=302)
    

    # If not logged in, show role selection page
    return templates.TemplateResponse("select_role.html", {"request": request})


@app.post("/auth", response_class=HTMLResponse)
async def login_user(request: Request, email: str = Form(...), password: str = Form(...)):
    user = db["Users"].find_one({"email": email})

    if not user or user["password"] != password:
        return HTMLResponse("Invalid credentials", status_code=401)

    request.session["user"] = str(user["_id"])       # store user ID
    request.session["role"] = user["role"]           # store "doctor" or "patient"

    # redirect based on role
    if user["role"] == "doctor":
        return RedirectResponse("/doctor/dashboard", status_code=302)
    else:
        return RedirectResponse("/patient/dashboard", status_code=302)

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
async def patient_dashboard(
    request: Request,
    action: str = None,
    date: str = None,
    slot: str = None
):
    patient_id = request.session.get("user")
    if not patient_id:
        return RedirectResponse("/auth", status_code=status.HTTP_302_FOUND)

    patient = db["Patients"].find_one({"_id": ObjectId(patient_id)})

    appointments = list(db["Appointments"].find({"patient_id": ObjectId(patient_id)}))
    for appt in appointments:
        doctor = db["Doctors"].find_one({"_id": appt["doctor_id"]})
        clinic = db["Clinics"].find_one({"_id": appt["clinic_id"]})

        appt["doctor_name"] = doctor.get("full_name", "Unknown") if doctor else "Unknown"
        appt["specialization"] = doctor.get("specialization", "N/A") if doctor else "N/A"
        appt["clinic_name"] = clinic["name"] if clinic else "Unknown"
        appt["clinic_address"] = clinic["address"] if clinic else "Unknown"

    return templates.TemplateResponse("patient/dashboard.html", {
        "request": request,
        "appointments": appointments,
        "action": action,
        "date": date,
        "slot": slot
    })


# Logout
@app.get("/doctor/register", response_class=HTMLResponse)
async def get_doctor_register(request: Request):
    clinics = list(db["Clinics"].find({}))
    return templates.TemplateResponse("doctor/register.html", {
        "request": request,
        "clinics": clinics
    })



@app.post("/doctor/register", response_class=HTMLResponse)
async def post_doctor_register(
    request: Request,
    full_name: str = Form(...),
    email: str = Form(...),
    specialization: str = Form(...),
    clinic: str = Form(...),  # clinic is _id in string format
    password: str = Form(...)
):
    clinic_obj_id = ObjectId(clinic)

    # Check if doctor already exists based on name + specialization + clinic
    existing_doctor = doctor_collection.find_one({
        "full_name": full_name,
        "specialization": specialization,
        "clinic_id": clinic_obj_id
    })

    if existing_doctor:
        # Update email and password
        doctor_collection.update_one(
            {"_id": existing_doctor["_id"]},
            {
                "$set": {
                    "email": email,
                    "password": bcrypt.hash(password)
                }
            }
        )
    else:
        # Insert new doctor
        doctor_collection.insert_one({
            "full_name": full_name,
            "email": email,
            "specialization": specialization,
            "clinic_id": clinic_obj_id,
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
    if not doctor_id:
        return RedirectResponse("/doctor/login", status_code=302)

    try:
        doctor_obj_id = ObjectId(doctor_id)
    except:
        return HTMLResponse("Invalid doctor ID", status_code=400)

    appointments = list(db["Appointments"].find({"doctor_id": doctor_obj_id}))

    patient_data = []
    for appt in appointments:
        patient = db["Patients"].find_one({"_id": appt["patient_id"]})
        if not patient:
            continue
        patient_data.append({
            "name": patient.get("full_name", "Unknown"),
            "email": patient.get("email", "Unknown"),
            "date": appt["date"],
            "slot": appt["slot"],
            "age": patient.get("age", "N/A"),
            "phone": patient.get("phone_number", "N/A"),
            "appointment_id": str(appt["_id"])
        })

    doctor = db["Doctors"].find_one({"_id": doctor_obj_id})

    return templates.TemplateResponse("doctor/dashboard.html", {
        "request": request,
        "doctor": doctor,
        "patients": patient_data
    })
    
@app.get("/logout")
async def logout(request: Request):
    request.session.clear()
    return RedirectResponse("/", status_code=302)


@app.get("/Cardiology", response_class=HTMLResponse)
async def cardiology_page(request: Request):
    user_name = request.session.get("user_name")
    role = request.session.get("role")
    return templates.TemplateResponse("cardio.html", {
        "request": request,
        "user_name": user_name,
        "role": role
    })
    
@app.get("/Dentist", response_class=HTMLResponse)
async def dentist_page(request: Request):
    user_name = request.session.get("user_name")
    role = request.session.get("role")
    return templates.TemplateResponse("dental.html", {
        "request": request,
        "user_name": user_name,
        "role": role
    })
    
@app.get("/Gynecology", response_class=HTMLResponse)
async def gynecologist_page(request: Request):
    user_name = request.session.get("user_name")
    role = request.session.get("role")
    return templates.TemplateResponse("gyneaco.html", {
        "request": request,
        "user_name": user_name,
        "role": role
    })
    
@app.get("/Neurology", response_class=HTMLResponse)
async def gynecologist_page(request: Request):
    user_name = request.session.get("user_name")
    role = request.session.get("role")
    return templates.TemplateResponse("neurology.html", {
        "request": request,
        "user_name": user_name,
        "role": role
    })
    
@app.get("/Pediatrician", response_class=HTMLResponse)
async def pediatric_page(request: Request):
    user_name = request.session.get("user_name")
    role = request.session.get("role")
    return templates.TemplateResponse("pediatrics.html", {
        "request": request,
        "user_name": user_name,
        "role": role
    })
    
@app.get("/Psychiatrist", response_class=HTMLResponse)
async def pediatric_page(request: Request):
    user_name = request.session.get("user_name")
    role = request.session.get("role")
    return templates.TemplateResponse("psychiatry.html", {
        "request": request,
        "user_name": user_name,
        "role": role
    })
    
@app.get("/Orthopedic", response_class=HTMLResponse)
async def ortho_page(request: Request):
    user_name = request.session.get("user_name")
    role = request.session.get("role")
    return templates.TemplateResponse("ortho.html", {
        "request": request,
        "user_name": user_name,
        "role": role
    })

@app.get("/OurTeam", response_class=HTMLResponse)
async def our_team_page(request: Request):
    user_name = request.session.get("user_name")
    role = request.session.get("role")
    return templates.TemplateResponse("our_team.html", {
        "request": request,
        "user_name": user_name,
        "role": role
    })

@app.get("/AboutUs", response_class=HTMLResponse)
async def about_us_page(request: Request):
    user_name = request.session.get("user_name")
    role = request.session.get("role")
    return templates.TemplateResponse("about_us.html", {
        "request": request,
        "user_name": user_name,
        "role": role
    })

@app.get("/Blog", response_class=HTMLResponse)
async def blog_page(request: Request):
    user_name = request.session.get("user_name")
    role = request.session.get("role")
    return templates.TemplateResponse("blog.html", {
        "request": request,
        "user_name": user_name,
        "role": role
    })

# Show doctors by specialization
@app.get("/specialty/{specialization}", response_class=HTMLResponse)
async def show_specialty_page(request: Request, specialization: str, clinic_id: str = Query(None)):
    query = {"specialization": specialization.capitalize()}

    if clinic_id:
        try:
            query["clinic_id"] = ObjectId(clinic_id)
        except:
            pass

    doctors = list(db["Doctors"].find(query))

    for doc in doctors:
        clinic_id = doc.get("clinic_id")
        if not clinic_id:
            continue  

        clinic = db["Clinics"].find_one({"_id": clinic_id})

        doc["clinic_name"] = clinic["name"] if clinic else "Unknown"
        doc["clinic_address"] = clinic["address"] if clinic else "N/A"

    return templates.TemplateResponse("specialty/choose_doctor.html", {
        "request": request,
        "specialization": specialization.capitalize(),
        "doctors": doctors
    })

@app.get("/clinics/{specialization}", response_class=HTMLResponse)
async def show_specialty_page(request: Request, specialization: str, clinic_id: str = Query(None)):
    query = {"specialization": specialization.capitalize()}

    if clinic_id:
        try:
            query["clinic_id"] = ObjectId(clinic_id)
        except:
            pass

    doctors = db["Doctors"].find(query)

    doctor_list = []
    for doc in doctors:
        clinic_id = doc.get("clinic_id")
        if not clinic_id:
            continue 

        clinic = db["Clinics"].find_one({"_id": clinic_id})
        if not clinic:
            continue 

        doctor_list.append({
            "full_name": doc.get("full_name"),
            "specialization": doc.get("specialization"),
            "opening_hours": doc.get("opening_hours"),
            "closing_hours": doc.get("closing_hours"),
            "phone_number": doc.get("phone_number"),
            "_id": str(doc["_id"]),
            "clinic_name": clinic["name"],
            "clinic_address": clinic["address"]
        })

    return templates.TemplateResponse("specialty/choose_doctor.html", {
        "request": request,
        "specialization": specialization.capitalize(),
        "doctors": doctor_list
    })
    
    
# Booking page for specific doctor
@app.get("/book/{doctor_id}", response_class=HTMLResponse)
async def show_booking_page(
    request: Request,
    doctor_id: str,
    edit_id: str = Query(None),
    date: str = Query(None),
    slot: str = Query(None)
):
    patient_id = request.session.get("user")
    if not patient_id:
        return RedirectResponse("/auth", status_code=status.HTTP_302_FOUND)

    doctor = db["Doctors"].find_one({"_id": ObjectId(doctor_id)})
    clinic = db["Clinics"].find_one({"_id": doctor["clinic_id"]})
    today = datetime.now().strftime("%Y-%m-%d")

    all_slots = [
        "10:00 AM", "10:30 AM", "11:00 AM", "11:30 AM",
        "12:00 PM", "12:30 PM", "2:00 PM", "2:30 PM"
    ]

    booked = db["Appointments"].find({"doctor_id": ObjectId(doctor_id)})
    booked_slots = [f"{appt['date']}::{appt['slot']}" for appt in booked]

    return templates.TemplateResponse("book/appointment.html", {
        "request": request,
        "doctor": doctor,
        "clinic": clinic,
        "available_slots": all_slots,
        "today": today,
        "booked_slots": booked_slots,
        "edit": bool(edit_id),  # pass True if editing
        "edit_id": edit_id,
        "existing_date": date,
        "existing_slot": slot
    })

@app.post("/book/{doctor_id}", response_class=HTMLResponse)
async def submit_booking(
    request: Request,
    doctor_id: str,
    date: str = Form(...),
    slot: str = Form(...),
    edit_id: str = Form(None)
):
    # ✅ Get patient ID from session
    patient_id = request.session.get("user")
    if not patient_id:
        return RedirectResponse("/", status_code=302)

    # ✅ Get doctor
    doctor = db["Doctors"].find_one({"_id": ObjectId(doctor_id)})
    if not doctor:
        return HTMLResponse("Doctor not found", status_code=404)

    clinic_id = doctor.get("clinic_id")
    if not clinic_id:
        return HTMLResponse("Clinic not associated with this doctor", status_code=400)

    # ✅ Check for slot conflict
    query = {
        "doctor_id": ObjectId(doctor_id),
        "date": date,
        "slot": slot
    }

    if edit_id:
        query["_id"] = {"$ne": ObjectId(edit_id)}

    existing = db["Appointments"].find_one(query)
    if existing:
        return HTMLResponse(content="""
            <body style="
                margin: 0;
                padding: 0;
                background-image: url('/static/images/bg.png');
                background-size: cover;
                background-repeat: no-repeat;
                background-position: center;
                height: 100vh;
                display: flex;
                align-items: center;
                justify-content: center;
                font-family: 'Segoe UI', sans-serif;
            ">
            <div style=" 
                max-width: 600px;
                margin: 80px auto;
                padding: 40px;
                background-color: #fff0f0;
                border: 2px solid #ff4d4f;
                border-radius: 12px;
                box-shadow: 0 4px 10px rgba(0,0,0,0.1);
                text-align: center;
            ">
                <h2 style="color: #c0392b; margin-bottom: 20px;">❌ Slot Already Booked</h2>
                <p style="font-size: 16px; color: #444;">Please go back and choose a different time slot.</p>
                <a href="javascript:history.back()" style="
                    display: inline-block;
                    margin-top: 20px;
                    padding: 10px 20px;
                    background-color: #1eb8cd;
                    color: white;
                    text-decoration: none;
                    border-radius: 6px;
                    font-weight: bold;
                ">Go Back</a>
            </div>
        """, status_code=409)

    # ✅ Create appointment
    db["Appointments"].insert_one({
        "doctor_id": ObjectId(doctor_id),
        "clinic_id": clinic_id,
        "patient_id": ObjectId(patient_id),
        "slot": slot,
        "date": date
    })

    if edit_id:
        db["Appointments"].delete_one({"_id": ObjectId(edit_id)})

    action = "updated" if edit_id else "booked"
    return RedirectResponse(
        f"/patient/dashboard?action={action}&date={date}&slot={slot}",
        status_code=302
    )



@app.get("/confirmation", response_class=HTMLResponse)
async def appointment_confirmation(request: Request, slot: str, date: str, doctor_id: str):
    doctor = db["Doctors"].find_one({"_id": ObjectId(doctor_id)})
    clinic = db["Clinics"].find_one({"_id": doctor["clinic_id"]})

    return templates.TemplateResponse("confirmation.html", {
        "request": request,
        "doctor": doctor,
        "clinic": clinic,
        "slot": slot,
        "date": date
    })

@app.get("/appointment/edit/{appointment_id}", response_class=HTMLResponse)
async def edit_appointment(request: Request, appointment_id: str):
    appointment = db["Appointments"].find_one({"_id": ObjectId(appointment_id)})
    if not appointment:
        return HTMLResponse("Appointment not found", status_code=404)

    doctor = db["Doctors"].find_one({"_id": appointment["doctor_id"]})
    patient = db["Patients"].find_one({"_id": appointment["patient_id"]})
    today = datetime.now().strftime("%Y-%m-%d")

    is_doctor = request.session.get("role") == "doctor"
    template_name = "doctor_edit_appointment.html" if is_doctor else "appointment.html"

    return templates.TemplateResponse(template_name, {
        "request": request,
        "doctor": doctor,
        "patient": patient,
        "date": appointment["date"],
        "slot": appointment["slot"],
        "available_slots": [
            "10:00 AM", "10:30 AM", "11:00 AM", "11:30 AM",
            "12:00 PM", "12:30 PM", "2:00 PM", "2:30 PM"
        ],
        "today": today,
        "edit": True,
        "appointment_id": appointment_id
    })



@app.post("/appointment/edit/{appointment_id}")
async def update_appointment(
    request: Request,
    appointment_id: str,
    date: str = Form(...),
    slot: str = Form(...)
):
    # Fetch original appointment
    appointment = db["Appointments"].find_one({"_id": ObjectId(appointment_id)})
    if not appointment:
        return HTMLResponse("Appointment not found", status_code=404)

    doctor_id = appointment["doctor_id"]

    # Prevent slot conflicts (exclude this appointment ID)
    conflict = db["Appointments"].find_one({
        "doctor_id": doctor_id,
        "date": date,
        "slot": slot,
        "_id": {"$ne": ObjectId(appointment_id)}  # Exclude current one
    })

    if conflict:
        # Styled "Slot Already Booked" error page with bg.png
        return HTMLResponse(
            content="""
            <!DOCTYPE html>
            <html>
            <head><title>Slot Already Booked</title></head>
            <body style='
                margin: 0;
                padding: 0;
                background-image: url("/static/images/bg.png");
                background-size: cover;
                background-position: center;
                height: 100vh;
                display: flex;
                justify-content: center;
                align-items: center;
                font-family: "Segoe UI", sans-serif;
            '>
            <div style='
                max-width: 600px;
                padding: 40px;
                background-color: #fff0f0;
                border: 2px solid #ff4d4f;
                border-radius: 12px;
                text-align: center;
                box-shadow: 0 4px 10px rgba(0,0,0,0.1);
            '>
                <h2 style='color: #c0392b;'>❌ Slot Already Booked</h2>
                <p>Please go back and choose a different time slot.</p>
                <a href='javascript:history.back()' style='
                    padding: 10px 20px;
                    background-color: #1eb8cd;
                    color: white;
                    text-decoration: none;
                    border-radius: 6px;
                    font-weight: bold;
                '>Go Back</a>
            </div>
            </body>
            </html>
            """,
            status_code=409
        )

    # If no conflict, proceed with update
    db["Appointments"].update_one(
        {"_id": ObjectId(appointment_id)},
        {"$set": {"date": date, "slot": slot}}
    )

    role = request.session.get("role")

    if role == "doctor":
        return RedirectResponse("/doctor/dashboard", status_code=302)
    return RedirectResponse("/patient/dashboard", status_code=302)



@app.get("/appointment/delete/{appointment_id}")
async def delete_appointment(request: Request, appointment_id: str):
    role = request.session.get("role")
    user_id = request.session.get("user")

    if not user_id or not role:
        return RedirectResponse("/auth", status_code=302)

    appointment = db["Appointments"].find_one({"_id": ObjectId(appointment_id)})
    if not appointment:
        return HTMLResponse("Appointment not found", status_code=404)

    # Ensure patient can only delete their own appointments
    if role == "patient" and str(appointment["patient_id"]) != user_id:
        return HTMLResponse("Unauthorized", status_code=403)

    # Ensure doctor can only delete their own appointments
    if role == "doctor" and str(appointment["doctor_id"]) != user_id:
        return HTMLResponse("Unauthorized", status_code=403)

    db["Appointments"].delete_one({"_id": ObjectId(appointment_id)})

    # Redirect to appropriate dashboard
    if role == "doctor":
        return RedirectResponse("/doctor/dashboard", status_code=302)
    return RedirectResponse("/patient/dashboard", status_code=302)


















