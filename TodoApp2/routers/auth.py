import bcrypt
import logging
import os
import smtplib
from datetime import datetime, timedelta, timezone
from email.message import EmailMessage
from typing import Optional

from argon2 import PasswordHasher
from argon2.exceptions import VerificationError
from dotenv import load_dotenv
from fastapi import APIRouter, Depends, Form, HTTPException, Request, status
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from jose import JWTError, jwt
from sqlalchemy.orm import Session

import models
from database import SessionLocal
from template_utils import render_template

load_dotenv()

SECRET_KEY = os.environ.get("SECRET_KEY")
if not SECRET_KEY and not os.getenv("VERCEL"):
    SECRET_KEY = "daymark-local-development-only-key"
ALGORITHM = os.environ.get("ALGORITHM", "HS256")
TOKEN_EXPIRES_MINUTES = 60

logger = logging.getLogger(__name__)
password_hasher = PasswordHasher()
templates = Jinja2Templates(directory="templates")
router = APIRouter(prefix="/auth", tags=["auth"])


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def get_password_hash(password: str) -> str:
    return password_hasher.hash(password)


def verify_password(plain_password: str, hashed_password: str) -> bool:
    if hashed_password.startswith(("$2a$", "$2b$", "$2y$")):
        try:
            return bcrypt.checkpw(plain_password.encode("utf-8")[:72], hashed_password.encode("ascii"))
        except (UnicodeEncodeError, ValueError, TypeError):
            return False

    try:
        return password_hasher.verify(hashed_password, plain_password)
    except (VerificationError, TypeError, ValueError):
        return False


def authenticate_user(username: str, password: str, db: Session):
    user = db.query(models.Users).filter(models.Users.username == username).first()
    if user is None or not verify_password(password, user.hashed_password):
        return False

    if user.hashed_password.startswith(("$2a$", "$2b$", "$2y$")) or password_hasher.check_needs_rehash(user.hashed_password):
        user.hashed_password = get_password_hash(password)
        db.commit()

    return user


def create_access_token(username: str, user_id: int,
                        expires_delta: Optional[timedelta] = None) -> str:
    if not SECRET_KEY:
        raise RuntimeError("Set SECRET_KEY in the environment before using authentication.")

    expires_at = datetime.now(timezone.utc) + (expires_delta or timedelta(minutes=15))
    payload = {"sub": username, "id": user_id, "exp": expires_at}
    return jwt.encode(payload, SECRET_KEY, algorithm=ALGORITHM)


async def get_current_user(request: Request):
    token = request.cookies.get("access_token")
    if not token or not SECRET_KEY:
        return None

    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
    except JWTError:
        return None

    username = payload.get("sub")
    user_id = payload.get("id")
    if not isinstance(username, str) or not isinstance(user_id, int):
        return None
    return {"username": username, "id": user_id}


@router.get("/", response_class=HTMLResponse)
async def authentication_page(request: Request):
    return render_template(templates, request, "login.html", {"user": None})


@router.post("/", response_class=HTMLResponse)
async def login(request: Request, db: Session = Depends(get_db)):
    form = await request.form()
    username = str(form.get("username") or form.get("email") or "").strip()
    password = str(form.get("password") or "")
    user = authenticate_user(username, password, db)
    if not user:
        return render_template(
            templates,
            request,
            "login.html",
            {"user": None, "msg": "Incorrect username or password."},
            status_code=status.HTTP_401_UNAUTHORIZED,
        )

    token = create_access_token(
        user.username,
        user.id,
        expires_delta=timedelta(minutes=TOKEN_EXPIRES_MINUTES),
    )
    response = RedirectResponse(url="/todos/", status_code=status.HTTP_303_SEE_OTHER)
    response.set_cookie(
        key="access_token",
        value=token,
        max_age=TOKEN_EXPIRES_MINUTES * 60,
        httponly=True,
        secure=request.url.scheme == "https",
        samesite="lax",
    )
    return response


@router.get("/logout")
async def logout():
    response = RedirectResponse(url="/auth/", status_code=status.HTTP_303_SEE_OTHER)
    response.delete_cookie(key="access_token", httponly=True, samesite="lax")
    return response


@router.get("/register", response_class=HTMLResponse)
async def register(request: Request):
    return render_template(templates, request, "register.html", {"user": None})


@router.post("/register", response_class=HTMLResponse)
async def register_user(
    request: Request,
    email: str = Form(...),
    username: str = Form(...),
    firstname: str = Form(...),
    lastname: str = Form(...),
    password: str = Form(...),
    password2: str = Form(...),
    db: Session = Depends(get_db),
):
    username = username.strip()
    email = email.strip().lower()
    username_exists = db.query(models.Users).filter(models.Users.username == username).first()
    email_exists = db.query(models.Users).filter(models.Users.email == email).first()

    if password != password2:
        message = "Your passwords do not match."
    elif len(password) < 8:
        message = "Use a password with at least 8 characters."
    elif username_exists or email_exists:
        message = "That username or email is already registered."
    else:
        user = models.Users(
            username=username,
            email=email,
            first_name=firstname.strip(),
            last_name=lastname.strip(),
            hashed_password=get_password_hash(password),
            is_active=True,
        )
        db.add(user)
        db.commit()

        email_address = os.environ.get("EMAIL_ADDRESS") or os.environ.get("email_address")
        email_password = os.environ.get("EMAIL_PASSWORD") or os.environ.get("email_password")
        if email_address and email_password:
            message_email = EmailMessage()
            message_email["Subject"] = "Welcome to Daymark"
            message_email["From"] = email_address
            message_email["To"] = email
            message_email.set_content(f"Welcome to Daymark, {user.first_name}.")
            try:
                with smtplib.SMTP_SSL("smtp.gmail.com", 465, timeout=10) as smtp:
                    smtp.login(email_address, email_password)
                    smtp.send_message(message_email)
            except (OSError, smtplib.SMTPException):
                logger.warning("Welcome email could not be sent.")

        return render_template(
            templates,
            request,
            "login.html",
            {"user": None, "msg": "Your account is ready. Sign in to continue."},
        )

    return render_template(
        templates,
        request,
        "register.html",
        {"user": None, "msg": message},
        status_code=status.HTTP_400_BAD_REQUEST,
    )
