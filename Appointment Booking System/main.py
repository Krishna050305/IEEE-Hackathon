from fastapi import FastAPI, Request, Form, status, Query, Depends, HTTPException
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from starlette.middleware.sessions import SessionMiddleware
from starlette.responses import RedirectResponse
from pathlib import Path
from passlib.hash import bcrypt
from passlib.context import CryptContext
from pymongo import MongoClient
from bson import ObjectId
from datetime import datetime
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm
from authlib.integrations.starlette_client import OAuthError
import os
from authlib.integrations.starlette_client import OAuth
from dotenv import load_dotenv
import logging
import sys

# Configure root logger
logging.basicConfig(
    level=logging.INFO,  # Change to INFO in production
    format="%(asctime)s - %(levelname)s - %(name)s - %(message)s",
    stream=sys.stdout
)

logger = logging.getLogger("appointment_app")

load_dotenv()

app = FastAPI()

app.add_middleware(SessionMiddleware, secret_key=os.getenv("SECRET_KEY", "dev-secret"))

#Implementing o-auth2 for security
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/token")
@app.post("/token")
async def token(form_data: OAuth2PasswordRequestForm = Depends()):
    user = db["Users"].find_one({"email": form_data.username})
    if not user or not bcrypt.verify(form_data.password, user["password"]):
        raise HTTPException(status_code=401, detail="Invalid credentials")
    return {"access_token": str(user["_id"]), "token_type": "bearer"}

oauth = OAuth()
oauth.register(
    name="google",
    client_id=os.getenv("GOOGLE_CLIENT_ID"),
    client_secret=os.getenv("GOOGLE_CLIENT_SECRET"),
    server_metadata_url="https://accounts.google.com/.well-known/openid-configuration",
    client_kwargs={"scope": "openid email profile"},
)

# --- Admin Auth Helpers ---
from functools import wraps

ADMIN_EMAIL = os.getenv("ADMIN_EMAIL")
ADMIN_PASSWORD = os.getenv("ADMIN_PASSWORD")

def require_admin(request: Request):
    if request.session.get("admin") != True:
        return RedirectResponse("/admin/login?next=/admin/dashboard", status_code=302)
    return True

mongo_uri = os.getenv('MONGO_URI')
client = MongoClient(mongo_uri)
db = client["ApoointmentBooking"]  

patient_collection = db["Patients"]
doctor_collection = db["Doctors"]

# One-time migration: set status for existing doctors without it
doctor_collection.update_many(
    {"status": {"$exists": False}},
    {"$set": {"status": "pending", "is_approved": False, "approved_at": None}}
)

# Templates
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
templates = Jinja2Templates(directory=os.path.join(BASE_DIR, "templates"))
app.mount("/static", StaticFiles(directory=os.path.join(BASE_DIR, "static")), name="static")


#Google OAuth2 
@app.get("/login/google")
async def login_google(request: Request, role: str = None):
    if role:
        request.session["oauth_role"] = role  # remember that this came from the doctor page
    redirect_uri = "https://ieee-hackathon-12.onrender.com/auth/google/callback"
    return await oauth.google.authorize_redirect(request, redirect_uri)


