# CDK Box

一个轻量级的兑换码（CDK）发放管理系统。管理员创建活动并导入兑换码，用户输入用户名即可一键领取，每人每活动限领一个。

## 功能

**用户端**
- 输入用户名即可进入，无需注册
- 一键领取兑换码，支持复制
- 查看个人领取记录
- 每人每活动限领一个

**管理端**
- 创建活动、批量导入兑换码（每行一个）
- 活动补货、开启/停止
- 查看兑换码领取详情

## 快速开始

### 环境要求

- Python 3.8+

### 一键安装

```bash
git clone https://github.com/你的用户名/cdk-box.git
cd cdk-box
bash setup.sh
```

脚本会自动完成：创建虚拟环境 → 安装依赖 → 生成配置文件 → 初始化数据库。

### 启动

```bash
.venv/bin/python app.py
```

打开浏览器访问 `http://localhost:5000`

管理后台：`http://localhost:5000/admin`（默认账号 `admin` / `change-me-please`）

> 首次启动后请在 `.env` 中修改管理员密码和 SECRET_KEY。

### 生产部署

```bash
.venv/bin/gunicorn app:app -b 0.0.0.0:5000
```

## 配置说明

复制 `.env.example` 为 `.env` 并修改（一键安装脚本会自动完成）：

| 变量 | 说明 | 默认值 |
|------|------|--------|
| `ADMIN_USERNAME` | 管理员用户名 | `admin` |
| `ADMIN_PASSWORD` | 管理员密码 | `change-me-please` |
| `SECRET_KEY` | Session 密钥 | 安装时自动生成 |
| `PORT` | 监听端口 | `5000` |
| `DEBUG` | 调试模式 | `false` |

## 项目结构

```
cdk-box/
├── app.py              # 主程序
├── requirements.txt    # Python 依赖
├── setup.sh            # 一键安装脚本
├── .env.example        # 配置模板
├── static/
│   └── style.css       # 样式
└── templates/
    ├── base.html       # 基础模板
    ├── index.html      # 登录页
    ├── dashboard.html  # 用户面板
    ├── admin.html      # 管理后台
    ├── admin_detail.html  # 活动详情
    └── admin_login.html   # 管理员登录
```

## 技术栈

- Python / Flask
- SQLite（零配置，数据存储在 `data.db`）
- 原生 HTML/CSS，无前端框架

## License

MIT
