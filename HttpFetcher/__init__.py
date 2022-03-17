# Python stdlib
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
}


def main(req: func.HttpRequest) -> func.HttpResponse:

    logger.info("HTTP trigger Gathering DLP Scan alerts.")

    try:
        body = req.get_json()
    except ValueError as err:
        return func.HttpResponse(f"Failed to get body from HttpRequest {err}", status_code=400)

    try:
        body["action"]
        body["policies"]
        body["profiles"]
        body["rules"]
    except KeyError as err:
        return func.HttpResponse(f"Failed to get required key error {err}", status_code=400)

    fn_env.update(body)

    try:
        message = fetch_results(fn_env)
        logger.info(message)
        return func.HttpResponse(message, status_code=200)
    except Exception as err:
        logger.error(f"Error fetching DLP Scan results {err}")
        return func.HttpResponse(err, status_code=400)
