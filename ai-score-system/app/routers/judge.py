from datetime import datetime

from fastapi import APIRouter, Depends, Form, Request
from fastapi.responses import FileResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session

from app import models
from app.auth import require_user
from app.database import get_db
from app.services.scoring import submission_stats
from app.services.upload import safe_file_path


router = APIRouter(prefix="/judge")
templates = Jinja2Templates(directory="app/templates")


def get_judge(request: Request, db: Session):
    return require_user(request, db, {"judge", "admin"})


@router.get("/dashboard")
def dashboard(request: Request, stage_id: int | None = None, db: Session = Depends(get_db)):
    user = get_judge(request, db)
    stages = db.query(models.Stage).order_by(models.Stage.stage_no).all()
    query = db.query(models.Submission).filter(models.Submission.is_current.is_(True)).join(models.Stage).join(models.Player)
    if stage_id:
        query = query.filter(models.Submission.stage_id == stage_id)
    submissions = query.order_by(models.Stage.stage_no, models.Submission.submitted_at.desc()).all()
    stats = {}
    my_scores = {}
    for submission in submissions:
        stats[submission.id] = submission_stats(db, submission.id)
        my_scores[submission.id] = (
            db.query(models.Score)
            .filter(models.Score.submission_id == submission.id, models.Score.judge_id == user.id)
            .first()
        )
    return templates.TemplateResponse(
        "judge_dashboard.html",
        {"request": request, "user": user, "stages": stages, "submissions": submissions, "stats": stats, "my_scores": my_scores, "stage_id": stage_id},
    )


@router.get("/submissions/{submission_id}/score")
def score_page(request: Request, submission_id: int, db: Session = Depends(get_db)):
    user = get_judge(request, db)
    submission = db.get(models.Submission, submission_id)
    criteria = db.query(models.ScoreCriteria).filter(models.ScoreCriteria.stage_id == submission.stage_id).order_by(models.ScoreCriteria.sort_order).all()
    score = db.query(models.Score).filter(models.Score.submission_id == submission.id, models.Score.judge_id == user.id).first()
    values = {item.criteria_id: float(item.score) for item in score.items} if score else {}
    avg_score, judge_count = submission_stats(db, submission.id)
    return templates.TemplateResponse(
        "score_form.html",
        {"request": request, "user": user, "submission": submission, "criteria": criteria, "score": score, "values": values, "avg_score": avg_score, "judge_count": judge_count},
    )


@router.post("/submissions/{submission_id}/score")
async def save_score(request: Request, submission_id: int, comment: str = Form(...), db: Session = Depends(get_db)):
    user = get_judge(request, db)
    submission = db.get(models.Submission, submission_id)
    if not submission.stage.score_open:
        return templates.TemplateResponse("message.html", {"request": request, "title": "评分失败", "message": "该阶段未开放评分"}, status_code=400)
    form = await request.form()
    criteria = db.query(models.ScoreCriteria).filter(models.ScoreCriteria.stage_id == submission.stage_id).order_by(models.ScoreCriteria.sort_order).all()
    values = {}
    total = 0.0
    for item in criteria:
        raw = form.get(f"criteria_{item.id}", "0")
        value = float(raw)
        if value < 0 or value > float(item.max_score):
            return templates.TemplateResponse("message.html", {"request": request, "title": "评分失败", "message": f"{item.name} 超出允许范围"}, status_code=400)
        values[item.id] = value
        total += value

    score = db.query(models.Score).filter(models.Score.submission_id == submission_id, models.Score.judge_id == user.id).first()
    if not score:
        score = models.Score(submission_id=submission_id, judge_id=user.id, total_score=total, comment=comment.strip())
        db.add(score)
        db.flush()
    else:
        score.total_score = total
        score.comment = comment.strip()
        score.updated_at = datetime.utcnow()
        score.items.clear()
        db.flush()
    for criteria_id, value in values.items():
        db.add(models.ScoreItem(score_id=score.id, criteria_id=criteria_id, score=value))
    db.commit()
    return RedirectResponse("/judge/dashboard", status_code=303)


@router.get("/download/{file_id}")
def download(file_id: int, request: Request, db: Session = Depends(get_db)):
    get_judge(request, db)
    file = db.get(models.SubmissionFile, file_id)
    path = safe_file_path(file.file_path)
    return FileResponse(path, media_type=file.file_type or "application/octet-stream", filename=file.original_name)
