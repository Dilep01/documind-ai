import hashlib
import secrets
from datetime import timedelta

from argon2 import PasswordHasher
from argon2.exceptions import VerificationError
from fastapi import Depends, HTTPException, Request
from sqlalchemy.orm import Session

from documind_ai.database import LoginSession, User, get_db, now

hasher = PasswordHasher(time_cost=2, memory_cost=19456, parallelism=1)
DUMMY_HASH = hasher.hash("constant-time-unknown-user-password")


def hash_password(password: str) -> str:
    if not 12 <= len(password) <= 200:
        raise ValueError("Use a password between 12 and 200 characters.")
    return hasher.hash(password)


def verify_password(stored: str, password: str) -> bool:
    try:
        return hasher.verify(stored, password)
    except VerificationError:
        return False


def token_hash(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()


def create_session(db: Session, user: User) -> tuple[str, LoginSession]:
    token = secrets.token_urlsafe(40)
    session = LoginSession(
        token_hash=token_hash(token),
        user_id=user.id,
        csrf_token=secrets.token_urlsafe(32),
        expires_at=now() + timedelta(hours=8),
    )
    db.add(session)
    return token, session


def current_user(request: Request, db: Session = Depends(get_db)) -> User:
    token = request.cookies.get("documind_session", "")
    if not token:
        raise HTTPException(401, "Sign in to continue.")
    session = db.get(LoginSession, token_hash(token))
    if session is None or session.expires_at <= now():
        raise HTTPException(401, "Your session expired. Please sign in again.")
    user = db.get(User, session.user_id)
    if user is None or not user.active:
        raise HTTPException(401, "This account is inactive.")
    if request.method not in {"GET", "HEAD", "OPTIONS"}:
        supplied = request.headers.get("x-documind-csrf", "")
        if not secrets.compare_digest(supplied, session.csrf_token):
            raise HTTPException(403, "Invalid request token. Reload and try again.")
    request.state.login_session = session
    return user


def reviewer(user: User = Depends(current_user)) -> User:
    if user.role not in {"reviewer", "admin"}:
        raise HTTPException(403, "Reviewer permission is required.")
    return user


def admin(user: User = Depends(current_user)) -> User:
    if user.role != "admin":
        raise HTTPException(403, "Administrator permission is required.")
    return user
