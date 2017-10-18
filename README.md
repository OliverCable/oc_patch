# Ansible Role: oc_patch

This ansible custom module is used to edit objects within openshift.

To find more about the APIs and json used:

- [JSON Patch details and libraries](http://jsonpatch.com/)
- [Very detailed JSON Patch information](https://tools.ietf.org/html/rfc6902#section-4.3)
- [Openshift Enterprise v1 REST API](https://docs.openshift.com/enterprise/3.2/rest_api/openshift_v1.html)
- [Kubernetes API](https://docs.openshift.com/container-platform/3.6/rest_api/kubernetes_v1.html)
- [Kubernetes ConfigMap](https://kubernetes.io/docs/tasks/configure-pod-container/configmap/#create-configmaps-from-directories)
- [Openshift API commandline examples](https://bierkowski.com/openshift-cli-morsels-updating-objects-non-interactively/)

## Requirements

1. Openshift cluster
2. Ansible.

## Role Variables
1. Provide a token for OCP from Ansible Vault.

## Example Playbook

Example of how to use this role:

```
---
- hosts: local
  connection: local
  gather_facts: True
  vars_files:
    - ocp-vault.yml
  tasks:

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
```
