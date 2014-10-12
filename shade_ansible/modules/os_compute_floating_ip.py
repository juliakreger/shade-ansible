#!/usr/bin/python
#coding: utf-8 -*-

# Copyright (c) 2014 Hewlett-Packard Development Company, L.P.
# Copyright (c) 2013, Benno Joy <benno@ansible.com>
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
    from shade_ansible import spec
except ImportError:
    print "failed=True msg='shade is required'"

DOCUMENTATION = '''
---
module: os_compute_floating_ip
short_description: Associate or disassociate a particular floating IP with an instance
extends_documentation_fragment: openstack
description:
   - Associates or disassociates a specific floating IP with a particular instance
options:
   state:
     description:
        - indicates the desired state of the resource
     choices: ['present', 'absent']
     default: present
   instance_name:
     description:
        - name of the instance to which the public IP should be assigned
     required: true
     default: None
   ip_address:
     description:
        - floating ip that should be assigned to the instance
     required: true
     default: None
requirements: ["shade"]
'''

EXAMPLES = '''
# Associate a specific floating IP with an Instance
- os_compute_floating_ip:
           state=present
           username=admin
           password=admin
           project_name=admin
           ip_address=1.1.1.1
           instance_name=vm1
'''


def _get_server_state(module, nova):
    server_info = None
    server = None
    try:
        for server in nova.servers.list():
            if server:
                info = server._info
                if info['name'] == module.params['instance_name']:
                    if info['status'] != 'ACTIVE' and module.params['state'] == 'present':
                        module.fail_json(msg="The VM is available but not Active. state:" + info['status'])
                    server_info = info
                    break
    except Exception, e:
            module.fail_json(msg = "Error in getting the server list: %s" % e.message)
    return server_info, server

def _get_port_id(neutron, module, instance_id):
    kwargs = dict(device_id = instance_id)
    try:
        ports = neutron.list_ports(**kwargs)
    except Exception, e:
        module.fail_json( msg = "Error in listing ports: %s" % e.message)
    if not ports['ports']:
        return None
    return ports['ports'][0]['id']

def _get_floating_ip_id(module, neutron):
    kwargs = {
        'floating_ip_address': module.params['ip_address']
    }
    try:
        ips = neutron.list_floatingips(**kwargs)
    except Exception, e:
        module.fail_json(msg = "error in fetching the floatingips's %s" % e.message)
    if not ips['floatingips']:
        module.fail_json(msg = "Could find the ip specified in parameter, Please check")
    ip = ips['floatingips'][0]['id']
    if not ips['floatingips'][0]['port_id']:
        state = "detached"
    else:
        state = "attached"
    return state, ip

def _update_floating_ip(neutron, module, port_id, floating_ip_id):
    kwargs = {
        'port_id': port_id
    }
    try:
        result = neutron.update_floatingip(floating_ip_id, {'floatingip': kwargs})
    except Exception, e:
        module.fail_json(msg = "There was an error in updating the floating ip address: %s" % e.message)
    module.exit_json(changed = True, result = result, public_ip=module.params['ip_address'])

def main():

    argument_spec = spec.openstack_argument_spec(
        ip_address                      = dict(required=True),
        instance_name                   = dict(required=True),
    )
    module_kwargs = spec.openstack_module_kwargs()
    module = AnsibleModule(argument_spec, **module_kwargs)

    try:
        cloud = shade.openstack_cloud(**module.params)
        nova = cloud.nova_client
        neutron = cloud.neutron_client

        state, floating_ip_id = _get_floating_ip_id(module, neutron)
        if module.params['state'] == 'present':
            if state == 'attached':
                module.exit_json(changed = False, result = 'attached', public_ip=module.params['ip_address'])
            server_info, server_obj = _get_server_state(module, nova)
            if not server_info:
                module.fail_json(msg = " The instance name provided cannot be found")
            port_id = _get_port_id(neutron, module, server_info['id'])
            if not port_id:
                module.fail_json(msg = "Cannot find a port for this instance, maybe fixed ip is not assigned")
            _update_floating_ip(neutron, module, port_id, floating_ip_id)

        if module.params['state'] == 'absent':
            if state == 'detached':
                module.exit_json(changed = False, result = 'detached')
            if state == 'attached':
                _update_floating_ip(neutron, module, None, floating_ip_id)
            module.exit_json(changed = True, result = "detached")
    except shade.OpenStackCloudException as e:
        module.fail_json(msg=e.message)

# this is magic, see lib/ansible/module_common.py
from ansible.module_utils.basic import *
from ansible.module_utils.openstack import *
main()

