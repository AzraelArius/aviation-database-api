# Copyright (c) BDist Development Team
# Distributed under the terms of the Modified BSD License.
FROM python:3.12-slim-bookworm
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 PYTHONPATH=/app/src
WORKDIR /app
COPY requirements.txt requirements.lock ./
RUN pip install --no-cache-dir -r requirements.txt -c requirements.lock
RUN useradd --create-home --uid 10001 aviation
COPY src ./src
COPY wsgi.py ./wsgi.py
COPY LICENSE.md ./LICENSE.md
COPY scripts ./scripts
COPY database ./database
RUN chmod +x /app/scripts/entrypoint /app/scripts/start
USER aviation
EXPOSE 8080
ENTRYPOINT ["/app/scripts/entrypoint"]
CMD ["/app/scripts/start"]
