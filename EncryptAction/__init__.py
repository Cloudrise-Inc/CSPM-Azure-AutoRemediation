from io import BytesIO
import logging
import os

from azure.core.exceptions import ResourceExistsError, ResourceNotFoundError
import azure.functions as func
from azure.identity import DefaultAzureCredential
from azure.storage.blob import BlobClient


# Set up  logger
LOG_LEVEL = os.getenv("LOGLEVEL", "INFO")
LOG_LEVEL = LOG_LEVEL.upper()
logger = logging.getLogger()
logger.setLevel(logging.getLevelName(LOG_LEVEL))

tombstone_content = os.environ.get(
    "DELETE_TOMBSTONE_CONTENT",
    "This object has been deleted due to security policy.\nPolicy: {policy}\nProfile: {profile}\nRule: {rule}",
)


def main(msg: func.QueueMessage) -> None:
    message = msg.get_body().decode()
    logger.info(f"Delete action received a queue message: {message}")
    url, policy, profile, rule = message.split(",")

    if artifact_exists(url):
        try:
            logger.info(f"Artifact {url} exists beginning delete.")
            write_tombstone(url, policy, profile, rule)
            delete_artifact(url)
            logger.info(f"Remediation was successfully invoked deleting {url}.")
        except Exception as err:
            logger.error(f"Exception encountered running Delete autoremediation: {err}")
    else:
        logger.info("Artifact no longer exists in bucket.")
        logger.info(f"Remediation complete for {url}.")


def artifact_exists(resource_id):
    cred = DefaultAzureCredential()
    client = BlobClient.from_blob_url(resource_id, credential=cred)
    return client.exists()


def write_tombstone(resource_id, policy, profile, rule):
    logger.info(f"Writing tombstone {resource_id}.txt.")
    cred = DefaultAzureCredential()
    tombstone = f"{resource_id}.txt"
    client = BlobClient.from_blob_url(tombstone, credential=cred)
    content = render_content(tombstone_content, policy, profile, rule)
    logger.debug(f"Content: {content}")
    data = BytesIO(content.encode())
    try:
        client.upload_blob(data, blob_type="BlockBlob")
        logger.info("Wrote tombstone.")
    except ResourceExistsError:
        logger.warning(f"Tombstone artifact {tombstone} already exists.")


def delete_artifact(resource_id):
    cred = DefaultAzureCredential()
    try:
        del_client = BlobClient.from_blob_url(resource_id, credential=cred)
        del_client.delete_blob()
    except ResourceNotFoundError as err:
        logger.warning(f"Error deleting artifact {resource_id} with error {err}")


def render_content(template, policy, profile, rule):
    tags = {}
    if "{policy}" in template:
        tags["policy"] = policy
    if "{profile}" in template:
        tags["profile"] = profile
    if "{rule}" in template:
        tags["rule"] = rule
    return template.format(**tags)
