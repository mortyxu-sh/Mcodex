from fastapi import APIRouter, Depends, Form, Request
from fastapi.responses import RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session

from app.auth import authenticate_user, login_user, logout_user
from app.database import get_db


router = APIRouter()
templates = Jinja2Templates(directory="app/templates")


@router.get("/login")
def login_page(request: Request):
    return templates.TemplateResponse("login.html", {"request": request, "error": ""})


@router.post("/login")
def login(request: Request, username: str = Form(...), password: str = Form(...), db: Session = Depends(get_db)):
    user = authenticate_user(db, username, password)
    if not user:
        return templates.TemplateResponse("login.html", {"request": request, "error": "账号或密码错误"}, status_code=400)
    login_user(request, user)
    target = "/admin" if user.role == "admin" else "/judge/dashboard"
    return RedirectResponse(target, status_code=303)


@router.get("/logout")
@router.get("/judge/logout")
def logout(request: Request):
    logout_user(request)
    return RedirectResponse("/", status_code=303)
