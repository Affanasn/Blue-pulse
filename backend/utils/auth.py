# backend/utils/auth.py
import jwt
from datetime import datetime, timedelta
from flask import current_app

def generate_jwt(user_id, is_admin=False, expires_minutes=60*24):
    payload = {
        'sub': user_id,
        'admin': bool(is_admin),
        'exp': datetime.utcnow() + timedelta(minutes=expires_minutes)
    }
    return jwt.encode(payload, current_app.config['SECRET_KEY'], algorithm='HS256')

def decode_jwt(token):
    return jwt.decode(token, current_app.config['SECRET_KEY'], algorithms=['HS256'])
