FROM python:3.11

WORKDIR /opt

COPY requirements.txt requirements.txt


RUN  pip install --upgrade pip \
     && pip install -r requirements.txt

COPY .env .

COPY ./src ./src

CMD ["gunicorn", "-b", "0.0.0.0:8080", "-w", "1", "-k", "uvicorn.workers.UvicornWorker", "src.main:app"]
