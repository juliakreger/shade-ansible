#!/usr/bin/python
#coding: utf-8 -*-

# Copyright (c) 2014 Hewlett-Packard Development Company, L.P.
# Copyright (c) 2013, Benno Joy <benno@ansible.com>
# Copyright (c) 2013, John Dewey <john@dewey.ws>
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

import operator
import os
import time

try:
    import shade
    from shade import meta
    from shade_ansible import spec
except ImportError:
    print("failed=True msg='shade is required for this module'")

from novaclient.v1_1 import client as nova_client
from novaclient.v1_1 import floating_ips 
from novaclient import exceptions
from novaclient import utils


DOCUMENTATION = '''
---
module: os_compute
short_description: Create/Delete Compute Instances from OpenStack
extends_documentation_fragment: openstack
description:
   - Create or Remove compute instances from OpenStack.
options:
   state:
     description:
        - Indicate desired state of the resource
     choices: ['present', 'absent']
     default: present
   name:
     description:
        - Name that has to be given to the instance
     required: true
     default: None
   image_id:
     description:
        - The id of the base image to boot. Mutually exclusive with image_name
     required: true
     default: None
   image_name:
     description:
        - The name of the base image to boot. Mutually exclusive with image_id
     required: true
     default: None
   image_exclude:
     description:
        - Text to use to filter image names, for the case, such as HP, where there are multiple image names matching the common identifying portions. image_exclude is a negative match filter - it is text that may not exist in the image name. Defaults to "(deprecated)"
   flavor_id:
     description:
        - The id of the flavor in which the new instance has to be created. Mutually exclusive with flavor_ram
     required: false
     default: 1
   flavor_ram:
     description:
        - The minimum amount of ram in MB that the flavor in which the new instance has to be created must have. Mutually exclusive with flavor_id
     required: false
     default: 1
   flavor_include:
     description:
        - Text to use to filter flavor names, for the case, such as Rackspace, where there are multiple flavors that have the same ram count. flavor_include is a positive match filter - it must exist in the flavor name.
   key_name:
     description:
        - The key pair name to be used when creating a instance
     required: false
     default: None
   security_groups:
     description:
        - The name of the security group to which the instance should be added
     required: false
     default: None
   nics:
     description:
        - A list of network id's to which the instance's interface should be attached
     required: false
     default: None
   public_ip:
     description:
        - Ensure instance has public ip however the cloud wants to do that
     required: false
     default: 'yes'
   floating_ips:
     decription:
        - list of valid floating IPs that pre-exist to assign to this node
     required: false
     default: None
   floating_ip_pools:
     description:
        - list of floating IP pools from which to choose a floating IP
     required: false
     default: None
   meta:
     description:
        - A list of key value pairs that should be provided as a metadata to the new instance
     required: false
     default: None
   wait:
     description:
        - If the module should wait for the instance to be created.
     required: false
     default: 'yes'
   timeout:
     description:
        - The amount of time the module should wait for the instance to get into active state
     required: false
     default: 180
   config_drive:
     description:
        - Whether to boot the server with config drive enabled
     required: false
     default: 'no'
   userdata:
     description:
        - Opaque blob of data which is made available to the instance
     required: false
     default: None
requirements: ["shade"]
'''

