from io import BytesIO
import logging
import os
import requests

from time import time

from azure.storage.blob import BlobServiceClient
from azure.core.exceptions import ResourceExistsError, ResourceNotFoundError
from azure.storage.queue import QueueClient, BinaryBase64EncodePolicy


PAGE_SIZE = 100

# Set up  logger
LOG_LEVEL = os.getenv("LOGLEVEL", "INFO")
LOG_LEVEL = LOG_LEVEL.upper()
logger = logging.getLogger()
logger.setLevel(logging.getLevelName(LOG_LEVEL))


def fetch_results(configuration: dict) -> str:

    try:
        tenant_name = configuration["tenant_name"]
        token = configuration["token"]
        security_results_access_key = configuration["security_results_access_key"]
        timestamp_container = configuration["timestamp_container"]
        action_name = configuration["action"]
        policies = configuration["policies"]
        profiles = configuration["profiles"]
        rules = configuration["rules"]
    except KeyError as err:
        raise Exception(f"Failed to decode configuration missing key: {err}")

    logging.info(f"Calling Netskope API for DLP scan alerts for {action_name}")

    results_queue_name = f"dlp-scan-{action_name}-results"
    timestamp_file_name = f"last_timestamp_{action_name}.txt"

    blob_client = BlobServiceClient.from_connection_string(security_results_access_key)

    start_time = get_timestamp(blob_client, timestamp_container, timestamp_file_name) + 1
    last_timestamp = start_time

    page = 0
    count = 0
    alert_results = []
    results = get_alerts(tenant_name, token, str(PAGE_SIZE), str(page * PAGE_SIZE), start_time)
    logger.debug(f"results: {results}")

    while len(results):

        for data in results:
            policy = data["policy"]
            profile = data["dlp_profile"]
            rule = data["dlp_rule"]

            logger.debug(f"data: {data}")

            if policy in policies or profile in profiles or rule in rules:
                logger.info(
                    f"Got matching alert for action: {data['action']} "
                    f"on instance: {data['instance']} "
                    f"for resource: {data['url']} "
                    f"with (policy_name: {data['policy']}, profile_name: {data['dlp_profile']}, rule_name: {data['dlp_rule']})"
                )

                alert_results.append(f"{data['url']}, {data['policy']}, {data['dlp_profile']}, {data['dlp_rule']}")
                count += 1
                if int(data["timestamp"]) > int(last_timestamp):
                    last_timestamp = int(data["timestamp"])

        page = page + 1
        results = get_alerts(tenant_name, token, str(PAGE_SIZE), str(page * PAGE_SIZE), start_time)
        logger.debug(results)

    if count > 0:
        put_timestamp(blob_client, timestamp_container, timestamp_file_name, last_timestamp)

    if len(alert_results) > 0:
        logger.debug(f"alert_results list: {alert_results}")
        put_results(security_results_access_key, alert_results, results_queue_name)
        return (
            f'Got {count} total alerts matching configured policies: "{policies}", profiles: '
            f'"{profiles}", and rules: "{rules}"for the action {action_name}'
        )
    else:
        return (
            f'No DLP alerts found matching configured policies: "{policies}", profiles: '
            f'"{profiles}", and rules: "{rules}" for the action {action_name}'
        )


def get_alerts(tenant_name, token, limit, skip, start_time):

    now = int(time())
    get_url = f"https://{tenant_name}/api/v1/alerts"
    payload = {
        "token": token,
        "type": "DLP",
        "acked": "false",
        "starttime": start_time,
        "endtime": now,
        "query": "app like 'Microsoft Azure'",
        "limit": limit,
        "skip": skip,
    }

    res = requests.get(get_url, params=payload)
    res.raise_for_status()
    return res.json()["data"]


def get_timestamp(client, container_name, file_name):

    # Create a blob client using the local file name as the name for the blob
    try:
        blob_client = client.get_blob_client(container=container_name, blob=file_name)
        data = blob_client.download_blob().readall()
    except ResourceNotFoundError:
        return 1

    timestamp = int(data.decode())
    return timestamp


def put_timestamp(client, container_name, file_name, timestamp):

    # Create the container
    try:
        client.create_container(container_name)
    except ResourceExistsError:
        print(f"Container {container_name} already exists.")

    data = BytesIO(f"{int(timestamp)}".encode())
    # Create a blob client using the local file name as the name for the blob
    blob_client = client.get_blob_client(container=container_name, blob=file_name)
    print(f"Putting timestamp {timestamp}.")
    blob_client.upload_blob(data, overwrite=True)


def put_results(conn_string, results, queue_name):

    client = QueueClient.from_connection_string(conn_string, queue_name, message_encode_policy=BinaryBase64EncodePolicy())
    try:
        client.create_queue()
    except ResourceExistsError:
        logging.info(f"queue {queue_name} already exists")

    for result in results:
        client.send_message(result.encode())
