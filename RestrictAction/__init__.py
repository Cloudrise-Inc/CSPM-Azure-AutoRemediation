import logging
import os

from azure.core.exceptions import ResourceNotFoundError
import azure.functions as func
from azure.identity import DefaultAzureCredential
from azure.storage.blob import ContainerClient, PublicAccess


# Set up  logger
LOG_LEVEL = os.getenv("LOGLEVEL", "INFO")
LOG_LEVEL = LOG_LEVEL.upper()
logger = logging.getLogger()
logger.setLevel(logging.getLevelName(LOG_LEVEL))


def main(msg: func.QueueMessage) -> None:
    message = msg.get_body().decode()
    logger.info(f"Restrict action received a queue message: {message}")
    url, _, _, _ = message.split(",")

    try:
        logger.info(f"Artifact {url} exists beginning access restriction.")
        restrict_access(url)
        logger.info(f"Remediation was successfully invoked restrict access action on {url}.")
    except Exception as err:
        logger.error(f"Exception encountered running restrict access action: {err}")


def restrict_access(resource_id):
    cred = DefaultAzureCredential()
    client = ContainerClient.from_container_url(os.path.dirname(resource_id), credential=cred)
    try:
        policy = client.get_container_access_policy()
        client.set_container_access_policy(signed_identifiers=policy, public_access=PublicAccess.OFF)
    except ResourceNotFoundError as err:
        logger.warning(f"Could not find container for resource: {resource_id} with {err}")
        raise
