import csv
import io

from sqlalchemy.orm import Session

from app import models
from app.services.scoring import submission_stats


def scores_csv(db: Session) -> str:
    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(["阶段", "选手", "团队", "标题", "评委", "维度", "分数", "总分", "评语", "更新时间"])
    scores = (
        db.query(models.Score)
        .join(models.Submission)
        .join(models.Stage)
        .join(models.Player)
        .order_by(models.Stage.stage_no, models.Player.name, models.Score.updated_at.desc())
        .all()
    )
    for score in scores:
        for item in sorted(score.items, key=lambda i: i.criteria.sort_order):
            writer.writerow(
                [
                    score.submission.stage.name,
                    score.submission.player.name,
                    score.submission.player.team,
                    score.submission.title,
                    score.judge.display_name,
                    item.criteria.name,
                    float(item.score),
                    float(score.total_score),
                    score.comment,
                    score.updated_at.strftime("%Y-%m-%d %H:%M:%S"),
                ]
            )
    return output.getvalue()
