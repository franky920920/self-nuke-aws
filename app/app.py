from __future__ import print_function
import subprocess
import os
import logging
import urllib3
import json
import re
import yaml

logger = logging.getLogger()
logger.setLevel(logging.INFO)

binary_path = os.path.join(os.getcwd(), "cloud-nuke_linux_arm64")

## The cfn-response code ##
# Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.
# SPDX-License-Identifier: MIT-0


SUCCESS = "SUCCESS"
FAILED = "FAILED"

http = urllib3.PoolManager()


def cfnresponse(event, context, responseStatus, responseData, physicalResourceId=None, noEcho=False, reason=None):
    responseUrl = event['ResponseURL']

    print(responseUrl)

    responseBody = {
        'Status': responseStatus,
        'Reason': reason or "See the details in CloudWatch Log Stream: {}".format(context.log_stream_name),
        'PhysicalResourceId': physicalResourceId or context.log_stream_name,
        'StackId': event['StackId'],
        'RequestId': event['RequestId'],
        'LogicalResourceId': event['LogicalResourceId'],
        'NoEcho': noEcho,
        'Data': responseData
    }

    json_responseBody = json.dumps(responseBody)

    print("Response body:")
    print(json_responseBody)

    headers = {
        'content-type': '',
        'content-length': str(len(json_responseBody))
    }

    try:
        response = http.request('PUT', responseUrl, headers=headers, body=json_responseBody)
        print("Status code:", response.status)


    except Exception as e:

        print("send(..) failed executing http.request(..):", e)


def clean_console_output(text):
    # Remove ANSI escape codes for color and formatting
    clean_text = re.sub(r'\033\[[0-9;]+m', '', text)

    # Remove unnecessary characters
    clean_text = clean_text.replace('|', '')
    clean_text = clean_text.replace('┌─┐', '')
    clean_text = clean_text.replace('─', '-')

    return clean_text.strip()


def lambda_handler(event, context):
    logger.info(event)
    if event['RequestType'] == "Create":
        logger.warning('Cloudnuke stack is being created! All resources in this account will be nuked automatically '
                       'upon stack deletion. ')
        cfnresponse(event, context, SUCCESS, {})
    elif event['RequestType'] == "Delete":
        # Create config file in /tmp
        config_data = {
            'lambda': {
                'exclude': {
                    'names_regex': {
                        '^cloudnuke-CloudnukeFunction-.*'
                    }
                }
            },
            'cloudwatch-loggroup': {
                'exclude': {
                    'names_regex': {
                        '^/aws/lambda/cloudnuke-.*'
                    }
                }
            },
            'iam-role': {
                'exclude': {
                    'names_regex': {
                        'AdminRole'
                    }
                }
            }
        }

        # Specify the file path
        file_path = '/tmp/config.yml'

        # Write the configuration data to the YAML file
        with open(file_path, 'w') as file:
            yaml.dump(config_data, file, default_flow_style=False)

        try:
            result = subprocess.run([binary_path, "aws", "--region", os.environ['AWS_REGION'],
                                     "--config", "/tmp/config.yml", "--force"], stdout=subprocess.PIPE)
            logger.info("Command output:\n---\n{}\n---".format(clean_console_output(result.stdout.decode('UTF-8'))))
            cfnresponse(event, context, SUCCESS, {})
        except Exception as e:
            logger.error("Exception: {}".format(e))
            cfnresponse(event, context, FAILED, {})
