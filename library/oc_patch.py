#!/usr/bin/python
# -*- coding: utf-8 -*-
# Copyright (c) 2017 Ansible Project
# GNU General Public License v3.0+ (see COPYING or
# https://www.gnu.org/licenses/gpl-3.0.txt)

from ansible.module_utils.basic import *  # noqa: E402
import requests
import json
from functools import reduce
import operator

ANSIBLE_METADATA = {'status': ['preview'],
                    'supported_by': 'community',
                    'metadata_version': '1.1'}

DOCUMENTATION = '''
---
module: oc_patch
short_description: Used to patch Openshift objects via API calls.
description:
    - Can be used to apply patches to openshift objects.
    - These can be things like configmaps, quotas, etc.
    - Can be used with get/replace/remove/move/addi/test json methods.
    - Replace will add a key if it doesn't already exist.
version_added: "2.4"
author: "Oliver Cable (@olivercable)"
options:
    token:
        description:
            - A token is required to authenticate against Openshift.
            - Log in and type `oc whoami  -t`
            - Keep this in ansible vault.
        required: true
        default: null
    host:
        description:
            - URL/IP for your host.
        required: true
        default: null
    port:
        description:
            - The port to target for OCP.
        required: False
        default: 443
    namespace:
        description:
            - The namespace in which the object you're patching exists.
        required: true
        default: null
    object:
        description:
            - Details around the operation you wish to execute.
            - Includes the following:
            - name (of openshift object).
            - type (of openshift object).
            - operation (to perform: replace/add/get/remove/move/test)
            - path (to value of interest).
            - value (of key of interest).
            - See examples.

requirements:
    - python-requests
'''

EXAMPLES = '''
---
- name: GET example. Return the details of an object.
  oc_patch:
    token: "{{ v_ocp_token }}"
    host: "myocp.companyname.local"
    namespace: "demo-namespace"
    object:
      name: "demo-configmap"
      type: configmap
      operation: get

- name: REPLACE example. Replace a value.
  oc_patch:
    token: "{{ v_ocp_token }}"
    host: "myocp.companyname.local"
    namespace: "demo-namespace"
    object:
      name: "demo-configmap"
      type: configmap
      operation: replace
      path: "/data/replace.testpath"
      value: "This is the value I will replace the target value with."

- name: ADD example. Add a key:value pair.
  oc_patch:
    token: "{{ v_ocp_token }}"
    host: "myocp.companyname.local"
    namespace: "demo-namespace"
    object:
      name: "demo-configmap"
      type: configmap
      operation: add
      path: "/data/addtestpath"
      value: "This will be the value added to the path above."

- name: REMOVE example. Removes a key:value pair.
  oc_patch:
    token: "{{ v_ocp_token }}"
    host: "myocp.companyname.local"
    namespace: "demo-namespace"
    object:
      name: "demo-resourcequota"
      type: resourcequota
      operation: remove
      path: "/data/removetestpath"

- name: MOVE example. Moves a value to a new key.
  oc_patch:
    token: "{{ v_ocp_token }}"
    host: "myocp.companyname.local"
    namespace: "demo-namespace"
    object:
      name: "demo-resourcequota"
      type: resourcequota
      operation: move
      from: "/data/oldmovetestpath"
      path: "/data/newmovetestpath"
'''

RETURN = '''
status_code:
    description: The HTTP status code returned by the API call.
    returned: Always
    type: string
    sample: 200
json:
    description: The API payload and response.
    returned: Failure
    type: complex
    sample: "json": { "message": "configmaps \"fakeconfigmap\" not found" }
new_value:
    description: When manipulating objects this is the modified value.
    returned: Success
    type: string
    sample: "new_value": "This is the text I hope will replace sherbertlemon"
old_value:
    description: When manipulating objects this is the old value.
    returned: Success
    type: string
    sample: "old_value": "sherbertlemon"
test:
    description: Boolean result if a path contains a value.
    returned: Test method
    type: boolean
    sample: True/False
'''


class ApiEndpoint(object):
    'ApiEndpoint class used to pass to a HTTP request.'

    def __init__(self, host, port, namespace, objectName,
                 objectType, objectOperation):
        self.host = host.lstrip('https://')
        self.port = port
        self.namespace = namespace
        self.objectName = objectName
        self.objectType = objectType
        self.objectOperation = objectOperation

    def __str__(self):
        url = "https://"
        url += self.host + ":"
        url += str(self.port) + "/"
        url += "api/v1/namespaces/"
        url += self.namespace + "/"
        url += self.objectType.lower()  # Url is objectType + s so no / here.
        url += "s/"
        url += self.objectName
        return url


