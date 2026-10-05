from datetime import date, datetime, timedelta, timezone
from collections import Counter
from typing import Iterable, Optional

from fastapi import APIRouter, Depends, Form, HTTPException, Request, status
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy import func
from sqlalchemy.orm import Session

import models
from database import SessionLocal
from template_utils import render_template
from .auth import get_current_user

router = APIRouter(prefix="/todos", tags=["todos"])
templates = Jinja2Templates(directory="templates")


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def calculate_streak(completion_dates: Iterable[date], today: Optional[date] = None) -> int:
    dates = set(completion_dates)
    current_day = today or datetime.now(timezone.utc).date()
    if current_day not in dates:
        current_day -= timedelta(days=1)

    streak = 0
    while current_day in dates:
        streak += 1
        current_day -= timedelta(days=1)
    return streak


def build_weekly_activity(completion_dates: Iterable[date], today: Optional[date] = None):
    current_day = today or datetime.now(timezone.utc).date()
    counts = Counter(
        completed_day
        for completed_day in completion_dates
        if current_day - timedelta(days=6) <= completed_day <= current_day
    )
    peak = max(counts.values(), default=0)

    return [
        {
            "label": (current_day - timedelta(days=offset)).strftime("%a"),
            "date": (current_day - timedelta(days=offset)).strftime("%b %d"),
            "count": counts[current_day - timedelta(days=offset)],
            "height": round(counts[current_day - timedelta(days=offset)] / peak * 100) if peak else 0,
            "is_today": offset == 0,
        }
        for offset in range(6, -1, -1)
    ]


async def require_user(request: Request):
    return await get_current_user(request)


@router.get("/", response_class=HTMLResponse)
async def read_all_by_user(request: Request, db: Session = Depends(get_db)):
    user = await require_user(request)
    if user is None:
        return RedirectResponse(url="/auth/", status_code=status.HTTP_303_SEE_OTHER)

    todos = (
        db.query(models.Todos)
        .filter(models.Todos.owner_id == user["id"], models.Todos.complete.is_(False))
        .order_by(models.Todos.priority.desc(), models.Todos.due_date.is_(None), models.Todos.due_date)
        .all()
    )
    completed_count = (
        db.query(func.count(models.Todos.id))
        .filter(models.Todos.owner_id == user["id"], models.Todos.complete.is_(True))
        .scalar()
        or 0
    )
    completion_dates = [
        completed_at.date()
        for (completed_at,) in db.query(models.Todos.completed_at).filter(
            models.Todos.owner_id == user["id"],
            models.Todos.complete.is_(True),
            models.Todos.completed_at.is_not(None),
        )
    ]
    today = datetime.now(timezone.utc).date()
    weekly_activity = build_weekly_activity(completion_dates, today)
    completed_this_week = sum(day["count"] for day in weekly_activity)
    open_count = len(todos)
    total_count = open_count + completed_count
    completion_rate = round(completed_count / total_count * 100) if total_count else 0

    return render_template(
        templates,
        request,
        "home.html",
        {
            "user": user,
            "todos": todos,
            "open_count": open_count,
            "completed_count": completed_count,
            "completed_this_week": completed_this_week,
            "weekly_activity": weekly_activity,
            "completion_rate": completion_rate,
            "streak": calculate_streak(completion_dates),
            "today": today,
        },
    )


@router.get("/history", response_class=HTMLResponse)
async def completed_history(request: Request, db: Session = Depends(get_db)):
    user = await require_user(request)
    if user is None:
        return RedirectResponse(url="/auth/", status_code=status.HTTP_303_SEE_OTHER)

    todos = (
        db.query(models.Todos)
        .filter(models.Todos.owner_id == user["id"], models.Todos.complete.is_(True))
        .order_by(models.Todos.completed_at.is_(None), models.Todos.completed_at.desc())
        .all()
    )
    return render_template(
        templates,
        request,
        "history.html",
        {"user": user, "todos": todos},
    )