EXAMPLES = '''
# Creates a new instance and attaches to a network and passes metadata to the instance
- os_compute:
       state: present
       username: admin
       password: admin
       project_name: admin
       name: vm1
       image_id: 4f905f38-e52a-43d2-b6ec-754a13ffb529
       key_name: ansible_key
       timeout: 200
       flavor_id: 4
       nics:
         - net-id: 34605f38-e52a-25d2-b6ec-754a13ffb723
       meta:
         hostname: test1
         group: uge_master

# Creates a new instance in HP Cloud AE1 region availability zone az2 and automatically assigns a floating IP
- name: launch a compute instance
  hosts: localhost
  tasks:
  - name: launch an instance
    os_compute:
      state: present
      username: username
      password: Equality7-2521
      project_name: username-project1
      name: vm1
      auth_url: https://region-b.geo-1.identity.hpcloudsvc.com:35357/v2.0/
      region_name: region-b.geo-1
      availability_zone: az2
      image_id: 9302692b-b787-4b52-a3a6-daebb79cb498
      key_name: test
      timeout: 200
      flavor_id: 101
      security_groups: default
      auto_floating_ip: yes

# Creates a new instance in HP Cloud AE1 region availability zone az2 and assigns a pre-known floating IP
- name: launch a compute instance
  hosts: localhost
  tasks:
  - name: launch an instance
    os_compute:
      state: present
      username: username
      password: Equality7-2521
      project_name: username-project1
      name: vm1
      auth_url: https://region-b.geo-1.identity.hpcloudsvc.com:35357/v2.0/
      region_name: region-b.geo-1
      availability_zone: az2
      image_id: 9302692b-b787-4b52-a3a6-daebb79cb498
      key_name: test
      timeout: 200
      flavor_id: 101
      floating-ips:
        - 12.34.56.79

# Creates a new instance with 4G of RAM on Ubuntu Trusty, ignoring deprecated images
- name: launch a compute instance
  hosts: localhost
  tasks:
  - name: launch an instance
    os_compute:
      name: vm1
      state: present
      username: username
      password: Equality7-2521
      project_name: username-project1
      auth_url: https://region-b.geo-1.identity.hpcloudsvc.com:35357/v2.0/
      region_name: region-b.geo-1
      image_name: Ubuntu Server 14.04
      image_exclude: deprecated
      flavor_ram: 4096

# Creates a new instance with 4G of RAM on Ubuntu Trusty on a Rackspace Performance node in DFW
- name: launch a compute instance
  hosts: localhost
  tasks:
  - name: launch an instance
    os_compute:
      name: vm1
      state: present
      username: username
      password: Equality7-2521
      project_name: username-project1
      auth_url: https://identity.api.rackspacecloud.com/v2.0/
      region_name: DFW
      image_name: Ubuntu 14.04 LTS (Trusty Tahr) (PVHVM)
      flavor_ram: 4096
      flavor_include: Performance
'''


def _exit_hostvars(module, cloud, server, changed=True):
    hostvars = meta.get_hostvars_from_server(cloud, server)
    module.exit_json(changed=changed, id=server.id, openstack=hostvars)


def _delete_server(module, cloud):
    try:
        cloud.delete_server(
            module.params['name'], wait=module.params['wait'],
            timeout=module.params['timeout'])
    except Exception as e:
        module.fail_json( msg = "Error in deleting vm: %s" % e.message)
    module.exit_json(changed=True, result='deleted')


def _get_image_id(module, cloud):
    if module.params['image_id']:
        return module.params['image_id']
    return cloud.get_image_by_name(
        module.params['image_name'], module.params['image_exclude']).id


def _get_flavor_id(module, cloud):
    if module.params['flavor_id']:
        return module.params['flavor_id']
    return cloud.get_flavor_by_ram(
        module.params['flavor_ram'], module.params['flavor_include']).id


def _create_server(module, cloud):
    image_id = _get_image_id(module, cloud)
    flavor_id = _get_flavor_id(module, cloud)

    bootargs = [module.params['name'], image_id, flavor_id]
    bootkwargs = {
                'nics' : module.params['nics'],
                'meta' : module.params['meta'],
                'security_groups': module.params['security_groups'].split(','),
                'userdata': module.params['userdata'],
                'config_drive': module.params['config_drive'],
    }

    for optional_param in ('region_name', 'key_name', 'availability_zone'):
        if module.params[optional_param]:
            bootkwargs[optional_param] = module.params[optional_param]

    server = cloud.create_server(
        bootargs, bootkwargs,
        ip_pool=module.params['floating_ip_pools'],
        ips=module.params['floating_ips'],
        auto_ip=module.params['auto_floating_ip'],
        wait=module.params['wait'], timeout=module.params['timeout'])

    _exit_hostvars(module, cloud, server)


