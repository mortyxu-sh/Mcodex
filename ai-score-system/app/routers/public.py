from fastapi import APIRouter, Depends, Request
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session

from app import models
from app.database import get_db
from app.services.scoring import stage_ranking, total_ranking


router = APIRouter()
templates = Jinja2Templates(directory="app/templates")


@router.get("/")
@router.get("/ranking")
def ranking(request: Request, stage_id: int | None = None, db: Session = Depends(get_db)):
    stages = db.query(models.Stage).filter(models.Stage.ranking_visible.is_(True)).order_by(models.Stage.stage_no).all()
    selected_stage = db.get(models.Stage, stage_id) if stage_id else None
    rows = stage_ranking(db, selected_stage.id) if selected_stage else total_ranking(db)
    total_players = db.query(models.Player).filter(models.Player.is_active.is_(True)).count()
    current_submission_count = db.query(models.Submission).filter(models.Submission.is_current.is_(True)).count()
    scored_submission_count = db.query(models.Score.submission_id).distinct().count()
    return templates.TemplateResponse(
        "ranking.html",
        {
            "request": request,
            "stages": stages,
            "selected_stage": selected_stage,
            "rows": rows,
            "total_players": total_players,
            "current_submission_count": current_submission_count,
            "scored_submission_count": scored_submission_count,
        },
    )
