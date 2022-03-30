from io import BytesIO
import logging
import os
from datetime import datetime

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

    data, storage_acct, path = _download_quarantine_file(resource_id, cred)
    destination = _generate_target_path(storage_acct, path)
    _upload_to_quarantine(data, destination)

    del_client = BlobClient.from_blob_url(resource_id, credential=cred)
    del_client.delete_blob()


def _download_quarantine_file(resource_id, credential):
    storage_acct = resource_id.strip("https://").split("/")[0].split(".")[0]
    path = resource_id.strip("https://").split("/", 1)[1]
    data = BytesIO()
    try:
        logger.info(f"Downloading file from: {resource_id} to quarantine")
        download_blob_from_url(blob_url=resource_id, output=data, credential=credential)
        return data, storage_acct, path
    except ResourceNotFoundError as err:
        logger.warning(f"Could not find source artifact: {err}")
        raise


def _generate_target_path(storage_account, path):
    dirname = os.path.dirname(path)
    file = os.path.basename(path)
    fl = file.rsplit(".", 1)
    if len(fl) == 1:
        file = f"{fl[0]}_{datetime.now().isoformat()}"
    elif len(fl) == 2:
        file = f"{fl[0]}_{datetime.now().isoformat()}.{fl[1]}"
    return f"{storage_account}/{dirname}/{file}"


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
