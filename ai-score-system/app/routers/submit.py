from fastapi import APIRouter, Depends, File, Form, Request, UploadFile
from fastapi.responses import RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session

from app import models
from app.database import get_db
from app.services.upload import save_upload_file


router = APIRouter()
templates = Jinja2Templates(directory="app/templates")


@router.get("/submit")
def submit_form(request: Request, db: Session = Depends(get_db)):
    players = db.query(models.Player).filter(models.Player.is_active.is_(True)).order_by(models.Player.name).all()
    stages = db.query(models.Stage).filter(models.Stage.submit_open.is_(True)).order_by(models.Stage.stage_no).all()
    return templates.TemplateResponse("submit.html", {"request": request, "players": players, "stages": stages})


@router.post("/submit")
def submit_work(
    request: Request,
    player_id: int = Form(...),
    stage_id: int = Form(...),
    title: str = Form(...),
    description: str = Form(""),
    main_file: UploadFile = File(...),
    extra_files: list[UploadFile] = File(default=[]),
    db: Session = Depends(get_db),
):
    stage = db.get(models.Stage, stage_id)
    if not stage or not stage.submit_open:
        return templates.TemplateResponse("message.html", {"request": request, "title": "提交失败", "message": "该阶段未开放提交"}, status_code=400)
    old_items = (
        db.query(models.Submission)
        .filter(models.Submission.player_id == player_id, models.Submission.stage_id == stage_id, models.Submission.is_current.is_(True))
        .all()
    )
    for old in old_items:
        old.is_current = False
    submission = models.Submission(player_id=player_id, stage_id=stage_id, title=title.strip(), description=description.strip(), is_current=True)
    db.add(submission)
    db.flush()

    for upload in [main_file, *[item for item in extra_files if item.filename]]:
        original, stored, file_path, size = save_upload_file(upload, f"submission_{submission.id}")
        db.add(
            models.SubmissionFile(
                submission_id=submission.id,
                original_name=original,
                stored_name=stored,
                file_path=file_path,
                file_type=upload.content_type or "",
                file_size=size,
            )
        )
    db.commit()
    return templates.TemplateResponse("submit_success.html", {"request": request, "submission": submission})
