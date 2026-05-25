from fastapi import APIRouter, Depends, Form, Request
from fastapi.responses import RedirectResponse, Response
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session

from app import models
from app.auth import hash_password, require_user
from app.database import get_db
from app.services.export import scores_csv
from app.services.scoring import submission_stats


router = APIRouter(prefix="/admin")
templates = Jinja2Templates(directory="app/templates")


def get_admin(request: Request, db: Session):
    return require_user(request, db, {"admin"})


@router.get("")
@router.get("/")
def admin_home(request: Request, db: Session = Depends(get_db)):
    user = get_admin(request, db)
    players = db.query(models.Player).order_by(models.Player.id).all()
    users = db.query(models.User).order_by(models.User.role, models.User.username).all()
    stages = db.query(models.Stage).order_by(models.Stage.stage_no).all()
    submissions = db.query(models.Submission).filter(models.Submission.is_current.is_(True)).order_by(models.Submission.submitted_at.desc()).all()
    criteria = db.query(models.ScoreCriteria).order_by(models.ScoreCriteria.stage_id, models.ScoreCriteria.sort_order).all()
    stats = {submission.id: submission_stats(db, submission.id) for submission in submissions}
    return templates.TemplateResponse(
        "admin.html",
        {
            "request": request,
            "user": user,
            "players": players,
            "users": users,
            "stages": stages,
            "submissions": submissions,
            "criteria": criteria,
            "stats": stats,
        },
    )


@router.post("/players")
def save_player(
    request: Request,
    name: str = Form(...),
    team: str = Form(""),
    group_name: str = Form(""),
    phone: str = Form(""),
    player_id: int | None = Form(None),
    is_active: str | None = Form(None),
    db: Session = Depends(get_db),
):
    get_admin(request, db)
    player = db.get(models.Player, player_id) if player_id else models.Player()
    player.name = name.strip()
    player.team = team.strip()
    player.group_name = group_name.strip()
    player.phone = phone.strip()
    player.is_active = is_active == "on" if player_id else True
    db.add(player)
    db.commit()
    return RedirectResponse("/admin#players", status_code=303)


@router.post("/users")
def save_user(
    request: Request,
    username: str = Form(...),
    display_name: str = Form(...),
    role: str = Form("judge"),
    password: str = Form(""),
    user_id: int | None = Form(None),
    is_active: str | None = Form(None),
    db: Session = Depends(get_db),
):
    get_admin(request, db)
    user = db.get(models.User, user_id) if user_id else models.User(username=username.strip(), password_hash="")
    user.username = username.strip()
    user.display_name = display_name.strip()
    user.role = role if role in {"judge", "admin"} else "judge"
    user.is_active = is_active == "on" if user_id else True
    if password:
        user.password_hash = hash_password(password)
    if not user.password_hash:
        user.password_hash = hash_password("change-me-now")
    db.add(user)
    db.commit()
    return RedirectResponse("/admin#users", status_code=303)


@router.post("/stages")
def save_stage(
    request: Request,
    stage_id: int = Form(...),
    name: str = Form(...),
    description: str = Form(""),
    award_name: str = Form(""),
    award_quota: int = Form(1),
    submit_open: str | None = Form(None),
    score_open: str | None = Form(None),
    ranking_visible: str | None = Form(None),
    db: Session = Depends(get_db),
):
    get_admin(request, db)
    stage = db.get(models.Stage, stage_id)
    stage.name = name.strip()
    stage.description = description.strip()
    stage.award_name = award_name.strip()
    stage.award_quota = award_quota
    stage.submit_open = submit_open == "on"
    stage.score_open = score_open == "on"
    stage.ranking_visible = ranking_visible == "on"
    db.commit()
    return RedirectResponse("/admin#stages", status_code=303)


@router.post("/criteria")
def save_criteria(
    request: Request,
    stage_id: int = Form(...),
    name: str = Form(...),
    description: str = Form(""),
    max_score: float = Form(...),
    sort_order: int = Form(1),
    criteria_id: int | None = Form(None),
    db: Session = Depends(get_db),
):
    get_admin(request, db)
    criteria = db.get(models.ScoreCriteria, criteria_id) if criteria_id else models.ScoreCriteria(stage_id=stage_id)
    criteria.stage_id = stage_id
    criteria.name = name.strip()
    criteria.description = description.strip()
    criteria.max_score = max_score
    criteria.sort_order = sort_order
    db.add(criteria)
    db.commit()
    return RedirectResponse("/admin#criteria", status_code=303)


@router.post("/submissions/{submission_id}/toggle")
def toggle_submission(submission_id: int, request: Request, db: Session = Depends(get_db)):
    get_admin(request, db)
    submission = db.get(models.Submission, submission_id)
    submission.is_current = not submission.is_current
    db.commit()
    return RedirectResponse("/admin#submissions", status_code=303)


@router.get("/export/scores.csv")
def export_scores(request: Request, db: Session = Depends(get_db)):
    get_admin(request, db)
    content = scores_csv(db)
    return Response(content, media_type="text/csv; charset=utf-8", headers={"Content-Disposition": "attachment; filename=scores.csv"})
