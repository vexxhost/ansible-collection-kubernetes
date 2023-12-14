# Copyright (c) 2023 VEXXHOST, Inc.
#
# Licensed under the Apache License, Version 2.0 (the "License"); you may
# not use this file except in compliance with the License. You may obtain
# a copy of the License at
#
#      http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS, WITHOUT
# WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the
# License for the specific language governing permissions and limitations
# under the License.

import json
import time

from ansible.errors import AnsibleError
from ansible.plugins.action import ActionBase


class ActionModule(ActionBase):
    def _get_node_info(self, api_endpoint, node, task_vars, tmp):
        attempts = 60
        while attempts > 0:
            ret = self._execute_module(
                module_name="ansible.builtin.uri",
                module_args={
                    "url": f"{api_endpoint}/api/v1/nodes/{node}",
                    "ca_path": "/etc/kubernetes/pki/ca.crt",
                    "client_cert": "/var/lib/kubelet/pki/kubelet-client-current.pem",
                    "status_code": 200,
                    "validate_certs": False,
                    "return_content": True,
                    "timeout": 2,
                },
                task_vars=task_vars,
                tmp=tmp,
            )

            if not ret.get("failed"):
                break

            attempts -= 1
            time.sleep(2)

        if attempts == 0:
            raise AnsibleError(f"Failed to get node info: {ret['msg']}")

        return json.loads(ret["content"])

    def _wait_for_kubelet_ready(self, task_vars, tmp):
        attempts = 60
        while attempts > 0:
            ret = self._execute_module(
                module_name="ansible.builtin.uri",
                module_args={
                    "url": "http://localhost:10248/healthz",
                    "status_code": 200,
                    "timeout": 2,
                },
                task_vars=task_vars,
                tmp=tmp,
            )

            if not ret.get("failed"):
                break

            attempts -= 1
            time.sleep(2)

        if attempts == 0:
            raise AnsibleError("Kubelet is not ready")

    def _wait_for_node_ready(self, api_endpoint, node, task_vars, tmp):
        attempts = 60
        while attempts > 0:
            node_info = self._get_node_info(
                api_endpoint,
                node,
                task_vars=task_vars,
                tmp=tmp,
            )
            conditions = node_info["status"]["conditions"]
            condition_map = {
                condition["type"]: condition["status"] for condition in conditions
            }

            if condition_map.get("Ready") == "True":
                break

            attempts -= 1
            time.sleep(2)

        if attempts == 0:
            raise AnsibleError(f"Node {node} is not ready")

    def run(self, tmp=None, task_vars=None):
        result = super().run(tmp, task_vars)

        _, new_module_args = self.validate_argument_spec(
            argument_spec={
                "api_endpoint": {"type": "str", "required": True},
                "node": {"type": "str", "required": True},
                "version": {"type": "str", "required": True},
            },
        )

        node_info = self._get_node_info(
            new_module_args["api_endpoint"],
            new_module_args["node"],
            task_vars=task_vars,
            tmp=tmp,
        )
        kubelet_version = node_info["status"]["nodeInfo"]["kubeletVersion"]

        if kubelet_version.endswith(new_module_args["version"]):
            result.update({"changed": False})
            return result

        ret = self._execute_module(
            module_name="ansible.builtin.command",
            module_args={
                "_raw_params": "kubeadm upgrade node",
            },
            task_vars=task_vars,
            tmp=tmp,
        )

        if ret.get("failed"):
            result.update(ret)
            return result

        ret = self._execute_module(
            module_name="ansible.builtin.service",
            module_args={
                "name": "kubelet",
                "state": "restarted",
                "enabled": True,
            },
            task_vars=task_vars,
            tmp=tmp,
        )

        if ret.get("failed"):
            result.update(ret)
            return result

        self._wait_for_kubelet_ready(task_vars=task_vars, tmp=tmp)
        self._wait_for_node_ready(
            new_module_args["api_endpoint"],
            new_module_args["node"],
            task_vars=task_vars,
            tmp=tmp,
        )

        result.update({"changed": True})
        return result
