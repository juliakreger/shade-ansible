#!/usr/bin/python

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

try:
    import shade
    from shade import meta
    from shade_ansible import spec
except ImportError:
    print("failed=True msg='shade is required for this module'")

DOCUMENTATION = '''
---
module: os_compute_facts
short_description: Retrieve facts about a compute instance
extends_documentation_fragment: openstack
description:
   - Retrieve facts about a compute instance from OpenStack
options:
   name:
     description:
        - Name of the instance
     default: None
   id:
     description:
        - Id of the instance
     default: None
   mounts:
     description:
        - Optional list of dicts tying volumes to mount points
     default: None
requirements: ["shade"]
'''

EXAMPLES = '''
# Fetch facts about an instance called vm1
- os_compute:
    state: present
    cloud: rax-dfw
    name: vm1
- debug: openstack
'''

def main():

    argument_spec = spec.openstack_argument_spec(
        name=dict(default=None),
        id=dict(default=None),
        mounts=dict(default={}),
    )
    module_kwargs = spec.openstack_module_kwargs(
        mutually_exclusive=[
            ['name', 'id'],
        ],
        required_one_of=[
            ['name', 'id'],
        ],
    )
    module = AnsibleModule(argument_spec, **module_kwargs)

    try:
        cloud = shade.openstack_cloud(**module.params)
        if module.params['id']:
            server = cloud.get_server_by_id(module.params['id'])
        else:
            server = cloud.get_server_by_name(module.params['name'])
        hostvars = dict(openstack=meta.get_hostvars_from_server(
            cloud, server, mounts=module.params['mounts']))
        module.exit_json(changed=False, ansible_facts=hostvars)

    except shade.OpenStackCloudException as e:
        module.fail_json(msg=e.message)

# this is magic, see lib/ansible/module_common.py
from ansible.module_utils.basic import *
from ansible.module_utils.openstack import *
main()

