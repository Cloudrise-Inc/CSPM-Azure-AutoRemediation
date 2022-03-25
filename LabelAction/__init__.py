import logging
import os

import azure.functions as func
from azure.identity import DefaultAzureCredential
from azure.storage.blob import BlobClient


# Set up  logger
LOG_LEVEL = os.getenv("LOGLEVEL", "INFO")
LOG_LEVEL = LOG_LEVEL.upper()
logger = logging.getLogger()
logger.setLevel(logging.getLevelName(LOG_LEVEL))

container_label = os.environ.get("CONTAINER_LABEL", "")
object_albel = os.environ.get("OBJECT_LABEL", "")


def main(msg: func.QueueMessage) -> None:
    message = msg.get_body().decode()
    logger.info(f"Python queue trigger function processed a queue item: {message}")

    url, policy, profile, rule = message.split(",")
    cred = DefaultAzureCredential()
    client = BlobClient.from_blob_url(url, credential=cred)
    props = client.get_blob_properties()
    print(props.metadata)

    # TODO: nstantiate container and blob client and apply labels
