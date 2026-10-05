from fastapi import APIRouter, Depends, Form, Request, status
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session

import models
from database import SessionLocal
from .auth import get_current_user, get_password_hash, verify_password
from template_utils import render_template

router = APIRouter(prefix="/users", tags=["users"])
templates = Jinja2Templates(directory="templates")


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


@router.get("/edit-password", response_class=HTMLResponse)
async def edit_user_view(request: Request):
    user = await get_current_user(request)
    if user is None:
        return RedirectResponse(url="/auth/", status_code=status.HTTP_303_SEE_OTHER)
    return render_template(
        templates,
        request,
        "edit-user-password.html",
        {"user": user},
    )


@router.post("/edit-password", response_class=HTMLResponse)
async def user_password_change(
    request: Request,
    password: str = Form(...),
    new_password: str = Form(...),
    new_password_confirm: str = Form(...),
    db: Session = Depends(get_db),
):
    identity = await get_current_user(request)
    if identity is None:
        return RedirectResponse(url="/auth/", status_code=status.HTTP_303_SEE_OTHER)

    user = db.query(models.Users).filter(models.Users.id == identity["id"]).first()
    if user is None or not verify_password(password, user.hashed_password):
        message = "Your current password is incorrect."
    elif len(new_password) < 8:
        message = "Use a password with at least 8 characters."
    elif new_password != new_password_confirm:
        message = "Your new passwords do not match."
    else:
        user.hashed_password = get_password_hash(new_password)
        db.commit()
        message = "Password updated."

    return render_template(
        templates,
        request,
        "edit-user-password.html",
        {"user": identity, "msg": message},
        status_code=status.HTTP_400_BAD_REQUEST if message != "Password updated." else status.HTTP_200_OK,
    )
