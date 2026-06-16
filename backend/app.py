import os
import uuid
import datetime
from typing import Optional, Dict, Tuple

from flask import Flask, request, jsonify, send_from_directory, abort
from flask_cors import CORS
from werkzeug.utils import secure_filename
from flask_migrate import Migrate

from models import db, User, Complaint, Employee
from utils.auth import generate_jwt, decode_jwt 

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
FRONTEND_DIR = os.path.join(BASE_DIR, "frontend")
UPLOAD_FOLDER = os.path.join(BASE_DIR, "uploads")
ALLOWED_EXTENSIONS = {"png", "jpg", "jpeg", "gif"}

os.makedirs(UPLOAD_FOLDER, exist_ok=True)
os.makedirs(FRONTEND_DIR, exist_ok=True)

app = Flask(__name__, static_folder=FRONTEND_DIR, static_url_path="")
CORS(app)  

app.config["SQLALCHEMY_DATABASE_URI"] = os.getenv(
    "DATABASE_URL", "sqlite:///" + os.path.join(BASE_DIR, "app.db")
)
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False
app.config["SECRET_KEY"] = os.getenv("SECRET_KEY", "dev-secret-change-me")
app.config["UPLOAD_FOLDER"] = UPLOAD_FOLDER
app.config["MAX_CONTENT_LENGTH"] = 16 * 1024 * 1024  

db.init_app(app)
migrate = Migrate(app, db)


def allowed_file(filename: str) -> bool:
    return "." in filename and filename.rsplit(".", 1)[1].lower() in ALLOWED_EXTENSIONS


def get_current_user() -> Tuple[Optional[User], Optional[Dict]]:
    """
    Extract current user from Authorization header using utils.auth.decode_jwt.
    Returns (User model or None, token payload or None)
    """
    auth = request.headers.get("Authorization")
    if not auth:
        return None, None
    try:
        token = auth.split()[1]
        payload = decode_jwt(token)
        if not payload or "sub" not in payload:
            return None, None
        user = db.session.get(User, payload["sub"])
        return user, payload
    except Exception:
        return None, None


@app.route("/api/auth/register", methods=["POST"])
def register():
    data = request.get_json() or {}
    email = data.get("email")
    pw = data.get("password")
    role = data.get("role", "user")
    secret_key = data.get("secret_key")

    if not email or not pw:
        return jsonify({"error": "email and password required"}), 400

    if role == "admin":
        expected_secret = os.getenv("ADMIN_SECRET_KEY", "supersecret123")
        if not secret_key or secret_key != expected_secret:
            return jsonify({"error": "Invalid admin secret key"}), 403

    if User.query.filter_by(email=email).first():
        return jsonify({"error": "email already registered"}), 400

    u = User(email=email, role=role)
    u.set_password(pw)
    db.session.add(u)
    db.session.commit()

    token = generate_jwt(u.id, is_admin=(u.role == "admin"))
    return (
        jsonify({"token": token, "user": {"id": u.id, "email": u.email, "role": u.role}}),
        201,
    )


@app.route("/api/auth/login", methods=["POST"])
def login():
    data = request.get_json() or {}
    email = data.get("email")
    pw = data.get("password")

    u = User.query.filter_by(email=email).first()
    if not u or not u.check_password(pw):
        return jsonify({"error": "Invalid credentials"}), 401

    token = generate_jwt(u.id, is_admin=(u.role == "admin"))
    return jsonify({"token": token, "user": {"id": u.id, "email": u.email, "role": u.role}})


@app.route("/api/employees", methods=["GET"])
def list_employees():
    user, _ = get_current_user()
    if not user or user.role != "admin":
        return jsonify({"error": "admin_required"}), 403

    employees = Employee.query.order_by(Employee.name.asc()).all()
    return jsonify(
        [
            {"id": e.id, "name": e.name, "email": e.email, "phone": e.phone, "role": e.role}
            for e in employees
        ]
    )


@app.route("/api/employees", methods=["POST"])
def add_employee():
    user, _ = get_current_user()
    if not user or user.role != "admin":
        return jsonify({"error": "admin_required"}), 403

    data = request.get_json() or {}
    name = data.get("name")
    email = data.get("email")
    phone = data.get("phone")
    role = data.get("role", "technician")

    if not name or not email or not phone:
        return jsonify({"error": "Missing required fields (name, email, phone)"}), 400

    if Employee.query.filter_by(email=email).first():
        return jsonify({"error": "Employee email already exists"}), 400

    emp = Employee(name=name, email=email, phone=phone, role=role)
    db.session.add(emp)
    db.session.commit()
    return jsonify({"message": "Employee added", "id": emp.id}), 201


@app.route("/api/employees/<int:eid>", methods=["DELETE"])
def delete_employee(eid):
    user, _ = get_current_user()
    if not user or user.role != "admin":
        return jsonify({"error": "admin_required"}), 403

    emp = Employee.query.get(eid)
    if not emp:
        return jsonify({"error": "not_found"}), 404

    assigned_count = Complaint.query.filter(Complaint.assigned_to_id == emp.id).count()
    if assigned_count > 0:
        return jsonify({"error": "employee_assigned_to_complaints"}), 400

    db.session.delete(emp)
    db.session.commit()
    return jsonify({"ok": True})

