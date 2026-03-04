#!/usr/bin/env bash
set -e

echo "========================================="
echo "  CDK Box 一键安装脚本"
echo "========================================="

# 检查 Python
if ! command -v python3 &> /dev/null; then
    echo "❌ 未找到 python3，请先安装 Python 3.8+"
    exit 1
fi

echo "✅ Python: $(python3 --version)"

# 创建虚拟环境
if [ ! -d ".venv" ]; then
    echo "📦 创建虚拟环境..."
    python3 -m venv .venv
fi

echo "📦 安装依赖..."
.venv/bin/pip install -q -r requirements.txt

# 生成 .env（如果不存在）
if [ ! -f ".env" ]; then
    echo "⚙️  生成配置文件..."
    SECRET=$(python3 -c "import secrets; print(secrets.token_hex(24))")
    sed "s/change-this-to-a-random-string/$SECRET/" .env.example > .env
    echo "⚠️  请编辑 .env 修改管理员密码"
fi

# 初始化数据库
echo "🗄️  初始化数据库..."
.venv/bin/python -c "from app import init_db; init_db()"

echo ""
echo "========================================="
echo "  ✅ 安装完成！"
echo "========================================="
echo ""
echo "  启动命令:  .venv/bin/python app.py"
echo "  访问地址:  http://localhost:8099"
echo "  管理后台:  http://localhost:8099/admin"
echo ""
echo "  生产部署:  .venv/bin/gunicorn app:app -b 0.0.0.0:8099"
echo ""
