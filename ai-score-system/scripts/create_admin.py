import getpass
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from app import models
from app.auth import hash_password
from app.database import SessionLocal


def main():
    username = input("管理员用户名: ").strip()
    display_name = input("显示名称: ").strip() or username
    password = getpass.getpass("密码: ")
    if not username or not password:
        raise SystemExit("用户名和密码不能为空")
    db = SessionLocal()
    try:
        user = db.query(models.User).filter(models.User.username == username).first()
        if user:
            user.password_hash = hash_password(password)
            user.display_name = display_name
            user.role = "admin"
            user.is_active = True
        else:
            db.add(
                models.User(
                    username=username,
                    password_hash=hash_password(password),
                    display_name=display_name,
                    role="admin",
                    is_active=True,
                )
            )
        db.commit()
    finally:
        db.close()
    print("管理员已创建或更新")


if __name__ == "__main__":
    main()
