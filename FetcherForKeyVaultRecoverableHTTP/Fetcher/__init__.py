from asyncio import exceptions
import os
import sys
import requests
import logging
import uuid
import datetime

from requests.exceptions import HTTPError
from typing import List
from time import time
from io import BytesIO

import azure.functions as func
from azure.storage.blob import BlobClient, BlobServiceClient, ContainerClient
from azure.core.exceptions import ResourceExistsError, ResourceNotFoundError
from azure.storage.queue import QueueClient



CLOUD_PROVIDER = "azure"
STATUS = 'Failed'
MUTED = 'No'
PAGE_SIZE = 100

# Set up  logger
LOG_LEVEL = os.getenv("LOGLEVEL", "INFO")
LOG_LEVEL = LOG_LEVEL.upper()
logger = logging.getLogger()
logger.setLevel(logging.getLevelName(LOG_LEVEL))

# Create a logger for the 'azure.storage.blob' SDK
azure_logger = logging.getLogger('azure.storage.blob')
azure_logger.setLevel(logging.DEBUG)
handler = logging.StreamHandler(stream=sys.stdout)
azure_logger.addHandler(handler)


# Configure a console output
handler = logging.StreamHandler(stream=sys.stdout)
logger.addHandler(handler)

# Getting required data from environment variable, raising an error when not configured
tenant_name = os.environ['tenant_name']
token = os.environ['token']
security_results_access_key = os.environ['DLP_SCAN_RESULT_STORAGE']
timestamp_container = os.environ['TIMESTAMP_CONTAINER']

def main(req: func.HttpRequest ) -> str:
    
    logger.info('Python HTTP trigger function processed a request.')

    body = req.get_json()

    action_name = body['action']
    policies = body['policies']
    profiles = body['profiles']
    rules = body['rules']

    logging.info(f"Calling Netskope API for DLP scan alerts for {action_name}")

    results_queue_name = f'dlp-scan-{action_name}-results'

    timestamp_file_name = f'last_timestamp_{action_name}.txt'
    
    blob_client =  BlobServiceClient.from_connection_string(security_results_access_key)

    start_time = get_timestamp(blob_client, timestamp_container, timestamp_file_name) + 1
    last_timestamp = start_time

    page = 0

    results = get_alerts(
        action_name, token, str(PAGE_SIZE), str(page * PAGE_SIZE), start_time)

    logger.info(f'results: {results}')
        
    violations_results = []

    count = 0

    while len(results):

        for data in results:

            policy = data['policy']
            profile = data['dlp_profile']
            rule = data['dlp_rule']

            logger.info(f'data: {data}')

            if policy in policies or profile in profiles or rule in rules:
                logger.info(
                    f"Got matching alert for action: {data['action']} "
                    f"on instance: {data['instance']} "
                    f"for resource_id: {data['_id']} "
                    f"with (policy_name: {data['policy']}, profile_name: {data['dlp_profile']}, rule_name: {data['dlp_rule']})"
                )

                violations_results.append(f"{data['url']}, {data['policy']}, {data['dlp_profile']}, {data['dlp_rule']}")

                count += 1

                if int(data['timestamp']) > int(last_timestamp):
                    last_timestamp = int(data['timestamp'])

        page = page + 1

        results = get_alerts(tenant_name, data['dlp_rule'], token, str(PAGE_SIZE), str(page * PAGE_SIZE), start_time)
        logger.debug(results)

    # put_results(results, bucket, f"{action_name}/{file_name}")
    if count > 0:
        put_timestamp(blob_client, timestamp_container, timestamp_file_name, last_timestamp)

    if len(violations_results) > 0:

        logger.info(f'violationsResourceID List: {violations_results}')

        put_results(violations_results, results_queue_name)

        logger.info(f"Violated Resource ids enqueued to the remediation Storage Queue. The resources with violation are {violations_results}")
    else:
        return f"No violation for the rule {rule_name} on tenant {tenant_name}"

    return f'Got {count} total alerts for the action {action_name}'

def get_alerts(token, limit, skip, start_time):

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
        "skip": skip
    }

    res = requests.get(get_url, params=payload)

    res.raise_for_status()

    return res.json()['data']

