#!/usr/bin/env python3

from logging import getLogger, basicConfig, INFO
from argparse import ArgumentParser
from time import sleep
from lxml import etree

from owslib import wps
import requests
import json
import sys


def check_status(url=None, response=None, sleep_secs=2, verify=False):
    """
    Run owslib.wps check_status with additional exception handling.

    :param verify: Flag to enable SSL verification. Default: False
    :return: OWSLib.wps.WPSExecution object.
    """
    logger = getLogger(__name__)
    execution = wps.WPSExecution()
    if response:
        logger.debug("using response document ...")
        xml = response
    elif url:
        logger.debug('using status_location url ...')
        xml = requests.get(url, verify=verify).content
    else:
        raise Exception("You need to provide a status-location "
                        "url or response object.")
    logger.debug("xml has type %s", type(xml))
    logger.debug("xml has contents %s", xml)

    if type(xml) is not str:
        xml = xml.decode('utf8', errors='ignore')

    execution.checkStatus(response=xml, sleepSecs=sleep_secs)
    if execution.response is None:
        raise Exception("check_status failed!")
    # TODO: workaround for owslib type change of reponse
    logger.debug("response has type : %s", type(execution.response))
    if not isinstance(execution.response, etree._Element):
        execution.response = etree.fromstring(execution.response)
    return execution


def main():
    """
    Command line entry point.
    """
    basicConfig(level=INFO)
    logger = getLogger(__name__)
    parser = ArgumentParser()
    parser.add_argument('target')
    parser.add_argument('workflow_filename')
    args = parser.parse_args()

    with open(args.workflow_filename) as wf_f:
        workflow = json.load(wf_f)

    host = args.target
    url = 'http://{host}:8091/wps'.format(host=host)
    logger.info("Calling a WPS instance at %s", url)
    client = wps.WebProcessingService(
        url=url,
        skip_caps=True)

    logger.info("Executing the process 'workflow' by providing the workflow "
                "from %s", args.workflow_filename)
    inputs = [('workflow_string', json.dumps(workflow))]
    execution = client.execute(
        identifier='custom_workflow',
        inputs=inputs,
        output=[('output', True),
                ('logfile', True)])

    # The status location can be opened in a browser and refresh to get the
    # current status until the process finished or failed
    print(execution.statusLocation)

    num_retries = 0
    while execution.isNotComplete():
        if num_retries >= 5:
            raise Exception("Could not read status document after 5 retries. "
                            "Giving up.")

        try:
            execution = check_status(url=execution.statusLocation,
                                     verify=False,
                                     sleep_secs=3)
            #logger.debug('response : ' + str(execution.response))
            #logger.debug('status : ' + execution.getStatus())
            #logger.debug('status_message : ' + execution.statusMessage)
            #logger.debug('progress : {0}'.format(execution.percentCompleted))
            if execution.isComplete():
                if execution.isSucceded():
                    logger.info('status_message : Succeeded')
                else:
                    errors = execution.errors
                    logger.info('status_message : Failed' +
                                 '\n'.join(error.text for error in errors))
                    return 1

        except:
            num_retries += 1
            logger.exception("Could not read status xml document. "
                             "Trying again ...")
            sleep(1)
        else:
            num_retries = 0
    return 0


if __name__ == '__main__':
    sys.exit(main())
