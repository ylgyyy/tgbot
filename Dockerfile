FROM python:3.13-slim

WORKDIR /app

# 安装依赖
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# 复制源码
COPY bot.py .

# 数据持久化目录
VOLUME ["/app/data"]

# 通过环境变量配置
ENV DATA_DIR=/app/data
ENV BOT_TOKEN=""
ENV OWNER_ID=""
ENV TG_PROXY=""

CMD ["python", "-u", "bot.py"]
