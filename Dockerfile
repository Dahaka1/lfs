FROM python:3.11

WORKDIR /usr/src/app

COPY requirements.txt .

RUN pip install -r requirements.txt

COPY . .

ENV docker=true

CMD python main.py