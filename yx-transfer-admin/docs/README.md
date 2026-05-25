# 营销大并发管理门户初版

## 目标

基于附件运维文档中的转接外呼服务，设计一个前端管理页面，支持：

- 客户查询、添加、删除
- 被叫黑名单 / 白名单查询、添加、删除、批量导入、导出 CSV、同步 Redis
- 主叫鉴权白名单查询、添加、删除、同步 Redis
- Nginx 反向代理访问
- Python FastAPI 编码，作为前端管理门户与 8098 Java 后端之间的代理层

## 附件文档中提取的关键接口

后端 Java 服务默认端口：`8098`。

| 功能 | 后端接口前缀 | 说明 |
|---|---|---|
| 客户管理 | `/transfer/customer` | 客户账号、余额、单价、付费方式、频控、状态 |
| 主叫白名单 | `/transfer/auth` | 主叫鉴权白名单，DB + Redis 同步 |
| 被叫黑白名单 | `/transfer/numberlist` | 推荐 DB 持久化接口，自动同步 Redis |
| 禁止时段 | `/transfer/forbidden-time` | 本初版暂未做页面，可后续增加 |
| 被叫频次 | `/transfer/freq` | 本初版暂未做页面，可后续增加 |
| 话单查询 | `/transfer/cdr` | 本初版暂未做页面，可后续增加 |

## 目录说明

```text
yx-transfer-admin/
├── app/
│   ├── main.py              # FastAPI 后端代理接口
│   ├── config.py            # 环境变量配置
│   └── static/
│       ├── index.html       # 单页面前端
│       ├── app.js           # 前端逻辑
│       └── style.css        # 页面样式
├── nginx/
│   └── yx-transfer-admin.conf
├── scripts/
│   └── run.sh
├── .env.example
└── requirements.txt
```

## 启动方式

```bash
cd yx-transfer-admin
cp .env.example .env
# 修改 TRANSFER_API_BASE 为真实 8098 服务地址，例如：
# TRANSFER_API_BASE=http://192.168.10.61:8098
bash scripts/run.sh
```

直接访问：

```text
http://<python-server-ip>:18098/
```

通过 Nginx 访问：

```bash
cp nginx/yx-transfer-admin.conf /usr/local/nginx/conf/conf.d/
/usr/local/nginx/sbin/nginx -t
/usr/local/nginx/sbin/nginx -s reload
```

访问：

```text
http://<nginx-ip>:18080/yx-admin/
```

## 当前已完成能力

- 客户管理支持分页查询、添加、编辑、启用/禁用、余额调整、删除。
- 被叫黑白名单支持分页查询、添加、删除、导出 CSV、同步 Redis。
- 被叫黑白名单批量导入支持 `txt`、`csv`、`xlsx`，导入后展示成功/失败明细，并可下载失败列表。
- 主叫白名单支持分页查询、添加、删除、同步 Redis。
- 前端删除、启停、同步等高风险操作增加统一确认弹窗，接口错误统一 toast 提示。
- 后端补充 pytest 测试，mock 8098 后端接口验证代理与批量导入逻辑。

## 测试

```bash
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt
.venv/bin/python -m pytest -q
node --check app/static/app.js
```

## 交给 Codex 的建议任务

1. 根据真实后端返回结构，统一 `rowsOf()` 解析逻辑和分页控件。
2. 为客户管理增加编辑弹窗、充值余额、禁用/启用功能。
3. 被叫黑白名单批量导入增加失败明细下载，支持 xlsx 解析。
4. 增加登录认证、操作审计日志、权限区分。
5. 增加禁止呼出时段、频控查询、话单查询页面。
6. 增加 pytest 单元测试和接口 mock。
7. 将前端拆成 Vue 或 React 项目；当前版本是便于快速上线的原生 HTML/JS。

## Codex 提示词

```text
请基于当前 yx-transfer-admin 项目继续开发。项目背景：营销大并发转接外呼系统，后端 Java 服务端口 8098，已有接口 /transfer/customer、/transfer/auth、/transfer/numberlist。Python FastAPI 作为管理门户代理层，前端是 app/static/index.html + app.js + style.css。

优先任务：
1. 保持现有接口兼容，增加分页组件。
2. 增加客户编辑、启停、余额调整功能。
3. 优化被叫黑白名单批量导入：支持 txt/csv/xlsx，展示成功/失败明细，可下载失败列表。
4. 增加操作确认弹窗和统一错误提示。
5. 补充 pytest 测试，mock 8098 后端接口。

注意：不要直接连接生产数据库，所有增删改都通过 8098 后端接口；Nginx 仅代理到 Python 服务。
```
