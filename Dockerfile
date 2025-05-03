FROM python:3.12.9-slim

WORKDIR /root

RUN apt-get update && apt-get install -y git  # Needed to install git packages from requirements.txt
COPY . .
RUN pip install -r requirements.txt

ENTRYPOINT ["python"]
CMD ["app.py"]
