from asyncio import exceptions
import os
import sys
import requests
from requests.exceptions import HTTPError
import logging
from typing import List
from time import time
import uuid

from operator import attrgetter

import azure.functions as func
from azure.storage.blob import BlobClient, BlobServiceClient, ContainerClient

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

def main(req: func.HttpRequest, msg: func.Out[List[str]] ) -> str:
    
    logger.info('Python HTTP trigger function processed a request.')

    # Getting required data from environment variable, raising an error when not configured
    tenant_name = os.environ['tenant_name']
    action_name = os.environ['action']
    token = os.environ['token']
    rule_name = os.environ['rule_name']
    account_url = os.environ['account_url']
    security_results_access_key = os.environ['SecurityAssessmentResultsStorage']

    # start_time = get_last_timestamp(account_url, security_results_access_key)
    start_time = 1
    last_timestamp = str(start_time)

    page = 0

    # try:
    #     SecurityPostureAssessmentResults = get_alerts(
    #         tenant_name, rule_name, token, str(PAGE_SIZE), str(page * PAGE_SIZE), start_time)
    # except HTTPError as e:
    #     logger.error(e) 

    results = get_alerts(
        tenant_name, rule_name, token, str(PAGE_SIZE), str(page * PAGE_SIZE), start_time)

    logger.info(f'results: {results}')
        
    violations_results = []

    count = 0

    while len(results):

        for data in results:

            logger.info(f'data: {data}')

            logger.info(
                f"Got matching alert for action: {data['action']} "
                f"on instance: {data['instance']} "
                f"for resource_id: {data['_id']} "
                f"with (policy_name: {data['policy']}, profile_name: {data['dlp_profile']}, rule_name: {data['dlp_rule']})"
            )

            violations_results.append(f"{data['_id']}, {data['policy']}, {data['dlp_profile']}, {data['dlp_rule']}")

            if int(data['timestamp']) > int(last_timestamp):
                last_timestamp = int(data['timestamp'])

        if len(violations_results) > 0:

            logger.info(f'violationsResourceID List: {violations_results}')

            msg.set(violations_results)

            count += 1

            page = page + 1

            logger.info(f"Violated Resource ids enqueued to the remediation Storage Queue. The resources with violation are {violations_results}")
        else:
            return f"No violation for the rule {rule_name} on tenant {tenant_name}"

        results = get_alerts(tenant_name, data['dlp_rule'], token, str(PAGE_SIZE), str(page * PAGE_SIZE), start_time)
        logger.debug(results)

    # put_results(results, bucket, f"{action_name}/{file_name}")
    if count > 0:
        put_last_timestamp(security_results_access_key, last_timestamp, data['action'])

    return f'Got {count} total alerts for the action {action_name}'




def get_alerts(tenant_name, rule_name, token, limit, skip, starttime):

    now = int(time())

    logging.info("Going to get the security assessment violations from the latest scan for the " +
                 tenant_name + " tenant and the rule is " + rule_name)

    get_url = f"https://{tenant_name}/api/v1/alerts"

    payload = {
        "token": token,
        "type": "DLP",
        "acked": "false",
        "starttime": starttime,
        "endtime": now,
        "query": "app like 'Microsoft Azure'",
        "limit": limit,
        "skip": skip
    }

    logging.info(f"Calling Netskope API for DLP scan alerts for {rule_name}")

    res = requests.get(get_url, params=payload)

    res.raise_for_status()

    return res.json()['data']

def get_last_timestamp(account_url, credential):

    try:
        blob_service_client = BlobClient(account_url=account_url, credential=credential)
        blob_client = blob_service_client.get_blob_client(container=container_name, blob=local_file_name)
        # get container and parse out the timestamp
        ### aws example code ###
        # s3 = boto3.client("s3")
        # object_key = f"{action_name}/last_timestamp_{action_name}.txt"
        # object = s3.get_object(Bucket=bucket, Key=object_key)
        # timestamp = int(object["Body"].read().strip())

    except Exception as e:
        logger.info(e)
        timestamp = 1

    return timestamp

