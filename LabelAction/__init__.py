import logging
import os

from azure.core.exceptions import ResourceNotFoundError
import azure.functions as func
from azure.identity import DefaultAzureCredential
from azure.storage.blob import BlobClient, ContainerClient


# Set up  logger
LOG_LEVEL = os.getenv("LOGLEVEL", "INFO")
LOG_LEVEL = LOG_LEVEL.upper()
logger = logging.getLogger()
logger.setLevel(logging.getLevelName(LOG_LEVEL))

container_label = os.environ.get("CONTAINER_LABEL", "")
blob_label = os.environ.get("BLOB_LABEL", "")


def main(msg: func.QueueMessage) -> None:
    message = msg.get_body().decode()
    logger.info(f"Label action received a queue message: {message}")
    url, policy, profile, rule = message.split(",")

    if container_label is not None and len(container_label):
        try:
            logger.info("Labeling container.")
            tags = {"DLPScanAlert": render_label(container_label, policy, profile, rule)}
            tag_container(os.path.dirname(url), **tags)
        except Exception as err:
            logger.error(f"Exception encountered running container labeling autoremediation: {err}")
            return
    else:
        logger.info("No container label defined, skipping label.")

    if blob_label is not None and len(blob_label):
        try:
            logger.info("Labeling blob.")
            tags = {"DLPScanAlert": render_label(container_label, policy, profile, rule)}
            tag_blob(url, **tags)
        except Exception as err:
            logger.error(f"Exception encountered running blob labeling autoremediation: {err}")
            return
    else:
        logger.info("No blob label defined, skipping label.")


def tag_container(resource_id, **tags):
    cred = DefaultAzureCredential()
    client = ContainerClient.from_container_url(resource_id, credential=cred)
    try:
        existing_tags = client.get_container_properties().metadata
        new_tags = {**existing_tags, **tags}
        client.set_container_metadata(new_tags)
    except ResourceNotFoundError as err:
        logger.warning(f"Could not find container resource: {err}")
        raise


def tag_blob(resource_id, **tags):
    cred = DefaultAzureCredential()
    client = BlobClient.from_blob_url(resource_id, credential=cred)
    try:
        existing_tags = client.get_blob_properties().metadata
        new_tags = {**existing_tags, **tags}
        client.set_blob_metadata(new_tags)
    except ResourceNotFoundError as err:
        logger.warning(f"Could not find blob resource: {err}")
        raise


def render_label(label, policy, profile, rule):
    tags = {}
    if "{policy}" in label:
        tags["policy"] = policy
    if "{profile}" in label:
        tags["profile"] = profile
    if "{rule}" in label:
        tags["rule"] = rule
    return label.format(**tags)
