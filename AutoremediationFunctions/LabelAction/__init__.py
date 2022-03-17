import logging
import os

import azure.functions as func
from shared_code.cred_wrapper import CredentialWrapper

# Set up  logger
LOG_LEVEL = os.getenv("LOGLEVEL", "INFO")
LOG_LEVEL = LOG_LEVEL.upper()
logger = logging.getLogger()
logger.setLevel(logging.getLevelName(LOG_LEVEL))

container_label = os.environ.get("CONTAINER_LABEL", "")
object_albel = os.environ.get("OBJECT_LABEL", "")


def main(msg: func.QueueMessage) -> None:
    logger.info("Python queue trigger function processed a queue item: %s", msg.get_body().decode("utf-8"))
    message = msg.get_body().decode("utf-8")
    url, policy, profile, rule = message.split(",")

    cred = CredentialWrapper()

    # TODO: nstantiate container and blob client and apply labels