class HTTPRequest(object):
    'HTTPRequest class used to make API calls.'

    def __init__(self, apiUrl, headers, payload):
        self.apiUrl = apiUrl
        self.headers = headers
        self.payload = payload

    def get(self):
        return requests.get(
            self.apiUrl,
            headers=self.headers
        )

    def post(self):
        return requests.post(
            self.apiUrl,
            headers=self.headers,
            data=json.dumps(self.payload)
        )

    def patch(self):
        return requests.patch(
            self.apiUrl,
            headers=self.headers,
            data=self.payload
        )

    def delete(self):
        return requests.delete(
            self.apiUrl,
            headers=self.headers
        )


def apiResponse(module, apiResult, getResult):

    op = module.params['object']['operation'].lower()

    # Handle replace and add cases where we didn't make an API call.
    if not apiResult:
        if op == "replace":
            module.fail_json(
                msg="NO CHANGE: Path does not already exist," +
                " consider using add method",
                changed=False,
                json=getResult.json(),
                status_code="N/A",
                new_value="N/A",
                old_value="N/A",
                test="N/A")
        elif op == "add":
            module.fail_json(
                msg="NO CHANGE: Path already exists, " +
                "consider using replace method.",
                changed=False,
                json=getResult.json(),
                status_code="N/A",
                new_value="N/A",
                old_value="N/A",
                test="N/A")

    # General success response, give a general thumbs up.
    if 200 <= apiResult.status_code <= 299:

        # REPLACE && ADD METHOD
        if op == "replace" or op == "add" or op == "remove":
            # Prepare values for comparison.
            path = module.params['object']['path']
            apiResultValue = getPathValueFromDict(apiResult.json(), path)
            getResultValue = getPathValueFromDict(getResult.json(), path)

            # If the old value was the same as the new one.
            if apiResultValue == getResultValue:
                module.exit_json(
                    msg="NO CHANGE: " + op +
                    " successful, specified path already contained value.",
                    changed=False,
                    json=apiResult.json(),
                    status_code=apiResult.status_code,
                    new_value=apiResultValue,
                    old_value=getResultValue,
                    test="N/A"
                )
            # If the old value was different to the new one.
            else:
                module.exit_json(
                    msg="CHANGED: " + op +
                    " successful, specified path was updated with new value.",
                    changed=False,
                    json=apiResult.json(),
                    status_code=apiResult.status_code,
                    new_value=apiResultValue,
                    old_value=getResultValue,
                    test="N/A"
                )

        # TEST METHOD
        elif op == "test":
            module.exit_json(
                msg="NO CHANGE: Test successful, " +
                "specified path contains value.",
                changed=False,
                json=apiResult.json(),
                status_code=apiResult.status_code,
                new_value="N/A",
                old_value="N/A",
                test=True)

        # MOVE METHOD
        elif op == "move":
            module.exit_json(
                msg="CHANGED: " + op +
                " sucessful, specified path sucessfully moved.",
                changed=True,
                json=apiResult.json(),
                status_code=apiResult.status_code,
                new_value="N/A",
                old_value="N/A",
                test="N/A"
            )

        # GET METHOD
        elif op == "get":
            module.exit_json(
                msg="NO CHANGE: " + op + " sucessful.",
                changed=True,
                json=apiResult.json(),
                status_code=apiResult.status_code,
                new_value="N/A",
                old_value="N/A",
                test="N/A"
            )

    # Server refuses bad token with 401, not always token but decent advice.
    elif apiResult.status_code == 401:
        module.fail_json(
            msg="FAILURE: Server refused action, check your credentials.",
            changed=False,
            json=apiResult.json(),
            status_code=apiResult.status_code,
            new_value="N/A",
            old_value="N/A",
            test="N/A")

    # Handle fail code returned by server when key is absent.
    elif apiResult.status_code == 500:
        # Handle absent key on remove method.
        if (op == "remove" and
                "Unable to remove nonexistant key:"
                in apiResult.json()['message']):
            module.exit_json(
                msg="NO CHANGE: Key to be removed is already non-existant",
                changed=False,
                json=apiResult.json(),
                status_code=apiResult.status_code,
                new_value="N/A",
                old_value="N/A",
                test="N/A"
            )
        # Handle absent key on move method.
        elif (op == "move" and
              "Unable to remove nonexistant key:"
              in apiResult.json()['message']):
            module.fail_json(
                msg="FAILED: Key to be moved does not exist in this path.",
                changed=False,
                json=apiResult.json(),
                status_code=apiResult.status_code,
                new_value="N/A",
                old_value="N/A",
                test="N/A"
            )
        # Handle test failure with a parameter to allow users to continue.
        elif op == "test":
            module.exit_json(
                msg="NO CHANGE: Test unsucessful, " +
                    "specified path does not contain value.",
                changed=False,
                json=apiResult.json(),
                status_code=apiResult.status_code,
                new_value="N/A",
                old_value="N/A",
                test=False)
    else:
        # Otherwise it's a general failure.
        module.fail_json(
            msg="FAILED: API call returned failure code.",
            changed=False,
            json=apiResult.json(),
            status_code=apiResult.status_code,
            new_value="N/A",
            old_value="N/A",
            test=False
        )