@app.get("/auth/google/callback")
async def auth_google_callback(request: Request):
    try:
        token = await oauth.google.authorize_access_token(request)
        resp = await oauth.google.get("userinfo", token=token)
        logger.info(f"Google OAuth response: {resp.json()}")
        userinfo = resp.json()
        email = userinfo["email"]
        name = userinfo.get("name") or userinfo.get("given_name") or "User"
        
    except OAuthError as e:
        # See exactly what failed
        msg = f"{e.error}:{e.description}"
        logger.error(f"OAuth error: {msg}")
    except Exception as e:
        # optional: log e
        logger.error(f"OAuth callback failed: {str(e)}")
        return RedirectResponse(url="https://ieee-hackathon-12.onrender.com", status_code=303)
    

    # email = userinfo["email"]
    # name = userinfo.get("name") or userinfo.get("given_name") or "User"

    patient = db["Patients"].find_one({"email": email})
    doctor  = db["Doctors"].find_one({"email": email})

    if patient:
        request.session.update({
            "user": str(patient["_id"]), "role": "patient",
            "user_name": patient.get("full_name") or name
        })
        return RedirectResponse(url="/", status_code=303)

    if doctor:
        status_val = doctor.get("status", "pending")
        if status_val != "approved":
            request.session["flash_error"] = (
                "Your doctor account is pending admin approval."
                if status_val == "pending" else
                "Your doctor account was denied by admin."
            )
            return RedirectResponse(url="/doctor/login", status_code=303)

        request.session.update({
            "user": str(doctor["_id"]), "role": "doctor",
            "user_name": doctor.get("full_name") or name
        })
        return RedirectResponse(url="/", status_code=303)

    role_hint = request.session.pop("oauth_role", None)
    if role_hint == "doctor":
        doctor_collection.insert_one({
            "full_name": name, "email": email,
            "specialization": "", "clinic_id": None,
            "password": None, "status": "pending",
            "is_approved": False, "approved_at": None
        })
        request.session["flash_error"] = "Your doctor account is pending admin approval."
        return RedirectResponse(url="/doctor/login", status_code=303)

    request.session["pending_google"] = {
        "email": email, "name": name, "sub": userinfo.get("sub")
    }
    return RedirectResponse(url="/", status_code=303)



# Homepage with Role Selection
@app.get("/", response_class=HTMLResponse)
async def home(request: Request):
    user_id = request.session.get("user")
    role = request.session.get("role")
    user_name = None

    # if user_id:
    #     if role == "patient":
    #         user = db["Patients"].find_one({"_id": ObjectId(user_id)})
    #         user_name = user["full_name"] if user else None
    #     elif role == "doctor":
    #         doctor = db["Doctors"].find_one({"_id": ObjectId(user_id)})
    #         user_name = doctor["full_name"] if doctor else None
    
    if not user_name and user_id and role:
        try:
            if role == "patient":
                user = db["Patients"].find_one({"_id": ObjectId(user_id)})
                user_name = user.get("full_name") if user else None
            elif role == "doctor":
                doc = db["Doctors"].find_one({"_id": ObjectId(user_id)})
                user_name = doc.get("full_name") if doc else None
        except Exception:
            pass  # keep whatever we had

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
    
    
#Google OAuth2 
@app.get("/login/google")
async def login_google(request: Request):
    # optional: add 'next' to return users back where they came from
    redirect_uri = os.getenv("OAUTH_REDIRECT_URI")
    return await oauth.google.authorize_redirect(request, redirect_uri)

@app.get("/auth/google/callback")
async def auth_google_callback(request: Request):
    token = await oauth.google.authorize_access_token(request)
    userinfo = token.get("userinfo") or await oauth.google.parse_id_token(request, token)
    email = userinfo["email"]
    name = userinfo.get("name") or userinfo.get("given_name") or "User"

    # Try patient first
    patient = db["Patients"].find_one({"email": email})
    doctor  = db["Doctors"].find_one({"email": email})

    if patient:
        user_id, role = str(patient["_id"]), "patient"
    elif doctor:
        user_id, role = str(doctor["_id"]), "doctor"
    else:
        # first login via Google → ask which role to create
        request.session["pending_google"] = {"email": email, "name": name, "sub": userinfo["sub"]}
        return RedirectResponse("/", status_code=302)

    request.session.update({"user": user_id, "role": role, "user_name": name})
    return RedirectResponse("/", status_code=302)



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



def require_login(request: Request):
    if not request.session.get("user"):
        return RedirectResponse("/?error=login_required", status_code=302)
    return True