@app.route("/api/complaints", methods=["POST"])
def create_complaint():
    user, _ = get_current_user()
    file = request.files.get("file")
    title = request.form.get("title")
    description = request.form.get("description")
    lat = request.form.get("lat")
    lng = request.form.get("lng")

    if not title or not description:
        return jsonify({"error": "Title and description required"}), 400

    photo_filename = None
    if file and file.filename and allowed_file(file.filename):
        ext = file.filename.rsplit(".", 1)[1].lower()
        filename = secure_filename(f"{uuid.uuid4().hex}.{ext}")
        fp = os.path.join(app.config["UPLOAD_FOLDER"], filename)
        file.save(fp)
        photo_filename = filename

    complaint = Complaint(
        title=title,
        description=description,
        photo_path=photo_filename,
        lat=float(lat) if lat else None,
        lng=float(lng) if lng else None,
        created_by=user.id if user else None,
    )
    db.session.add(complaint)
    db.session.commit()

    return jsonify(
        {
            "id": complaint.id,
            "title": complaint.title,
            "description": complaint.description,
            "photo_path": complaint.photo_path,
            "lat": complaint.lat,
            "lng": complaint.lng,
            "status": complaint.status,
            "assigned_to": _employee_payload(complaint),
            "timestamp": complaint.created_at.isoformat(),
        }
    ), 201


@app.route("/api/complaints", methods=["GET"])
def list_complaints():
    """Admin sees all, normal users see only their own complaints."""
    user, _ = get_current_user()

    q = Complaint.query.order_by(Complaint.created_at.desc())
    if not (user and user.role == "admin"):
        if not user:
            return jsonify([])  
        q = q.filter_by(created_by=user.id)

    rows = q.all()
    out = []
    for c in rows:
        out.append(
            {
                "id": c.id,
                "title": c.title,
                "description": c.description,
                "photo_path": c.photo_path,
                "lat": c.lat,
                "lng": c.lng,
                "status": c.status,
                "assigned_to": _employee_payload(c),
                "timestamp": c.created_at.isoformat(),
            }
        )
    return jsonify(out)


@app.route("/api/complaints/<cid>", methods=["PUT", "PATCH"])
@app.route("/api/complaints/<cid>/status", methods=["PUT"])
def update_complaint_status(cid):
    """
    Admin API to change status. Accepts JSON:
      { "status": "assigned", "assigned_to": <employee_id> }
    """
    user, _ = get_current_user()
    if not user or user.role != "admin":
        return jsonify({"error": "admin_required"}), 403

    data = request.get_json() or {}
    status = data.get("status")
    emp_id = data.get("assigned_to")

    if status not in ["raised", "assigned", "installed", "closed"]:
        return jsonify({"error": "invalid status"}), 400

    c = Complaint.query.get(cid)
    if not c:
        return jsonify({"error": "not found"}), 404

    c.status = status

    if status == "assigned":
        if emp_id:
            emp = Employee.query.get(emp_id)
            if not emp:
                return jsonify({"error": "employee_not_found"}), 404
            c.assigned_to_id = emp.id
    else:
        pass

    c.created_at = datetime.datetime.utcnow()
    db.session.commit()

    return jsonify(
        {
            "ok": True,
            "id": c.id,
            "status": c.status,
            "assigned_to": _employee_payload(c),
            "timestamp": c.created_at.isoformat(),
        }
    )


@app.route("/api/complaints/<cid>", methods=["DELETE"])
def delete_complaint(cid):
    user, _ = get_current_user()
    if not user or user.role != "admin":
        return jsonify({"error": "admin_required"}), 403

    c = Complaint.query.get(cid)
    if not c:
        return jsonify({"error": "not found"}), 404

    if (c.status or "").lower() != "closed":
        return jsonify({"error": "only closed complaints can be deleted"}), 400

    if c.photo_path:
        try:
            fp = os.path.join(app.config["UPLOAD_FOLDER"], c.photo_path)
            if os.path.exists(fp):
                os.remove(fp)
        except Exception as e:
            app.logger.warning("Failed to remove file %s: %s", getattr(c, "photo_path", None), e)

    db.session.delete(c)
    db.session.commit()
    return jsonify({"ok": True, "message": "Complaint deleted"}), 200


@app.route("/uploads/<filename>")
def uploaded_file(filename):
    if not filename or ".." in filename or filename.startswith("/"):
        abort(404)
    return send_from_directory(app.config["UPLOAD_FOLDER"], filename)


@app.route("/")
def index():
    index_path = os.path.join(FRONTEND_DIR, "index.html")
    if not os.path.exists(index_path):
        return (f"Frontend index.html not found. Put your frontend files in: {FRONTEND_DIR}"), 500
    return send_from_directory(FRONTEND_DIR, "index.html")


@app.errorhandler(404)
def handle_404(err):
    req_path = request.path.lstrip("/")
    candidate = os.path.join(FRONTEND_DIR, req_path)
    if req_path and os.path.exists(candidate) and os.path.isfile(candidate):
        return send_from_directory(FRONTEND_DIR, req_path)
    if request.path.startswith("/api/"):
        return jsonify({"error": "API endpoint not found"}), 404
    return send_from_directory(FRONTEND_DIR, "index.html")

def _employee_payload(complaint):
    """
    Returns None or a small dict with employee details if assigned.
    Handles cases where `complaint.assigned_to` might be:
      - None
      - integer id
      - an Employee instance (relationship)
    """
    try:
        emp_ref = getattr(complaint, "assigned_to", None)
        if not emp_ref:
            return None

        if isinstance(emp_ref, Employee):
            emp = emp_ref
        else:
            try:
                emp_id = int(emp_ref)
            except Exception:
                emp_id = emp_ref
            emp = db.session.get(Employee, emp_id)

        if not emp:
            return None

        return {"id": emp.id, "name": emp.name, "email": emp.email, "phone": emp.phone, "role": emp.role}
    except Exception as e:
        app.logger.exception("Error building employee payload: %s", e)
        return None



if __name__ == "__main__":
    print("Serving frontend from:", FRONTEND_DIR)
    print("Serving uploads from:", UPLOAD_FOLDER)
    app.run(debug=True, port=5000, host="0.0.0.0")
