# aipassport-server

FastAPI + SQLite 后端，**bppassport 项目的服务端**。设备端固件在姊妹仓库 `bppassport`
（硬件 ESP32-C3 + ST7789P3 + ES8311，3 按键录音留言机）。

> 完整定位：[bppassport/docs/prd-voice-messenger.md](https://github.com/wangqiang1988/bppassport/blob/main/docs/prd-voice-messenger.md)
>
> HTTP 协议：[bppassport/docs/protocol.md](https://github.com/wangqiang1988/bppassport/blob/main/docs/protocol.md)（v1，本仓库实现）

## 能力

- 用户注册 / 登录（HTTP session cookie）
- 设备配对流（设备端 6 位短码 + 网页端确认）
- 录音上传 / 下载（IMA ADPCM，multipart）
- 收件箱 / 标记已读 / 删除
- 中文 Jinja 网页端（登录、收件箱、配对）

## 技术栈

| 项 | 选 |
|---|---|
| 语言 | Python 3.12 |
| 框架 | FastAPI |
| ASGI | Uvicorn |
| ORM | SQLAlchemy 2 |
| 数据库 | SQLite（MVP） |
| 模板 | Jinja2 |
| 存储 | 本地 `./voices/{yyyy-mm}/{id}.adpcm` |

## 快速开始（本地）

```bash
cd server

python3.12 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt

cp .env.example .env
# 把 SECRET_KEY 改成随机值：openssl rand -hex 32

python -m app.db init          # 建表 + 种子数据（爸爸/妈妈 账号，密码 x）

uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
```

服务起来后：

- HTTP API：`http://127.0.0.1:8000/api/v1/*`
- 网页端：`http://127.0.0.1:8000/login`
- 自动 OpenAPI：`http://127.0.0.1:8000/docs`

## Docker 部署

```bash
cd server

# 1. 生成密钥
echo "SECRET_KEY=$(openssl rand -hex 32)" > .env

# 2. 起容器
docker compose up -d --build

# 3. 验证（宿主机端口 8086 → 容器内 8000）
curl http://127.0.0.1:8086/healthz
```

数据持久化在 `./data/`（SQLite 数据库 + 录音文件）。

设备 NVS 中 `server.url` 写 `http://<服务器IP>:8086`。

## 目录结构

```
server/
├── app/
│   ├── main.py            FastAPI factory + 路由
│   ├── config.py          环境变量读取
│   ├── db.py              SQLAlchemy session + python -m app.db init
│   ├── models.py          ORM
│   ├── auth.py            密码 hash + device/web token
│   ├── templating.py      Jinja + filter
│   ├── api/               /api/v1/* 协议路由
│   │   ├── users.py       /register /login /logout
│   │   ├── me.py          /me
│   │   ├── contacts.py    /contacts
│   │   ├── pair.py        /pair/start /confirm /check + /devices/unpair
│   │   └── voices.py      /voices /voices/inbox /voices/{id}
│   ├── web/               中文 Jinja 路由
│   ├── templates/         HTML
│   └── static/css/        样式
├── voices/                录音文件（运行时生成，gitignore）
├── Dockerfile
├── docker-compose.yml
├── requirements.txt
├── .env.example
└── README.md
```

## MVP 不做（来自 [PRD §5](https://github.com/wangqiang1988/bppassport/blob/main/docs/prd-voice-messenger.md#5-显式排除mvp-不做)）

HTTPS / mTLS、WebSocket 推送、OTA、家庭组、语音转文字、E2E 加密、Web 端录音。

## 许可

MIT