def _delete_floating_ip_list(cloud, server, extra_ips):
    for ip in extra_ips:
        cloud.nova_client.servers.remove_floating_ip(
            server=server.id, address=ip)


def _check_floating_ips(module, cloud, server):
    changed = False
    if module.params['floating_ip_pools'] or module.params['floating_ips'] or module.params['auto_floating_ip']:
        ips = openstack_find_nova_addresses(server.addresses, 'floating')
        if not ips:
            # If we're configured to have a floating but we don't have one,
            # let's add one
            server = cloud.add_ips_to_server(
                server,
                auto_ip=module.params['auto_floating_ip'],
                ips=module.params['floating_ips'],
                ip_pool=module.params['floating_ip_pools'],
            )
            changed = True
        elif module.params['floating_ips']:
            # we were configured to have specific ips, let's make sure we have
            # those
            missing_ips = []
            for ip in module.params['floating_ips']:
                if ip not in ips:
                    missing_ips.append(ip)
            if missing_ips:
                server = cloud.add_ip_list(server, missing_ips)
                changed = True
            extra_ips = []
            for ip in ips:
                if ip not in module.params['floating_ips']:
                    extra_ips.append(ip)
            if extra_ips:
                _delete_floating_ip_list(cloud, server, extra_ips)
                changed = True
    return (changed, server)


def _get_server_state(module, cloud):
    server = cloud.get_server_by_name(module.params['name'])
    if server and module.params['state'] == 'present':
        if server.status != 'ACTIVE':
            module.fail_json(
                msg="The instance is available but not Active state:" + server.status)
        (ip_changed, server) = _check_floating_ips(module, cloud, server)
        _exit_hostvars(module, cloud, server, ip_changed)
    if server and module.params['state'] == 'absent':
        return True
    if module.params['state'] == 'absent':
        module.exit_json(changed = False, result = "not present")
    return True


def main():

    argument_spec = spec.openstack_argument_spec(
        name                            = dict(required=True),
        image_id                        = dict(default=None),
        image_name                      = dict(default=None),
        image_exclude                   = dict(default='(deprecated)'),
        flavor_id                       = dict(default=None),
        flavor_ram                      = dict(default=None, type='int'),
        flavor_include                  = dict(default=None),
        key_name                        = dict(default=None),
        security_groups                 = dict(default='default'),
        nics                            = dict(default=None),
        meta                            = dict(default=None),
        userdata                        = dict(default=None),
        config_drive                    = dict(default=False, type='bool'),
        auto_floating_ip                = dict(default=True, type='bool'),
        floating_ips                    = dict(default=None),
        floating_ip_pools               = dict(default=None),
    )
    module_kwargs = spec.openstack_module_kwargs(
        mutually_exclusive=[
            ['auto_floating_ip','floating_ips'],
            ['auto_floating_ip','floating_ip_pools'],
            ['floating_ips','floating_ip_pools'],
            ['image_id','image_name'],
            ['flavor_id','flavor_ram'],
        ],
    )
    module = AnsibleModule(argument_spec, **module_kwargs)

    try:
        cloud = shade.openstack_cloud(**module.params)

        if module.params['state'] == 'present':
            if not module.params['image_id'] and not module.params['image_name']:
                module.fail_json( msg = "Parameter 'image_id' or `image_name` is required if state == 'present'")
            else:
                _get_server_state(module, cloud)
                _create_server(module, cloud)
        if module.params['state'] == 'absent':
            _get_server_state(module, cloud)
            _delete_server(module, cloud)
    except shade.OpenStackCloudException as e:
        module.fail_json(msg=e.message)

# this is magic, see lib/ansible/module_common.py
from ansible.module_utils.basic import *
from ansible.module_utils.openstack import *
main()

