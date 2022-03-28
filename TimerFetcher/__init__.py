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
    "tenant_name": os.environ["NETSKOPE_FQDN"],
    "token": os.environ["NETSKOPE_TOKEN"],
    "security_results_access_key": os.environ["DLP_SCAN_RESULT_STORAGE"],
    "timestamp_container": os.environ["TIMESTAMP_CONTAINER"],
    "actions": [],
}


def _update_env(fn_env):

    actions = ("delete", "encrypt", "label", "quarantine", "restrict")
    enabled = []
    for action in actions:
        if os.environ.get(f"{action.upper()}_ACTION"):
            enabled.append(
                {
                    "action": action,
                    "policies": os.environ.get(f"{action.upper()}_MATCH_POLICIES", ""),
                    "profiles": os.environ.get(f"{action.upper()}_MATCH_PROFILES", ""),
                    "rules": os.environ.get(f"{action.upper()}_MATCH_RULES", ""),
                }
            )
    fn_env["actions"] = enabled


_update_env(fn_env)


def main(mytimer: func.TimerRequest):

    utc_timestamp = datetime.utcnow().replace(tzinfo=timezone.utc).isoformat()
    if mytimer.past_due:
        logger.info("The timer is past due!")

    logger.info(f"Executing Scheduled DLP-Scan alerts gathering function trigger at {utc_timestamp}")

    for act in fn_env["actions"]:
        try:
            action_env = fn_env.copy()
            action_env.update(act)
            message = fetch_results(action_env)
            logger.info(message)
        except Exception as err:
            logger.error(f"Error fetching DLP Scan results {err}")
