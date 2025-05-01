import json
import os

import boto3

QUEUE_URL = os.getenv("SQS_QUEUE_URL")

sqs = boto3.client("sqs", region_name="us-east-2")


def enviar_placa_a_sqs(placa: str, telefono: str):
    mensaje = {
        "plate": placa.upper(),
        "user": telefono,
    }

    sqs.send_message(QueueUrl=QUEUE_URL, MessageBody=json.dumps(mensaje))
    print(f"📨 Placa enviada a SQS: {placa} de {telefono}")
