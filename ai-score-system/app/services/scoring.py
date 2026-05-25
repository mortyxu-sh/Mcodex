from dataclasses import dataclass
from datetime import datetime

from sqlalchemy import func
from sqlalchemy.orm import Session

from app import models


@dataclass
class RankingRow:
    rank: int | str
    player: models.Player
    avg_score: float | None
    judge_count: int
    submit_status: str
    updated_at: datetime | None
    stage_scores: dict[int, float]


def submission_stats(db: Session, submission_id: int) -> tuple[float | None, int]:
    avg_score, judge_count = (
        db.query(func.avg(models.Score.total_score), func.count(models.Score.id))
        .filter(models.Score.submission_id == submission_id)
        .one()
    )
    return (round(float(avg_score), 2) if avg_score is not None else None, int(judge_count or 0))


def get_current_submission(db: Session, player_id: int, stage_id: int) -> models.Submission | None:
    return (
        db.query(models.Submission)
        .filter(
            models.Submission.player_id == player_id,
            models.Submission.stage_id == stage_id,
            models.Submission.is_current.is_(True),
        )
        .first()
    )


def stage_ranking(db: Session, stage_id: int) -> list[RankingRow]:
    players = db.query(models.Player).filter(models.Player.is_active.is_(True)).order_by(models.Player.id).all()
    rows: list[RankingRow] = []
    for player in players:
        submission = get_current_submission(db, player.id, stage_id)
        if not submission:
            rows.append(RankingRow("-", player, None, 0, "未提交", None, {}))
            continue
        avg_score, judge_count = submission_stats(db, submission.id)
        status = "待评分" if judge_count == 0 else "已评分"
        rows.append(RankingRow("-", player, avg_score, judge_count, status, submission.submitted_at, {}))
    return _with_ranks(rows)


def total_ranking(db: Session) -> list[RankingRow]:
    stages = db.query(models.Stage).filter(models.Stage.ranking_visible.is_(True)).order_by(models.Stage.stage_no).all()
    players = db.query(models.Player).filter(models.Player.is_active.is_(True)).order_by(models.Player.id).all()
    rows: list[RankingRow] = []
    for player in players:
        scores: dict[int, float] = {}
        judge_total = 0
        latest = None
        has_submission = False
        for stage in stages:
            submission = get_current_submission(db, player.id, stage.id)
            if not submission:
                continue
            has_submission = True
            latest = max(latest, submission.submitted_at) if latest else submission.submitted_at
            avg_score, judge_count = submission_stats(db, submission.id)
            judge_total += judge_count
            if avg_score is not None:
                scores[stage.id] = avg_score
        avg = round(sum(scores.values()) / len(scores), 2) if scores else None
        if not has_submission:
            status = "未提交"
        elif avg is None:
            status = "待评分"
        else:
            status = "已评分"
        rows.append(RankingRow("-", player, avg, judge_total, status, latest, scores))
    return _with_ranks(rows)


def _with_ranks(rows: list[RankingRow]) -> list[RankingRow]:
    rows.sort(key=lambda item: (item.avg_score is not None, item.avg_score or -1), reverse=True)
    rank = 0
    previous = None
    for index, row in enumerate(rows, start=1):
        if row.avg_score is None:
            row.rank = "-"
            continue
        if row.avg_score != previous:
            rank = index
            previous = row.avg_score
        row.rank = rank
    return rows
