FROM python:3.11

WORKDIR /opt

COPY requirements.txt requirements.txt


RUN  pip install --no-cache-dir --upgrade pip \
     && pip install --no-cache-dir -r requirements.txt

COPY .env .

COPY ./src ./src
