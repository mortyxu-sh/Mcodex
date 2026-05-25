import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from app import models
from app.auth import hash_password
from app.config import get_settings
from app.database import Base, SessionLocal, engine


STAGES = [
    {
        "stage_no": 1,
        "name": "阶段一：Agent 部署",
        "description": "全员完成 AI Agent 部署，跑通基础命令并沉淀踩坑记录。",
        "award_name": "开路先锋奖",
        "award_quota": 1,
        "criteria": [
            ("部署完成度", "是否完成 AI Agent 安装配置，成功接入指定模型，并能独立运行。", 4),
            ("基础操作验证", "是否跑通文件分析、数据整理、报告生成 3 个基础操作。", 3),
            ("踩坑记录价值", "是否记录问题、解决办法、配置经验，且对他人可复用。", 3),
        ],
    },
    {
        "stage_no": 2,
        "name": "阶段二：AI 试水",
        "description": "用 AI 完成一次真实工作，打破心理门槛。",
        "award_name": "初试锋芒奖",
        "award_quota": 2,
        "criteria": [
            ("场景真实性", "是否选择真实工作场景，问题是否明确且具有代表性。", 4),
            ("AI 使用效果", "AI 是否给出有效分析、结论或产出，是否提升处理效率。", 3),
            ("心得总结质量", "100 字心得是否说明使用过程、收获、限制和改进方向。", 3),
        ],
    },
    {
        "stage_no": 3,
        "name": "阶段三：业务嵌入",
        "description": "把 AI 嵌入日常工作流，实实在在节省时间。",
        "award_name": "流程再造奖",
        "award_quota": 3,
        "criteria": [
            ("流程改造价值", "是否真正嵌入日常业务流程，减少重复劳动或提升质量。", 4),
            ("实际产出质量", "是否有可验证的产出物，例如报告、问答助手、自动填报结果。", 3),
            ("效率数据可信度", "是否提供节省时间、降低错误率、复用次数等量化数据。", 3),
        ],
    },
    {
        "stage_no": 4,
        "name": "阶段四：自由创造 + 技能分享",
        "description": "自由创新，沉淀可复用技能，全团队共享。",
        "award_name": "创新突破奖",
        "award_quota": 4,
        "criteria": [
            ("创新性与实用性", "创新点是否明确，是否解决实际工作问题，是否有推广价值。", 4),
            ("成果展示完整度", "项目说明、成果演示、效果数据是否完整清晰。", 3),
            ("技能复用价值", "技能分享卡是否让其他人可以按步骤复用。", 3),
        ],
    },
]


def seed_stages(db):
    for data in STAGES:
        stage = db.query(models.Stage).filter(models.Stage.stage_no == data["stage_no"]).first()
        if not stage:
            stage = models.Stage(
                stage_no=data["stage_no"],
                name=data["name"],
                description=data["description"],
                award_name=data["award_name"],
                award_quota=data["award_quota"],
            )
            db.add(stage)
            db.flush()
        else:
            stage.name = data["name"]
            stage.description = data["description"]
            stage.award_name = data["award_name"]
            stage.award_quota = data["award_quota"]

        existing = {criteria.name: criteria for criteria in stage.criteria}
        for order, (name, description, max_score) in enumerate(data["criteria"], start=1):
            criteria = existing.get(name)
            if not criteria:
                db.add(
                    models.ScoreCriteria(
                        stage_id=stage.id,
                        name=name,
                        description=description,
                        max_score=max_score,
                        sort_order=order,
                    )
                )
            else:
                criteria.description = description
                criteria.max_score = max_score
                criteria.sort_order = order


def seed_admin(db):
    settings = get_settings()
    password = settings.admin_password or "please-change-password"
    admin = db.query(models.User).filter(models.User.username == settings.admin_username).first()
    if not admin:
        db.add(
            models.User(
                username=settings.admin_username,
                password_hash=hash_password(password),
                display_name="系统管理员",
                role="admin",
            )
        )


def seed_players(db):
    if db.query(models.Player).count() > 0:
        return
    for index in range(1, 31):
        db.add(models.Player(name=f"选手{index:02d}", team="技术二线", group_name="", phone=""))


def main():
    settings = get_settings()
    settings.upload_path.mkdir(parents=True, exist_ok=True)
    Path("data").mkdir(exist_ok=True)
    Base.metadata.create_all(bind=engine)
    db = SessionLocal()
    try:
        seed_stages(db)
        seed_admin(db)
        seed_players(db)
        db.commit()
    finally:
        db.close()
    print("数据库初始化完成")
    print(f"管理员账号：{settings.admin_username}")


if __name__ == "__main__":
    main()
