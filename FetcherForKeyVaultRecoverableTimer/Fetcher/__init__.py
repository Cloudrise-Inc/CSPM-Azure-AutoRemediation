import datetime
import logging
import os
import requests
import typing

from time import time

import azure.functions as func

CLOUD_PROVIDER = "azure"
STATUS = 'Failed'
MUTED = 'No'
LIMIT = 100


def main(mytimer: func.TimerRequest, msg: func.Out[typing.List[str]]) -> str:
    utc_timestamp = datetime.datetime.utcnow().replace(
        tzinfo=datetime.timezone.utc).isoformat()

    if mytimer.past_due:
        logging.info('The timer is past due!')
    logging.info(f"Function Trigger at {utc_timestamp}")

    # Getting required data from environment variable, raising an error when not configured
    tenant_name = os.environ['tenant_name']
    token = os.environ['token']
    rule_name = os.environ['rule_name']

    SecurityPostureAssessmentResults = get_alerts(
        tenant_name, rule_name, token)
    results = SecurityPostureAssessmentResults.get('data', [])
    violationsResourceID = []
    for data in results:
        violationsResourceID.append(data.get("resource_id"))
    if violationsResourceID:
        msg.set(violationsResourceID)
        logging.info(
            f"Violated Resource ids enqueued to the remediation Storage Queue. The resources with violation are {violationsResourceID}")
    logging.info(
        f"No violation for the rule {rule_name} on tenant {tenant_name}")


def get_alerts(tenant_name, rule_name, token):
    logging.info("Going to get the security assessment violations from the latest scan for the " +
                 tenant_name + " tenant and the rule is " + rule_name)
    get_url = "https://" + tenant_name + "/api/v1/alerts"
    payload = {
        'token': token,
        'type': 'DLP',
        'cloud_provider': CLOUD_PROVIDER,
        'rule_name': rule_name,
        'status': STATUS,
        'muted': MUTED,
        'limit': LIMIT,
        'skip': 0
    }
    res = requests.get(get_url, params=payload)
    return res.json()