def put_last_timestamp(connection_string, timestamp, action):

    logger.info('Executing put_last_timestamp function')


    blob_service_client = BlobServiceClient.from_connection_string(connection_string)

    # Create a container where you can upload 
    # or download blobs
    container_client = blob_service_client.get_container_client('my_container')

    try:
        container_client.create_container()

        logger.info('created container for timestamp')

        blob_client = container_client.get_blob_client('my_blob')

        # Create a file in the local data directory to upload and download
        local_file_name = f'{action}/last_timestamp_{action}.txt'

        # Write text to the file
        file = open(local_file_name, 'w')
        file.write(timestamp)
        file.close()

        # blob = BlobServiceClient.from_connection_string(connection_string, logging_enable=True) 
        # blob_client = blob.get_blob_client(container='my_container', blob=local_file_name)
        
        print("\nUploading to Azure Storage as blob:\n\t" + local_file_name)

        # Upload the created file
        with open(local_file_name, "rb") as data:
            blob_client.upload_blob(data, blob_type="BlockBlob")
            logger.info('uploaded new blob')
        

    except Exception as e:
        logger.info(e)

    




"""
{'status': 'success', 'msg': '', 'data': [{'_id': '2146bf72a5a7cfc67530db90', '_insertion_epoch_timestamp': 1646851643, 'access_method': 'API Connector', 'acked': 'false', 'action': 'alert', 'activity': 'Introspection Scan', 'alert': 'yes', 'alert_name': 'test_name_and_address', 'alert_type': 'DLP', 'app': 'Microsoft Azure', 'appcategory': 'IaaS/PaaS', 'browser': 'unknown', 'category': 'IaaS/PaaS', 'ccl': 'excellent', 'count': 1, 'device': 'Other', 'dlp_file': 'fname_address.rtf', 'dlp_incident_id': 1061204303622681500, 'dlp_is_unique_count': 'true', 'dlp_parent_id': 1061204303622681500, 'dlp_profile': 'Test Name and Address', 'dlp_rule': 'Test Name and Address', 'dlp_rule_count': 1, 'dlp_rule_severity': 'Low', 'dlp_unique_count': 1, 'dst_country': 'US', 'dst_latitude': 37.9273, 'dst_location': 'Tappahannock', 'dst_longitude': -76.8545, 'dst_region': 'Virginia', 'dst_timezone': 'America/New_York', 'dst_zipcode': '22560', 'dstip': '52.239.169.132', 'exposure': 'Private', 'file_lang': 'Unknown', 'file_path': 'https://dlptarget.blob.core.windows.net/dlp-target-container/fname_address.rtf', 'file_size': 418, 'file_type': 'text/rtf', 'from_user': 'admin', 'instance': 'Azure subscription 1', 'instance_id': 'Azure subscription 1', 'md5': '858883b87570583400ef81b59d6d377f', 'mime_type': 'text/rtf', 'modified': 1646850226, 'netskope_pop': 'US-SJC1', 'object': 'fname_address.rtf', 'object_id': 'aHR0cHM6Ly9kbHB0YXJnZXQuYmxvYi5jb3JlLndpbmRvd3MubmV0L2RscC10YXJnZXQtY29udGFpbmVyL2ZuYW1lX2FkZHJlc3MucnRm', 'object_type': 'File', 'organization_unit': '', 'os': 'unknown', 'other_categories': [], 'owner': 'admin', 'policy': 'test_name_and_address', 'request_id': 6328229169072771564, 'retro_scan_name': 'Retro_Scan_azure_Azure subscription 1_20220309_114649', 'scan_type': 'Retroactive', 'sha256': '8f0278cd8ec66d27e83aa21f58c31b3bc588412f63ba84c0d3ddf5cd82f13252', 'site': 'Microsoft Azure', 'suppression_key': 'fname_address.rtf', 'timestamp': 1646851638, 'title': 'fname_address.rtf', 'traffic_type': 'CloudApp', 'true_obj_category': 'Word Processor', 'true_obj_type': 'Rich Text Format (RTF)', 'type': 'nspolicy', 'ur_normalized': 'admin', 'url': 'https://dlptarget.blob.core.windows.net/dlp-target-container/fname_address.rtf', 'user': 'admin', 'user_id': 'admin'}
"""