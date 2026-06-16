# backend/create_admin.py
import os
from models import db, User
from app import app

def create_admin(email: str, password: str):
    with app.app_context():
        existing = User.query.filter_by(email=email).first()
        if existing:
            print(f"User exists: {email} — promoting to admin.")
            existing.is_admin = True
            if password:
                existing.set_password(password)
            db.session.commit()
            print("Promoted existing user to admin.")
            return
        u = User(email=email, is_admin=True)
        u.set_password(password)
        db.session.add(u)
        db.session.commit()
        print("Created admin user:", email)

if __name__ == "__main__":
    import sys
    if len(sys.argv) < 3:
        print("Usage: python create_admin.py admin@example.com password123")
        sys.exit(1)
    create_admin(sys.argv[1], sys.argv[2])
