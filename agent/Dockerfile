FROM registry.access.redhat.com/ubi9/python-312:latest
USER 0
WORKDIR /opt/app-root/src
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY mcp_server.py app.py ./
RUN chown -R 1001:0 /opt/app-root/src
USER 1001
ENV PYTHONUNBUFFERED=1
CMD ["python", "app.py"]
