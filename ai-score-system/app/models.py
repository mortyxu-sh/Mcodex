from datetime import datetime

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, Numeric, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class TimestampMixin:
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)


class User(TimestampMixin, Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    username: Mapped[str] = mapped_column(String(64), unique=True, index=True, nullable=False)
    password_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    display_name: Mapped[str] = mapped_column(String(100), nullable=False)
    role: Mapped[str] = mapped_column(String(20), default="judge", nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    scores: Mapped[list["Score"]] = relationship(back_populates="judge")


class Player(TimestampMixin, Base):
    __tablename__ = "players"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    team: Mapped[str] = mapped_column(String(100), default="", nullable=False)
    group_name: Mapped[str] = mapped_column(String(100), default="", nullable=False)
    phone: Mapped[str] = mapped_column(String(50), default="", nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    submissions: Mapped[list["Submission"]] = relationship(back_populates="player")


class Stage(Base):
    __tablename__ = "stages"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    stage_no: Mapped[int] = mapped_column(Integer, unique=True, nullable=False)
    name: Mapped[str] = mapped_column(String(120), nullable=False)
    description: Mapped[str] = mapped_column(Text, default="", nullable=False)
    award_name: Mapped[str] = mapped_column(String(120), default="", nullable=False)
    award_quota: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    submit_open: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    score_open: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    ranking_visible: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    criteria: Mapped[list["ScoreCriteria"]] = relationship(back_populates="stage", cascade="all, delete-orphan")
    submissions: Mapped[list["Submission"]] = relationship(back_populates="stage")


class Submission(Base):
    __tablename__ = "submissions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    player_id: Mapped[int] = mapped_column(ForeignKey("players.id"), nullable=False)
    stage_id: Mapped[int] = mapped_column(ForeignKey("stages.id"), nullable=False)
    title: Mapped[str] = mapped_column(String(200), nullable=False)
    description: Mapped[str] = mapped_column(Text, default="", nullable=False)
    is_current: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    submitted_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)

    player: Mapped[Player] = relationship(back_populates="submissions")
    stage: Mapped[Stage] = relationship(back_populates="submissions")
    files: Mapped[list["SubmissionFile"]] = relationship(back_populates="submission", cascade="all, delete-orphan")
    scores: Mapped[list["Score"]] = relationship(back_populates="submission", cascade="all, delete-orphan")


class SubmissionFile(Base):
    __tablename__ = "submission_files"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    submission_id: Mapped[int] = mapped_column(ForeignKey("submissions.id"), nullable=False)
    original_name: Mapped[str] = mapped_column(String(255), nullable=False)
    stored_name: Mapped[str] = mapped_column(String(255), nullable=False)
    file_path: Mapped[str] = mapped_column(String(500), nullable=False)
    file_type: Mapped[str] = mapped_column(String(100), default="", nullable=False)
    file_size: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    uploaded_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)

    submission: Mapped[Submission] = relationship(back_populates="files")


class ScoreCriteria(Base):
    __tablename__ = "score_criteria"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    stage_id: Mapped[int] = mapped_column(ForeignKey("stages.id"), nullable=False)
    name: Mapped[str] = mapped_column(String(120), nullable=False)
    description: Mapped[str] = mapped_column(Text, default="", nullable=False)
    max_score: Mapped[float] = mapped_column(Numeric(5, 2), nullable=False)
    sort_order: Mapped[int] = mapped_column(Integer, default=1, nullable=False)

    stage: Mapped[Stage] = relationship(back_populates="criteria")
    score_items: Mapped[list["ScoreItem"]] = relationship(back_populates="criteria")


class Score(Base):
    __tablename__ = "scores"
    __table_args__ = (UniqueConstraint("submission_id", "judge_id", name="uk_score_submission_judge"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    submission_id: Mapped[int] = mapped_column(ForeignKey("submissions.id"), nullable=False)
    judge_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False)
    total_score: Mapped[float] = mapped_column(Numeric(5, 2), nullable=False)
    comment: Mapped[str] = mapped_column(Text, default="", nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

    submission: Mapped[Submission] = relationship(back_populates="scores")
    judge: Mapped[User] = relationship(back_populates="scores")
    items: Mapped[list["ScoreItem"]] = relationship(back_populates="score_record", cascade="all, delete-orphan")


class ScoreItem(Base):
    __tablename__ = "score_items"
    __table_args__ = (UniqueConstraint("score_id", "criteria_id", name="uk_score_item_criteria"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    score_id: Mapped[int] = mapped_column(ForeignKey("scores.id"), nullable=False)
    criteria_id: Mapped[int] = mapped_column(ForeignKey("score_criteria.id"), nullable=False)
    score: Mapped[float] = mapped_column(Numeric(5, 2), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)

    score_record: Mapped[Score] = relationship(back_populates="items")
    criteria: Mapped[ScoreCriteria] = relationship(back_populates="score_items")