@app.get("/patient/dashboard", response_class=HTMLResponse)
async def patient_dashboard(
    request: Request,
    action: str = None,
    date: str = None,
    slot: str = None,
    ok: bool = Depends(require_login)
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

    # Is there already a doctor with this name+spec+clinic?
    existing_doctor = doctor_collection.find_one({
        "full_name": full_name,
        "specialization": specialization,
        "clinic_id": clinic_obj_id
    })

    if existing_doctor:
        # Update existing profile (keep its current approval fields if present)
        doctor_collection.update_one(
            {"_id": existing_doctor["_id"]},
            {"$set": {
                "email": email,
                "password": bcrypt.hash(password),
                "status": existing_doctor.get("status", "pending"),
                "is_approved": existing_doctor.get("is_approved", False),
                "approved_at": existing_doctor.get("approved_at", None),
            }}
        )
    else:
        # Create a new record WITH approval fields
        doctor_collection.insert_one({
            "full_name": full_name,
            "email": email,
            "specialization": specialization,
            "clinic_id": clinic_obj_id,
            "password": bcrypt.hash(password),
            "status": "pending",
            "is_approved": False,
            "approved_at": None,
        })

    # ✅ Fetch the fresh copy (doctor was None before insert)
    doctor = doctor_collection.find_one({"email": email})

    status_val = doctor.get("status", "pending")
    if status_val != "approved":
        msg = (
            "Your account is pending approval by admin."
            if status_val == "pending"
            else "Your account was denied by admin."
        )
        return templates.TemplateResponse("doctor/login.html", {"request": request, "error": msg})

    return RedirectResponse("/doctor/login", status_code=status.HTTP_302_FOUND)




@app.get("/doctor/login", response_class=HTMLResponse)
async def get_doctor_login(request: Request):
    return templates.TemplateResponse("doctor/login.html", {"request": request})


@app.post("/doctor/login", response_class=HTMLResponse)
async def post_doctor_login(request: Request, email: str = Form(...), password: str = Form(...)):
    doctor = doctor_collection.find_one({"email": email})
    if not doctor:
        return templates.TemplateResponse("doctor/login.html", {"request": request, "error": "No such account"})

    # If the doctor registered via Google, password is None
    if doctor.get("password") is None or not bcrypt.verify(password, doctor["password"]):
        return templates.TemplateResponse("doctor/login.html", {"request": request, "error": "Invalid credentials"})
    
    
    status_val = doctor.get("status", "pending")
    if status_val != "approved":
        msg = "Your account is pending approval by admin." if status_val == "pending" else "Your account has been denied by admin."
        return templates.TemplateResponse("doctor/login.html", {"request": request, "error": msg})

    if doctor.get("status", "pending") != "approved":
        msg = "Your account is pending approval by admin." if doctor.get("status") == "pending" else "Your account was denied by admin."
        return templates.TemplateResponse("doctor/login.html", {"request": request, "error": msg})

    request.session.update({"user": str(doctor["_id"]), "role": "doctor", "user_name": doctor.get("full_name")})
    return RedirectResponse("/", status_code=302)



@app.get("/doctor/dashboard", response_class=HTMLResponse)
async def doctor_dashboard(request: Request):
    doctor_id = request.session.get("user")
    role = request.session.get("role")
    if not doctor_id or role != "doctor":
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
    if not doctor or doctor.get("status") != "approved":
        return RedirectResponse("/doctor/login", status_code=302)

    return templates.TemplateResponse("doctor/dashboard.html", {
        "request": request,
        "doctor": doctor,
        "patients": patient_data
    })
    
# ----------------- Admin Auth & Dashboard -----------------

@app.get("/admin/login", response_class=HTMLResponse)
async def admin_login_page(request: Request, next: str = "/admin/dashboard"):
    err = request.query_params.get("error")
    html = f"""
    <!doctype html><html><head>
      <title>Admin Login</title>
      <link href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.0/dist/css/bootstrap.min.css" rel="stylesheet">
    </head><body class="p-4" style="font-family:Segoe UI;" >
      <div class="container" style="max-width:420px;">
        <h3 class="mb-3">Admin Login</h3>
        {'<div class="alert alert-danger">'+err+'</div>' if err else ''}
        <form method="post" action="/admin/login" class="card card-body">
          <input type="hidden" name="next" value="{next}">
          <div class="mb-3">
            <label class="form-label">Email</label>
            <input name="email" type="email" class="form-control" required>
          </div>
          <div class="mb-3">
            <label class="form-label">Password</label>
            <input name="password" type="password" class="form-control" required>
          </div>
          <button class="btn btn-primary w-100">Login</button>
        </form>
      </div>
    </body></html>
    """
    return HTMLResponse(html)

@app.post("/admin/login")
async def admin_login(request: Request, email: str = Form(...), password: str = Form(...), next: str = Form("/admin/dashboard")):
    if email.strip().lower() != ADMIN_EMAIL.strip().lower() or password != ADMIN_PASSWORD:
        return RedirectResponse("/admin/login?error=Invalid+credentials", status_code=302)
    request.session["admin"] = True
    return RedirectResponse(next or "/admin/dashboard", status_code=302)

@app.get("/admin/logout")
async def admin_logout(request: Request):
    request.session.pop("admin", None)
    return RedirectResponse("/", status_code=302)

@app.get("/admin/dashboard", response_class=HTMLResponse)
async def admin_dashboard(request: Request):
    guard = require_admin(request)
    if guard is not True:
        return guard

    pending  = list(doctor_collection.find({"$or": [{"status": "pending"}, {"status": {"$exists": False}}]}))
    approved = list(doctor_collection.find({"status": "approved"}))
    denied   = list(doctor_collection.find({"status": "denied"}))


    def tbl(title, docs):
        rows = "".join(f"""
        <tr>
          <td>{d.get('full_name','')}</td>
          <td>{d.get('email','')}</td>
          <td>{d.get('specialization','')}</td>
          <td>
            <form method="post" action="/admin/doctor/{str(d['_id'])}/approve" class="d-inline">
              <button class="btn btn-sm btn-success">Approve</button>
            </form>
            <form method="post" action="/admin/doctor/{str(d['_id'])}/deny" class="d-inline ms-2">
              <button class="btn btn-sm btn-outline-danger">Deny</button>
            </form>
          </td>
        </tr>""" for d in docs)
        if not rows:
            rows = '<tr><td colspan="4" class="text-center text-muted">None</td></tr>'
        return f"""
        <h5 class="mt-4">{title} <span class="badge bg-secondary">{len(docs)}</span></h5>
        <div class="table-responsive">
          <table class="table table-sm align-middle">
            <thead><tr><th>Name</th><th>Email</th><th>Specialization</th><th>Actions</th></tr></thead>
            <tbody>{rows}</tbody>
          </table>
        </div>
        """

    html = f"""
    <!doctype html><html><head>
      <title>Admin Dashboard</title>
      <link href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.0/dist/css/bootstrap.min.css" rel="stylesheet">
    </head><body class="p-4" style=
    "font-family:Segoe UI";
    "background-image: url('/static/images/bg.png');
    background-size: cover;
    background-repeat: no-repeat;
    background-position: center;">
      <div class="container">
        <div class="d-flex justify-content-between align-items-center">
          <h3>Admin Dashboard</h3>
          <a class="btn btn-outline-secondary" href="/admin/logout">Logout</a>
        </div>
        {tbl("Pending Doctors", pending)}
        {tbl("Approved Doctors", approved)}
        {tbl("Denied Doctors", denied)}
      </div>
    </body></html>
    """
    return HTMLResponse(html)

@app.post("/admin/doctor/{doctor_id}/approve")
async def admin_approve_doctor(request: Request, doctor_id: str):
    guard = require_admin(request)
    if guard is not True:
        return guard
    doctor_collection.update_one(
        {"_id": ObjectId(doctor_id)},
        {"$set": {"status": "approved", "is_approved": True, "approved_at": datetime.utcnow()}}
    )
    return RedirectResponse("/admin/dashboard", status_code=302)

@app.post("/admin/doctor/{doctor_id}/deny")
async def admin_deny_doctor(request: Request, doctor_id: str):
    guard = require_admin(request)
    if guard is not True:
        return guard
    doctor_collection.update_one(
        {"_id": ObjectId(doctor_id)},
        {"$set": {"status": "denied", "is_approved": False, "approved_at": None}}
    )
    return RedirectResponse("/admin/dashboard", status_code=302)

    
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