def getPathValueFromDict(jsonDict, path):
    # This function uses the operater.getitem function to iterate over
    # our data and retrieve the value for the key that we provide.
    # Since users provide /foo/bar/ we split it and avoid string indicies
    # errors by casting each item of mapPath to a string.
    mapPath = path.split("/")
    del mapPath[0]
    try:
        return reduce(operator.getitem, mapPath, jsonDict)
    except KeyError as e:
        return "FailedKeyError"
    except BaseException:
        raise Exception("""Failure: getPathValueFromDict -
                        failed to translate user provided path into
                        list. Check path input.""")


def getObject(module):
    # Prepare appropriate headers.
    headers = {
        'Content-Type': 'application/json',
        'Accept': 'application/json',
        'pretty': 'true',
        'Authorization': 'Bearer ' + module.params['token']
    }

    # Prepare the correct API endpoint URL.
    url = ApiEndpoint(
        module.params['host'],
        module.params['port'],
        module.params['namespace'],
        module.params['object']['name'],
        module.params['object']['type'],
        module.params['object']['operation'],
    )

    # Create a request object.
    request = HTTPRequest(
        url,
        headers,
        {}
    )

    # Execute API call and return a response to user.
    try:
        return(request.get())
    except BaseException:
        raise Exception("""Failure: getObject - API call failed,
                        user should check credentials, and API URL.""")


def patchObject(module, getResult):
    # Initialise local variables.
    op = module.params['object']['operation'].lower()
    headers = {
        'Content-Type': 'application/json-patch+json',
        'Accept': 'application/json',
        'pretty': 'true',
        'Authorization': 'Bearer ' + module.params['token']
    }

    # Decide if we need to make an API call.
    getResultValue = getPathValueFromDict(
        getResult.json(), module.params['object']['path'])

    # If the key:value pair already exists.
    if getResultValue == "FailedKeyError":
        if op == "replace":
            apiResponse(module, 0, getResult)
    else:
        if op == "add":
            apiResponse(module, 0, getResult)

    # Create a usable payload from data provided.
    payload = [{
        'op': op,
        'path': module.params['object']['path'].rstrip('/')
    }]

    # All operations apart from move/remove require an objectValue.
    if "move" not in op:
        payload[0]['value'] = module.params['object']['value']
    # Only move requires the from key.
    elif op == "move":
        payload[0]['from'] = module.params['object']['from']

    # Prepare the correct API endpoint URL.
    url = ApiEndpoint(
        module.params['host'],
        module.params['port'],
        module.params['namespace'],
        module.params['object']['name'],
        module.params['object']['type'],
        module.params['object']['operation'],
    )

    # Create HTTPRequest object
    request = HTTPRequest(
        url,
        headers,
        json.dumps(payload)
    )

    # Execute API call and return a response to user.
    try:
        apiResponse(module, request.patch(), getResult)
    except BaseException:
        raise Exception("""Failure: patchObject - API call failed,
                        user should check credentials, and API URL.""")


def main():
    module = AnsibleModule(
        supports_check_mode=False,
        argument_spec=dict(
            token=dict(required=True, no_log=True, type='str'),
            host=dict(required=True, type='str'),
            port=dict(required=False, type='int', default=443),
            version=dict(required=False, type='str', default='v3'),
            namespace=dict(required=True, type='str'),
            object=dict(required=True, type='dict')
        ),
    )

    # Define operation variable.
    op = module.params['object']['operation'].lower()

    # Confirm user gave an absolute path.
    if op != "get":
        if not re.match("^/", module.params['object']['path']):
            module.fail_json(
                msg="NO CHANGE: Declare an absolute path - e.g. /foo/baz.",
                changed=False,
            )

    # Get the object.
    try:
        getResponse = getObject(module)
    except Exception as e:
        module.fail_json(
            msg="Module Failure",
            error=e
        )

    # Chose correct operation.
    if op == "get":
        # NB: Here we pass the get response as the apiResult.
        # this is so we don't have to over-complicate the apiResponse function.
        try:
            apiResponse(module, getResponse, {})
        except Exception as e:
            module.fail_json(
                msg="Module Failure",
                error=e
            )
    elif re.search("\\b" + op + "\\b", "replace|add|remove|move|test"):
        # Attempt to execute the role. Catch error and report back to user.
        try:
            patchObject(module, getResponse)
        except Exception as e:
            module.fail_json(
                msg="Module Failure",
                error=e
            )
    else:
        module.fail_json(
            msg="""Please select an operation from:
                replace, add, remove, move, test, get""",
            changed=False
        )


if __name__ == '__main__':
    main()
