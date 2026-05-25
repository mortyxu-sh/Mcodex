# AI先锋挑战赛评分系统

基于 FastAPI + Jinja2 + SQLAlchemy 的内部活动评分系统，支持选手提交、评委评分、公开排行榜、后台维护和 CSV 导出。

## 功能

- 公开排行榜：总榜、阶段榜、提交状态、评分人数、平均分。
- 选手提交：选择选手和阶段，填写成果说明，上传主文件和多个附件。
- 评委工作台：登录、筛选阶段、下载附件、按动态评分细则打分。
- 管理后台：维护选手、评委/管理员、阶段、评分细则、提交物状态。
- 导出：评分明细 CSV。

## 本地运行

```bash
cd ai-score-system
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
python scripts/init_db.py
uvicorn app.main:app --host 127.0.0.1 --port 8000
```

访问：

- 排行榜：`http://127.0.0.1:8000/`
- 选手提交：`http://127.0.0.1:8000/submit`
- 登录：`http://127.0.0.1:8000/login`
- 管理后台：`http://127.0.0.1:8000/admin`

初始化管理员账号来自 `.env`：

```env
ADMIN_USERNAME=admin
ADMIN_PASSWORD=please-change-password
```

生产部署前必须修改 `SECRET_KEY` 和 `ADMIN_PASSWORD`。

## 配置

`.env` 示例：

```env
APP_NAME=AI先锋挑战赛评分系统
APP_ENV=production
SECRET_KEY=please-change-this-secret
DATABASE_URL=sqlite:///./data/app.db
UPLOAD_DIR=/opt/ai-score-system/uploads
MAX_UPLOAD_SIZE_MB=100
ADMIN_USERNAME=admin
ADMIN_PASSWORD=please-change-password
```

MySQL 示例：

```env
DATABASE_URL=mysql+pymysql://ai_score:StrongPassword@127.0.0.1:3306/ai_score?charset=utf8mb4
```

## Ubuntu 部署

```bash
sudo apt update
sudo apt install -y python3 python3-venv python3-pip nginx unzip git
sudo mkdir -p /opt/ai-score-system
sudo chown -R $USER:$USER /opt/ai-score-system
```

上传代码到 `/opt/ai-score-system` 后：

```bash
cd /opt/ai-score-system
python3 -m venv .venv
source .venv/bin/activate
pip install --upgrade pip
pip install -r requirements.txt
cp .env.example .env
vim .env
mkdir -p data uploads
python scripts/init_db.py
```

配置 systemd：

```bash
sudo cp deploy/ai-score-system.service /etc/systemd/system/ai-score-system.service
sudo chown -R www-data:www-data /opt/ai-score-system
sudo systemctl daemon-reload
sudo systemctl enable ai-score-system
sudo systemctl start ai-score-system
sudo systemctl status ai-score-system
```

配置 Nginx：

```bash
sudo cp deploy/nginx_ai_score.conf /etc/nginx/sites-available/ai-score-system
sudo ln -s /etc/nginx/sites-available/ai-score-system /etc/nginx/sites-enabled/ai-score-system
sudo nginx -t
sudo systemctl reload nginx
```

常用运维：

```bash
sudo journalctl -u ai-score-system -f
sudo tail -f /var/log/nginx/error.log
sudo systemctl restart ai-score-system
```

## 安全说明

- 密码使用 bcrypt 哈希保存。
- 上传文件以 UUID 重命名，原文件名仅用于展示和下载。
- 下载接口会校验路径，避免读取上传目录外的文件。
- `/judge/*` 需要评委或管理员登录，`/admin/*` 仅管理员可访问。
- `uploads` 不应配置为可直接公开访问目录。
