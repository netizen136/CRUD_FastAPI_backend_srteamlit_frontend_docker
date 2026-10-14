FROM python:3.12-slim

WORKDIR /app

# Copy dependency metadata first. Docker can reuse the installed-dependencies
# layer when application code changes but the requirements stay the same.
# Copying all of app/ first would work, but every code edit would invalidate
# this layer and rerun pip install on the next build.
COPY app/requirements.txt ./requirements.txt
RUN pip install --no-cache-dir -r requirements.txt \
    "uvicorn[standard]" \
    "psycopg[binary]" \
    python-multipart

# Copy application source after installing dependencies. .dockerignore keeps
# local files such as app/.env out of the image build context.
COPY app/ ./app/

# EXPOSE is Optional metadata/documentation for the ports used by the apps.
# EXPOSE does not publish ports; use `docker run -p HOST_PORT:CONTAINER_PORT`.
EXPOSE 8000 8051

# Default container command: start FastAPI on port 8000.
# To run Streamlit from this same image, override CMD after the image name:
# python -m streamlit run app/frontend_streamlit.py
#   --server.address=0.0.0.0 --server.port=8051
CMD ["python", "-m", "uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
