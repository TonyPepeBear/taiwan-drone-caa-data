FROM python:3.11-alpine
RUN apk add --no-cache wireguard-tools iproute2
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1
WORKDIR /workspace
ENTRYPOINT ["python3", "/workspace/scripts/vpn/sync.py"]
