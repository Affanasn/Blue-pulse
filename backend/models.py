from flask_sqlalchemy import SQLAlchemy
from datetime import datetime
from werkzeug.security import generate_password_hash, check_password_hash
import uuid

db = SQLAlchemy()



class User(db.Model):
    id = db.Column(db.String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    email = db.Column(db.String(255), unique=True, nullable=False)
    password_hash = db.Column(db.String(255), nullable=False)
    role = db.Column(db.String(20), default='user')  
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    def set_password(self, pw):
        self.password_hash = generate_password_hash(pw)

    def check_password(self, pw):
        return check_password_hash(self.password_hash, pw)



class Employee(db.Model):
    __tablename__ = 'employees'

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(120), nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False)
    phone = db.Column(db.String(20), nullable=False)
    role = db.Column(db.String(50), default='technician')
    is_active = db.Column(db.Boolean, default=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    complaints = db.relationship('Complaint', back_populates='assigned_to', lazy=True)

    def __repr__(self):
        return f"<Employee {self.name}>"



class Complaint(db.Model):
    __tablename__ = 'complaints'

    id = db.Column(db.String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    title = db.Column(db.String(255), nullable=False)
    description = db.Column(db.Text, nullable=False)
    photo_path = db.Column(db.String(512), nullable=True)
    lat = db.Column(db.Float, nullable=True)
    lng = db.Column(db.Float, nullable=True)
    status = db.Column(db.String(32), default='raised', nullable=False)
    created_by = db.Column(db.String(36), db.ForeignKey('user.id'), nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)

    assigned_to_id = db.Column(db.Integer, db.ForeignKey('employees.id'), nullable=True)
    assigned_to = db.relationship('Employee', back_populates='complaints', lazy='joined')

    def to_dict(self):
        """Convert complaint to JSON-serializable dict for API responses."""
        return {
            "id": self.id,
            "title": self.title,
            "description": self.description,
            "photo_path": self.photo_path,
            "lat": self.lat,
            "lng": self.lng,
            "status": self.status,
            "timestamp": self.created_at.isoformat(),
            "assigned_to": (
                {
                    "id": self.assigned_to.id,
                    "name": self.assigned_to.name,
                    "email": self.assigned_to.email,
                    "phone": self.assigned_to.phone,
                }
                if self.assigned_to
                else None
            ),
        }

    def __repr__(self):
        return f"<Complaint {self.title} - {self.status}>"
