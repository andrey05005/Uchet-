from datetime import datetime
from typing import Optional

from fastapi import Depends, FastAPI, Form, HTTPException, Request
from fastapi.responses import RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from sqlalchemy import func
from sqlalchemy.orm import Session

from auth import SESSION_COOKIE, create_session_token, hash_password, read_session_token, verify_password
from db import Base, SessionLocal, engine
from models import DebtGroup, DebtItem, User

Base.metadata.create_all(bind=engine)

app = FastAPI()
app.mount("/static", StaticFiles(directory="static"), name="static")

templates = Jinja2Templates(directory="templates")


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def get_current_user(request: Request, db: Session = Depends(get_db)) -> User:
    token = request.cookies.get(SESSION_COOKIE)
    if not token:
        raise HTTPException(status_code=401)
    user_id = read_session_token(token)
    if not user_id:
        raise HTTPException(status_code=401)
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=401)
    return user


def require_user(request: Request, db: Session = Depends(get_db)) -> User:
    try:
        return get_current_user(request, db)
    except HTTPException:
        raise HTTPException(status_code=302, headers={"Location": "/login"})


@app.get("/")
async def root():
    return RedirectResponse("/dashboard")


@app.get("/register")
async def register_page(request: Request):
    return templates.TemplateResponse("register.html", {"request": request, "error": None})


@app.post("/register")
async def register(request: Request, username: str = Form(...), password: str = Form(...), db: Session = Depends(get_db)):
    existing = db.query(User).filter(User.username == username).first()
    if existing:
        return templates.TemplateResponse(
            "register.html",
            {"request": request, "error": "Это имя уже занято."},
            status_code=400,
        )
    user = User(username=username, password_hash=hash_password(password))
    db.add(user)
    db.commit()
    db.refresh(user)
    token = create_session_token(user.id)
    response = RedirectResponse("/dashboard", status_code=302)
    response.set_cookie(
        SESSION_COOKIE,
        token,
        httponly=True,
        samesite="lax",
    )
    return response


@app.get("/login")
async def login_page(request: Request):
    return templates.TemplateResponse("login.html", {"request": request, "error": None})


@app.post("/login")
async def login(request: Request, username: str = Form(...), password: str = Form(...), db: Session = Depends(get_db)):
    user = db.query(User).filter(User.username == username).first()
    if not user or not verify_password(password, user.password_hash):
        return templates.TemplateResponse(
            "login.html",
            {"request": request, "error": "Неверный логин или пароль."},
            status_code=400,
        )
    token = create_session_token(user.id)
    response = RedirectResponse("/dashboard", status_code=302)
    response.set_cookie(
        SESSION_COOKIE,
        token,
        httponly=True,
        samesite="lax",
    )
    return response


@app.post("/logout")
async def logout():
    response = RedirectResponse("/login", status_code=302)
    response.delete_cookie(SESSION_COOKIE)
    return response


@app.get("/dashboard")
async def dashboard(request: Request, db: Session = Depends(get_db), user: User = Depends(require_user)):
    group_balances = (
        db.query(DebtGroup, func.coalesce(func.sum(DebtItem.amount), 0.0))
        .outerjoin(DebtItem, DebtItem.group_id == DebtGroup.id)
        .filter(DebtGroup.user_id == user.id)
        .group_by(DebtGroup.id)
        .order_by(DebtGroup.created_at.desc())
        .all()
    )
    total_balance = (
        db.query(func.coalesce(func.sum(DebtItem.amount), 0.0))
        .filter(DebtItem.user_id == user.id)
        .scalar()
        or 0.0
    )
    return templates.TemplateResponse(
        "dashboard.html",
        {
            "request": request,
            "user": user,
            "groups": group_balances,
            "total_balance": total_balance,
        },
    )


@app.post("/groups")
async def create_group(name: str = Form(...), db: Session = Depends(get_db), user: User = Depends(require_user)):
    group = DebtGroup(user_id=user.id, name=name)
    db.add(group)
    db.commit()
    return RedirectResponse("/dashboard", status_code=302)


@app.get("/groups/{group_id}")
async def group_detail(request: Request, group_id: int, db: Session = Depends(get_db), user: User = Depends(require_user)):
    group = db.query(DebtGroup).filter(DebtGroup.id == group_id, DebtGroup.user_id == user.id).first()
    if not group:
        raise HTTPException(status_code=404)
    items = (
        db.query(DebtItem)
        .filter(DebtItem.group_id == group.id, DebtItem.user_id == user.id)
        .order_by(DebtItem.created_at.desc())
        .all()
    )
    balance = sum(item.amount for item in items)
    return templates.TemplateResponse(
        "group.html",
        {
            "request": request,
            "user": user,
            "group": group,
            "items": items,
            "balance": balance,
        },
    )


@app.post("/groups/{group_id}/items")
async def add_item(
    group_id: int,
    amount: float = Form(...),
    note: Optional[str] = Form(None),
    db: Session = Depends(get_db),
    user: User = Depends(require_user),
):
    group = db.query(DebtGroup).filter(DebtGroup.id == group_id, DebtGroup.user_id == user.id).first()
    if not group:
        raise HTTPException(status_code=404)
    item = DebtItem(user_id=user.id, group_id=group.id, amount=amount, note=note)
    db.add(item)
    db.commit()
    return RedirectResponse(f"/groups/{group.id}", status_code=302)


@app.post("/groups/{group_id}/items/{item_id}/delete")
async def delete_item(
    group_id: int,
    item_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(require_user),
):
    item = (
        db.query(DebtItem)
        .filter(
            DebtItem.id == item_id,
            DebtItem.group_id == group_id,
            DebtItem.user_id == user.id,
        )
        .first()
    )
    if not item:
        raise HTTPException(status_code=404)
    db.delete(item)
    db.commit()
    return RedirectResponse(f"/groups/{group_id}", status_code=302)


@app.post("/groups/{group_id}/delete")
async def delete_group(
    group_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(require_user),
):
    group = db.query(DebtGroup).filter(DebtGroup.id == group_id, DebtGroup.user_id == user.id).first()
    if not group:
        raise HTTPException(status_code=404)
    db.delete(group)
    db.commit()
    return RedirectResponse("/dashboard", status_code=302)


@app.get("/health")
async def health():
    return {"status": "ok", "time": datetime.utcnow().isoformat()}
