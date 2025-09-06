FROM python:3.13-alpine
WORKDIR /tasmota-tuya-mqtt-bridge
COPY . .
RUN adduser -D jerkapi
USER jerkapi
CMD ["python3.13", "./main.py"]