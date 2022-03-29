from io import BytesIO
import logging
import os

from azure.core.exceptions import ResourceExistsError, ResourceNotFoundError
import azure.functions as func
from azure.identity import DefaultAzureCredential
from azure.storage.blob import BlobClient, BlobServiceClient, download_blob_from_url


# Set up  logger
LOG_LEVEL = os.getenv("LOGLEVEL", "INFO")
LOG_LEVEL = LOG_LEVEL.upper()
logger = logging.getLogger()
logger.setLevel(logging.getLevelName(LOG_LEVEL))

tombstone_content = os.environ.get(
    "QUARANTINE_TOMBSTONE_CONTENT",
    "This object has been quarantined due to security policy.\nPolicy: {policy}\nProfile: {profile}\nRule: {rule}",
)
storage_connection_string = os.environ.get("DLP_SCAN_RESULT_STORAGE", "")
quarantine_container = os.environ.get("QUARANTINE_CONTAINER", "")


def main(msg: func.QueueMessage) -> None:
    message = msg.get_body().decode()
    logger.info(f"Quarantine action received a queue message: {message}")
    url, policy, profile, rule = message.split(",")

    if artifact_exists(url):
        try:
            logger.info(f"Artifact {url} exists beginning quarantine.")
            write_tombstone(url, policy, profile, rule)
            move_artifact_to_quarantine(url)
            logger.info(f"Remediation was successfully invoked to quarantine for {url}.")
        except Exception as err:
            logger.error(f"Exception encountered running Quarantine autoremediation: {err}")
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


def move_artifact_to_quarantine(resource_id):
    cred = DefaultAzureCredential()

    data, destination = _download_quarantine_file(resource_id, cred)
    _upload_to_quarantine(data, destination)

    del_client = BlobClient.from_blob_url(resource_id, credential=cred)
    del_client.delete_blob()


def _download_quarantine_file(resource_id, credential):
    storage_acct = resource_id.strip("https://").split("/")[0].split(".")[0]
    path = resource_id.strip("https://").split("/", 1)[1]
    target_filepath = f"{storage_acct}/{path}"
    data = BytesIO()
    try:
        logger.info(f"Downloading file from: {resource_id} to quarantine")
        download_blob_from_url(blob_url=resource_id, output=data, credential=credential)
        return data, target_filepath
    except ResourceNotFoundError as err:
        logger.warning(f"Could not find source artifact: {err}")
        raise


def _upload_to_quarantine(data, destination):
    svc_client = BlobServiceClient.from_connection_string(storage_connection_string)
    try:
        svc_client.create_container(quarantine_container)
    except ResourceExistsError:
        print(f"Container {quarantine_container} already exists.")

    client = svc_client.get_blob_client(quarantine_container, destination)
    client.upload_blob(data, blob_type="BlockBlob")


def render_content(template, policy, profile, rule):
    tags = {}
    if "{policy}" in template:
        tags["policy"] = policy
    if "{profile}" in template:
        tags["profile"] = profile
    if "{rule}" in template:
        tags["rule"] = rule
    return template.format(**tags)
