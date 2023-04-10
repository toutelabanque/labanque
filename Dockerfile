# syntax=docker/dockerfile:1

FROM python:alpine

WORKDIR /labanque

COPY requirements.txt requirements.txt
RUN python3 -m pip install --upgrade pip
RUN pip3 install -r requirements.txt

COPY static ./static
COPY templates ./templates
COPY app.py .
COPY bank.py .
COPY config.json .
COPY consts.py .
COPY db.sqlite .

EXPOSE 443

CMD ["python3", "app.py"]
