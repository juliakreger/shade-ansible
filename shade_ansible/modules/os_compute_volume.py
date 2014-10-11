#!/usr/bin/python
#coding: utf-8 -*-

# This module is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# This software is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this software.  If not, see <http://www.gnu.org/licenses/>.
try:
    from novaclient.v1_1 import client as nova_client
    from novaclient import exceptions as nova_exc
except ImportError:
    print("failed=True msg='novaclient is required for this module'")
try:
    from cinderclient.v1 import client as cinder_client
    from cinderclient import exceptions as cinder_exc
except ImportError:
    print("failed=True msg='cinderclient is required for this module'")

import time

import shade
from shade_ansible import spec

DOCUMENTATION = '''
---
module: os_compute_volume
version_added: "1.8"
short_description: Attach/Detach Volumes from OpenStack VM's
extends_documentation_fragment: openstack
description:
   - Attach or Detach volumes from OpenStack VM's
options:
   state:
     description:
        - Indicate desired state of the resource
     choices: ['present', 'absent']
     default: present
   server_name:
     description:
       - Name of server you want to attach a volume to
     required: false
     default: None
   server_id:
     description:
       - ID of server you want to attach a volume to
     required: false
     default: None
   volume_name:
     description:
      - Name of volume you want to attach to a server
     required: false
     default: None
   volume_id:
     descripiton:
      - ID of volume you want to attach to a server
     required: false
     default: None
   device:
     description:
      - Device you want to attach
     required: false
     default: None
requirements: ["novaclient", "cinderclient"]
'''

EXAMPLES = '''
# Attaches a volume to a compute host
- name: attach a volume
  hosts: localhost
  tasks:
  - name: attach volume to host
    os_compute_volume:
      state: present
      username: admin
      password: admin
      project_name: admin
      auth_url: https://region-b.geo-1.identity.hpcloudsvc.com:35357/v2.0/
      region_name: region-b.geo-1
      server_name: Mysql-server
      volume_name: mysql-data
      device: /dev/vdb
'''

def _wait_for_detach(cinder, module):
    expires = float(module.params['timeout']) + time.time()
    while time.time() < expires:
        volume = cinder.volumes.get(module.params['volume_id'])
        if volume.status == 'available':
            break
    return volume


def _check_server_attachments(volume, server_id, volume_id):
    for attach in volume.attachments:
        if server_id == attach['server_id']:
            return True
    return False


def _present_volume(nova, cinder, module):
    try:
        volume = cinder.volumes.get(module.params['volume_id'])
    except Exception as e:
        module.fail_json(msg='Error getting volume:%s' % str(e))

    try:
        if _check_server_attachments(volume, module.params['server_id']):
            # Attached. Now, do we care about device?
            if module.params['device'] and not _check_device_attachment(volume, modules.params['device']):
                nova.volumes.delete_server_volume(
                    module.params['server_id'],
                    module.params['volume_id'])
                volume = _wait_for_detach(cinder, module)
            else:
                module.exit_json(changed=False, result='Volume already attached')
    except Exception as e:
        module.fail_json(msg='Error processing volume:%s' % str(e))

    if volume.status != 'available':
        module.fail_json(msg='Cannot attach volume, not available')
    try:
        nova.volumes.create_server_volume(module.params['server_id'],
                                          module.params['volume_id'],
                                          module.params['device'])
    except Exception as e:
        module.fail_json(msg='Cannot add volume to server:%s' % str(n))

    if module.params['wait']:
        expires = float(module.params['timeout']) + time.time()
        attachment = None
        while time.time() < expires:
            volume = cinder.volumes.get(module.params['volume_id'])
            for attach in volume.attachments:
                if attach['server_id'] == module.params['server_id']:
                    attachment = attach
                    break
    module.exit_json(changed=True, id=volume.id, info=attachment)


def _absent_volume(nova, cinder, module):
    try:
        volume = cinder.volumes.get(module.params['volume_id'])
    except Exception as e:
        module.fail_json(msg='Error getting volume:%s' % str(e))

    if not _check_server_attachments(volume, module.params['server_id']):
        module.exit_json(changed=False, msg='Volume is not attached to server')

    try:
        nova.volumes.delete_server_volume(module.params['server_id'],
                                          module.params['volume_id'])
        if module.params['wait']:
            _wait_for_detach(cinder, module)
    except Exception as e:
        module.fail_json(msg='Error removing volume from server:%s' % str(e))
    module.exit_json(changed=True, result='Detached volume from server')


def main():
    argument_spec = openstack_argument_spec(
        server_id                    = dict(default=None),
        server_name                  = dict(default=None),
        volume_name                  = dict(default=None),
        volume_id                    = dict(default=None),
        device                       = dict(default=None),
        state                        = dict(default='present', choices=['absent', 'present']),
        wait                         = dict(default=False, choices=[True, False]),
        timeout                      = dict(default=180)
    )
    module_kwargs = spec.openstack_module_kwargs(
        mutually_exclusive = [
            ['volume_id','volume_name'],
            ['server_id', 'server_name']
        ],
    )
    module = AnsibleModule(argument_spec, **module_kwargs)

    try:
        cloud = shade.openstack_cloud(**module.params)
        cinder = cloud.cinder_client
        nova = cloud.nova_client

        if module.params['volume_name'] != None:
            module.params['volume_id'] = cloud.get_volume_id(
                module.params['volume_name'])

        if module.params['server_name'] != None:
            module.params['server_id'] = cloud.get_server_id(
                module.params['server_name'])

        if module.params['state'] == 'present':
            _present_volume(nova, cinder, module)
        if module.params['state'] == 'absent':
            _absent_volume(nova, cinder, module)

    except shade.OpenStackCloudException as e:
        module.fail_json(msg=e.message)

# this is magic, see lib/ansible/module_utils/common.py
from ansible.module_utils.basic import *
from ansible.module_utils.openstack import *
main()
