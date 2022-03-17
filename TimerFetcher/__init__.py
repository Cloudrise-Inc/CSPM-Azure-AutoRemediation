# Python stdlib
from datetime import datetime, timezone
import logging
import os

# PyPi packages
import azure.functions as func

# local packages
from shared_code.fetcher import fetch_results

# Set up  logger
LOG_LEVEL = os.getenv("LOGLEVEL", "INFO")
LOG_LEVEL = LOG_LEVEL.upper()
logger = logging.getLogger()
logger.setLevel(logging.getLevelName(LOG_LEVEL))

# Getting required data from environment variable, raising an error when not configured
fn_env = {
    "tenant_name": os.environ["tenant_name"],
    "token": os.environ["token"],
    "security_results_access_key": os.environ["DLP_SCAN_RESULT_STORAGE"],
    "timestamp_container": os.environ["TIMESTAMP_CONTAINER"],
    "action": os.environ["AUTOREMEDIATION_ACTION"],
    "policies": os.environ["MATCH_POLICIES"],
    "profiles": os.environ["MATCH_PROFILES"],
    "rules": os.environ["MATCH_RULES"],
}


def main(mytimer: func.TimerRequest):

    utc_timestamp = datetime.utcnow().replace(tzinfo=timezone.utc).isoformat()
    if mytimer.past_due:
        logger.info("The timer is past due!")

    logger.info(f"Scheduled Function Trigger at {utc_timestamp} for action {fn_env['action']}")

    try:
        message = fetch_results(fn_env)
        logger.info(message)
    except Exception as err:
        logger.error(f"Error fetching DLP Scan results {err}")
