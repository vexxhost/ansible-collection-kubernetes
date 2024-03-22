# Copyright (c) 2023 BBC R&D
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

from __future__ import (absolute_import, division, print_function)
__metaclass__ = type

from ansible.errors import AnsibleActionFail
from ansible.plugins.action import ActionBase

import os
import shutil
from tempfile import TemporaryDirectory
from zipfile import ZipFile, ZipInfo


class ActionModule(ActionBase):
    def run(self, tmp=None, task_vars=None):
        super(ActionModule, self).run(tmp, task_vars)

        task_vars = task_vars or {}

        # Check required arguments
        for required_arg in ["src", "dest"]:
            if required_arg not in self._task.args:
                raise AnsibleActionFail("Missing '{}' argument.".format(required_arg))

        with TemporaryDirectory() as tmp_dir:
          zip_file_name = os.path.join(tmp_dir, "multi_copy.zip")
          source = self._find_needle('files', self._task.args['src'])
          shutil.make_archive(zip_file_name, 'gztar', source)

          # Upload and extract the files
          unarchive_args = {
              "src": zip_file_name + ".tar.gz",
          }
          for attr_arg in ["dest", "mode", "group", "owner", "attributes", "list_files"]:
              if attr_arg in self._task.args:
                  unarchive_args[attr_arg] = self._task.args[attr_arg]
          unarchive_result = self._execute_action_plugin(
              name='ansible.builtin.unarchive',
              args=unarchive_args,
              task_vars=task_vars,
          )

          return unarchive_result

    def _execute_action_plugin(self, name, args, task_vars):
        task = self._task.copy()
        task.args = args

        action_plugin = self._shared_loader_obj.action_loader.get(
            name,
            task=task,
            connection=self._connection,
            play_context=self._play_context,
            loader=self._loader,
            templar=self._templar,
            shared_loader_obj=self._shared_loader_obj,
        )

        return action_plugin.run(task_vars=task_vars)
