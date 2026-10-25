FROM python:3.14-slim
WORKDIR /app
COPY requirements.lock .
RUN pip install --no-cache-dir -r requirements.lock && useradd --uid 10001 --create-home relay
COPY app ./app
COPY static ./static
COPY run.py ./run.py
RUN mkdir /data && chown relay:relay /data
USER relay
ENV APP_ENV=production HOST=0.0.0.0 PORT=8787 DATABASE_PATH=/data/relay.sqlite
EXPOSE 8787
HEALTHCHECK --interval=30s --timeout=3s CMD python -c "import os,urllib.request,urllib.parse; h=urllib.parse.urlsplit(os.environ['PUBLIC_ORIGIN']).netloc; urllib.request.urlopen(urllib.request.Request('http://127.0.0.1:8787/health',headers={'Host':h}),timeout=2)"
CMD ["python", "run.py"]