@router.get("/add-todo", response_class=HTMLResponse)
async def add_new_todo(request: Request):
    user = await require_user(request)
    if user is None:
        return RedirectResponse(url="/auth/", status_code=status.HTTP_303_SEE_OTHER)
    return render_template(templates, request, "add-todo.html", {"user": user})


@router.post("/add-todo")
async def create_todo(
    request: Request,
    title: str = Form(...),
    description: Optional[str] = Form(None),
    priority: int = Form(..., ge=1, le=5),
    due_date: Optional[date] = Form(None),
    db: Session = Depends(get_db),
):
    user = await require_user(request)
    if user is None:
        return RedirectResponse(url="/auth/", status_code=status.HTTP_303_SEE_OTHER)

    todo = models.Todos(
        title=title.strip(),
        description=description.strip() if description else None,
        priority=priority,
        due_date=due_date,
        complete=False,
        owner_id=user["id"],
    )
    db.add(todo)
    db.commit()
    return RedirectResponse(url="/todos/", status_code=status.HTTP_303_SEE_OTHER)


@router.get("/edit-todo/{todo_id}", response_class=HTMLResponse)
async def edit_todo(request: Request, todo_id: int, db: Session = Depends(get_db)):
    user = await require_user(request)
    if user is None:
        return RedirectResponse(url="/auth/", status_code=status.HTTP_303_SEE_OTHER)

    todo = db.query(models.Todos).filter(
        models.Todos.id == todo_id,
        models.Todos.owner_id == user["id"],
    ).first()
    if todo is None:
        raise HTTPException(status_code=404, detail="Task not found")
    return render_template(
        templates,
        request,
        "edit-todo.html",
        {"todo": todo, "user": user},
    )


@router.post("/edit-todo/{todo_id}")
async def edit_todo_commit(
    request: Request,
    todo_id: int,
    title: str = Form(...),
    description: Optional[str] = Form(None),
    priority: int = Form(..., ge=1, le=5),
    due_date: Optional[date] = Form(None),
    db: Session = Depends(get_db),
):
    user = await require_user(request)
    if user is None:
        return RedirectResponse(url="/auth/", status_code=status.HTTP_303_SEE_OTHER)

    todo = db.query(models.Todos).filter(
        models.Todos.id == todo_id,
        models.Todos.owner_id == user["id"],
    ).first()
    if todo is None:
        raise HTTPException(status_code=404, detail="Task not found")

    todo.title = title.strip()
    todo.description = description.strip() if description else None
    todo.priority = priority
    todo.due_date = due_date
    db.commit()
    return RedirectResponse(url="/todos/", status_code=status.HTTP_303_SEE_OTHER)


@router.post("/complete/{todo_id}")
async def complete_todo(request: Request, todo_id: int, db: Session = Depends(get_db)):
    user = await require_user(request)
    if user is None:
        return RedirectResponse(url="/auth/", status_code=status.HTTP_303_SEE_OTHER)

    todo = db.query(models.Todos).filter(
        models.Todos.id == todo_id,
        models.Todos.owner_id == user["id"],
    ).first()
    if todo is None:
        raise HTTPException(status_code=404, detail="Task not found")

    todo.complete = not todo.complete
    todo.completed_at = datetime.now(timezone.utc) if todo.complete else None
    db.commit()
    return RedirectResponse(url="/todos/", status_code=status.HTTP_303_SEE_OTHER)


@router.post("/delete/{todo_id}")
async def delete_todo(request: Request, todo_id: int, db: Session = Depends(get_db)):
    user = await require_user(request)
    if user is None:
        return RedirectResponse(url="/auth/", status_code=status.HTTP_303_SEE_OTHER)

    todo = db.query(models.Todos).filter(
        models.Todos.id == todo_id,
        models.Todos.owner_id == user["id"],
    ).first()
    if todo is None:
        raise HTTPException(status_code=404, detail="Task not found")

    db.delete(todo)
    db.commit()
    return RedirectResponse(url="/todos/", status_code=status.HTTP_303_SEE_OTHER)
