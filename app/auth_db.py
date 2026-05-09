"""User authentication with Firestore — Firebase Admin SDK."""

from datetime import datetime, timedelta, timezone
from typing import Optional

import jwt
from firebase_admin import firestore
from passlib.context import CryptContext

from app.core.config import settings
from app.firestore_db import init_firestore
from app.schemas import UserCreate, UserOut

pwd_context = CryptContext(schemes=["pbkdf2_sha256"], deprecated="auto")


def _users_collection():
    init_firestore()
    return firestore.client().collection(settings.firestore_users_collection)


def hash_password(password: str) -> str:
    return pwd_context.hash(password)


def verify_password(plain_password: str, hashed_password: str) -> bool:
    return pwd_context.verify(plain_password, hashed_password)


def create_user(payload: UserCreate) -> UserOut:
    col = _users_collection()
    # Check if email exists
    existing = col.where("email", "==", payload.email).limit(1).get()
    if existing:
        raise ValueError("User with this email already exists")
    
    hashed_pw = hash_password(payload.password)
    doc_ref = col.document()
    doc_ref.set({
        "email": payload.email,
        "password_hash": hashed_pw,
        "name": payload.name or "",
        "created_at": firestore.SERVER_TIMESTAMP,
    })
    snap = doc_ref.get()
    data = snap.to_dict()
    return UserOut(
        id=doc_ref.id,
        email=data["email"],
        name=data.get("name", ""),
        created_at=data["created_at"].isoformat() if hasattr(data["created_at"], "isoformat") else str(data["created_at"]),
    )


def authenticate_user(email: str, password: str) -> Optional[UserOut]:
    col = _users_collection()
    users = col.where("email", "==", email).limit(1).get()
    if not users:
        return None
    user_doc = users[0]
    data = user_doc.to_dict()
    if not verify_password(password, data["password_hash"]):
        return None
    return UserOut(
        id=user_doc.id,
        email=data["email"],
        name=data.get("name", ""),
        created_at=data["created_at"].isoformat() if hasattr(data["created_at"], "isoformat") else str(data["created_at"]),
    )


def create_access_token(data: dict, expires_delta: Optional[timedelta] = None):
    to_encode = data.copy()
    if expires_delta:
        expire = datetime.now(timezone.utc) + expires_delta
    else:
        expire = datetime.now(timezone.utc) + timedelta(hours=settings.jwt_expiration_hours)
    to_encode.update({"exp": expire})
    encoded_jwt = jwt.encode(to_encode, settings.jwt_secret_key, algorithm=settings.jwt_algorithm)
    return encoded_jwt