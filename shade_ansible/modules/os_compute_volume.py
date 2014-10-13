#!/usr/bin/python
#coding: utf-8 -*-

# Copyright (c) 2014 Hewlett-Packard Development Company, L.P.
#
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

import time

try:
    import shade
    from shade import meta
    from shade_ansible import spec
except ImportError:
    print("failed=True msg='shade is required for this module'")


DOCUMENTATION = '''
---
module: os_compute_volume
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
requirements: ["shade"]
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


def _check_server_attachments(volume, server_id):
    for attach in volume.attachments:
        if server_id == attach['server_id']:
            return True
    return False


def _check_device_attachment(volume, device, server_id):
    for attach in volume.attachments:
        if server_id == attach['server_id'] and device == attach['device']:
            return True
    return False


def _present_volume(cloud, nova, cinder, module):
    try:
        volume = cinder.volumes.get(module.params['volume_id'])
    except Exception as e:
        module.fail_json(msg='Error getting volume:%s' % str(e))

    try:
        if _check_server_attachments(volume, module.params['server_id']):
            # Attached. Now, do we care about device?
            if (module.params['device'] and
                not _check_device_attachment(
                    volume, modules.params['device'],
                    module.params['server_id'])):
                nova.volumes.delete_server_volume(
                    module.params['server_id'],
                    module.params['volume_id'])
                volume = _wait_for_detach(cinder, module)
            else:
                server = cloud.get_server_by_id(module.params['server_id'])
                hostvars = meta.get_hostvars_from_server(cloud, server)
                module.exit_json(
                    changed=False,
                    result='Volume already attached',
                    attachments=volume.attachments)
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

    if attachment:
        server = cloud.get_server_by_id(module.params['server_id'])
        hostvars = meta.get_hostvars_from_server(cloud, server)
        module.exit_json(
            changed=True, id=volume.id, attachments=volume.attachments,
            openstack=hostvars,
        )
    module.fail_json(
        msg='Adding volume {volume} to server {server} timed out'.format(
            volume=volume.display_name, server=module.params['server_id']))


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
    argument_spec = spec.openstack_argument_spec(
        server_id=dict(default=None),
        server_name=dict(default=None),
        volume_id=dict(default=None),
        volume_name=dict(default=None),
        device=dict(default=None),
    )
    module_kwargs = spec.openstack_module_kwargs(
        mutually_exclusive=[
            ['server_id', 'server_name'],
            ['volume_id', 'volume_name'],
        ],
        required_one_of=[
            ['server_id', 'server_name'],
            ['volume_id','volume_name'],
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
            _present_volume(cloud, nova, cinder, module)
        if module.params['state'] == 'absent':
            _absent_volume(nova, cinder, module)

    except shade.OpenStackCloudException as e:
        module.fail_json(msg=e.message)

# this is magic, see lib/ansible/module_utils/common.py
from ansible.module_utils.basic import *
from ansible.module_utils.openstack import *
main()
