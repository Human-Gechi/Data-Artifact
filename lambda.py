import boto3
import botocore
import json
import logging
import os
from datetime import datetime, timezone

from botocore.exceptions import ClientError
from botocore.config import Config

logger = logging.getLogger()
logger.setLevel(logging.INFO)

BUCKET_NAME = ""
DDB_TABLE = ""
AWS_REGION = "eu-north-1"
MODEL_ID = "amazon.nova-2-lite-v1:0"

