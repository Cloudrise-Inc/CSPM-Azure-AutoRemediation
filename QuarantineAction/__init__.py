from io import BytesIO
import logging
import os

import azure.functions as func
from azure.identity import DefaultAzureCredential
from azure.storage.blob import BlobClient, BlobServiceClient


# Set up  logger
LOG_LEVEL = os.getenv("LOGLEVEL", "INFO")
LOG_LEVEL = LOG_LEVEL.upper()
logger = logging.getLogger()
logger.setLevel(logging.getLevelName(LOG_LEVEL))

tombstone_content = os.environ.get("QUARANTINE_TOMBSTONE_CONTENT", "")
storage_connection_string = os.environ.get("DLP_SCAN_RESULT_STORAGE", "")
quarantine_container = os.environ.get("QUARANTINE_CONTAINER", "")


def main(msg: func.QueueMessage) -> None:
    message = msg.get_body().decode()
    logger.info(f"Python queue trigger function processed a queue item: {message}")

    url, policy, profile, rule = message.split(",")
    if artifact_exists(url):
        logger.info(f"Artifact {url} exists beginning quarantine.")
        write_tombstone(url, policy, profile, rule)
        move_artifact_to_quarantine(url)
        logger.info(f"Remediation was successfully invoked to quarantine for {url}.")
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
    client.upload_blob(data, blob_type="BlockBlob")
    logger.info("Wrote tombstone.")


def move_artifact_to_quarantine(resource_id):
    cred = DefaultAzureCredential()
    storage_acct = resource_id.strip("https://").split("/")[0].split(".")[0]
    path = resource_id.strip("https://").split("/", 1)[1]
    target_filepath = f"{storage_acct}/{path}"
    svc_client = BlobServiceClient.from_connection_string(storage_connection_string, credential=cred)
    client = svc_client.get_blob_client(quarantine_container, target_filepath)
    copy_op = client.start_copy_from_url(resource_id)
    copy_op.wait()
    del_client = BlobClient.from_blob_url(resource_id, credential=cred)
    del_client.delete_blob()


def render_content(template, policy, profile, rule):
    tags = {}
    if "{policy}" in template:
        tags["policy"] = policy
    if "{profile}" in template:
        tags["profile"] = profile
    if "{rule}" in template:
        tags["rule"] = rule
    return template.format(**tags)
