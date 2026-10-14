FROM python:3.12.12-alpine
RUN pip install --no-cache-dir httpx==0.28.1 anyio==4.15.1 certifi==2026.7.22 httpcore==1.0.9 idna==3.20 h11==0.16.0 sniffio==1.3.1 typing-extensions==4.16.0
RUN addgroup -S checks && adduser -S checks -G checks
WORKDIR /checks
COPY orchestrator/acceptance.py /checks/acceptance.py
COPY infra/acceptance/main.py /checks/main.py
COPY infra/acceptance/bridge.py /checks/bridge.py
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1
USER checks
ENTRYPOINT ["python"]
CMD ["/checks/main.py"]
