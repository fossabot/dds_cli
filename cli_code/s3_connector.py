"""S3 Connector module"""

###############################################################################
# IMPORTS ########################################################### IMPORTS #
###############################################################################

# Standard library
import logging
import traceback
import requests
import sys

# Installed
import boto3
import botocore

# Own modules
from cli_code import DDSEndpoint
from cli_code import timestamp

###############################################################################
# LOGGING ########################################################### LOGGING #
###############################################################################

log = logging.getLogger(__name__)
log.setLevel(logging.DEBUG)

###############################################################################
# CLASSES ########################################################### CLASSES #
###############################################################################


class S3Connector:

    def __init__(self, project_id, token):
        self.safespring_project, self.keys, self.url, self.bucketname = \
            self.get_s3info(project_id=project_id, token=token)

        self.resource = None

    def __enter__(self):
        self.connect()
        return self

    def __exit__(self, exc_type, exc_value, tb):
        if exc_type is not None:
            traceback.print_exception(exc_type, exc_value, tb)
            return False  # uncomment to pass exception through

        return True

    def __repr__(self):
        return "<S3Connector>"

    def get_s3info(self, project_id, token):
        """Gets the safespring project and keys."""

        args = {"project": project_id}

        response = requests.get(DDSEndpoint.S3KEYS, params=args, headers=token)

        if not response.ok:
            sys.exit("Failed retrieving Safespring project name. "
                     f"Error code: {response.status_code} "
                     f" -- {response.reason}"
                     f"{response.text}")

        s3info = response.json()
        return s3info["safespring_project"], s3info["keys"], s3info["url"], \
            s3info["bucket"]

    def connect(self):
        """Connect to S3"""

        # Connect to service
        try:
            session = boto3.session.Session()

            self.resource = session.resource(
                service_name="s3",
                endpoint_url=self.url,
                aws_access_key_id=self.keys["access_key"],
                aws_secret_access_key=self.keys["secret_key"]
            )
        except botocore.client.ClientError as err:
            sys.exit("S3 connection failed: %s", err)

        bucket_exists = self.check_bucket_exists()
        if not bucket_exists:
            self.create_bucket()

    def check_bucket_exists(self):
        """Checks if the bucket exists"""

        try:
            self.resource.meta.client.head_bucket(Bucket=self.bucketname)
        except botocore.client.ClientError:
            log.info("Bucket '%s' does not exist!", self.bucketname)
            return False

        return True

    def create_bucket(self):
        """Creates the bucket"""

        log.info("Creating bucket '%s'...", self.bucketname)
        
        try:
            self.resource.meta.client.create_bucket(Bucket=self.bucketname)
        except botocore.client.ClientError as err2:
            log.critical("Could not create bucket %s! %s",
                         self.bucketname, err2)
            return False

        bucket_exists = self.check_bucket_exists()
        if not bucket_exists:
            sys.exit("Bucket '%s' does not exist. Failed second attempt.")

        log.info("Bucket '%s' created!", self.bucketname)