def get_timestamp(client, container_name, action):

    local_file_name = f'{action}/last_timestamp_{action}.txt'

    # Create a blob client using the local file name as the name for the blob
    try:
        blob_client = client.get_blob_client(container=container_name, blob=local_file_name)
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

def put_results(results, queue_name):

    client = QueueClient.from_connection_string(security_results_access_key, queue_name)
    try:
        client.create_queue()
    except ResourceExistsError: 
        logging.info(f'queue {queue_name} already exists')

    for result in results:
        client.send_message(result)


    
#  DefaultEndpointsProtocol=https;AccountName=securityresultz;AccountKey=qjtYYRu458vnFe/x5OkpxKdzHnbH11TsHFXHw/EO9jvaX5Z2AlprEpg61WtxIpmC60N38KxRhM7b+AStRIdn4w==;EndpointSuffix=core.windows.net



"""
{'status': 'success', 'msg': '', 'data': [{'_id': '2146bf72a5a7cfc67530db90', '_insertion_epoch_timestamp': 1646851643, 'access_method': 'API Connector', 'acked': 'false', 'action': 'alert', 'activity': 'Introspection Scan', 'alert': 'yes', 'alert_name': 'test_name_and_address', 'alert_type': 'DLP', 'app': 'Microsoft Azure', 'appcategory': 'IaaS/PaaS', 'browser': 'unknown', 'category': 'IaaS/PaaS', 'ccl': 'excellent', 'count': 1, 'device': 'Other', 'dlp_file': 'fname_address.rtf', 'dlp_incident_id': 1061204303622681500, 'dlp_is_unique_count': 'true', 'dlp_parent_id': 1061204303622681500, 'dlp_profile': 'Test Name and Address', 'dlp_rule': 'Test Name and Address', 'dlp_rule_count': 1, 'dlp_rule_severity': 'Low', 'dlp_unique_count': 1, 'dst_country': 'US', 'dst_latitude': 37.9273, 'dst_location': 'Tappahannock', 'dst_longitude': -76.8545, 'dst_region': 'Virginia', 'dst_timezone': 'America/New_York', 'dst_zipcode': '22560', 'dstip': '52.239.169.132', 'exposure': 'Private', 'file_lang': 'Unknown', 'file_path': 'https://dlptarget.blob.core.windows.net/dlp-target-container/fname_address.rtf', 'file_size': 418, 'file_type': 'text/rtf', 'from_user': 'admin', 'instance': 'Azure subscription 1', 'instance_id': 'Azure subscription 1', 'md5': '858883b87570583400ef81b59d6d377f', 'mime_type': 'text/rtf', 'modified': 1646850226, 'netskope_pop': 'US-SJC1', 'object': 'fname_address.rtf', 'object_id': 'aHR0cHM6Ly9kbHB0YXJnZXQuYmxvYi5jb3JlLndpbmRvd3MubmV0L2RscC10YXJnZXQtY29udGFpbmVyL2ZuYW1lX2FkZHJlc3MucnRm', 'object_type': 'File', 'organization_unit': '', 'os': 'unknown', 'other_categories': [], 'owner': 'admin', 'policy': 'test_name_and_address', 'request_id': 6328229169072771564, 'retro_scan_name': 'Retro_Scan_azure_Azure subscription 1_20220309_114649', 'scan_type': 'Retroactive', 'sha256': '8f0278cd8ec66d27e83aa21f58c31b3bc588412f63ba84c0d3ddf5cd82f13252', 'site': 'Microsoft Azure', 'suppression_key': 'fname_address.rtf', 'timestamp': 1646851638, 'title': 'fname_address.rtf', 'traffic_type': 'CloudApp', 'true_obj_category': 'Word Processor', 'true_obj_type': 'Rich Text Format (RTF)', 'type': 'nspolicy', 'ur_normalized': 'admin', 'url': 'https://dlptarget.blob.core.windows.net/dlp-target-container/fname_address.rtf', 'user': 'admin', 'user_id': 'admin'}
"""