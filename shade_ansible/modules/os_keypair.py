#!/usr/bin/python

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

import time

try:
    import shade
    from shade_ansible import spec
except ImportError:
    print("failed=True msg='shade is required for this module'")


DOCUMENTATION = '''
---
module: os_keypair
short_description: Add/Delete a keypair from OpenStack
extends_documentation_fragment: openstack
description:
   - Add or Remove key pair from OpenStack
options:
   state:
     description:
        - Indicate desired state of the resource
     choices: ['present', 'absent']
     default: present
   name:
     description:
        - Name that has to be given to the key pair
     required: true
     default: None
   public_key:
     description:
        - The public key that would be uploaded to nova and injected to vm's upon creation
     required: false
     default: None

requirements: ["shade"]
'''

EXAMPLES = '''
# Creates a key pair with the running users public key
- os_keypair: state=present username=admin
                password=admin project_name=admin name=ansible_key
                public_key={{ lookup('file','~/.ssh/id_rsa.pub') }}

# Creates a new key pair and the private key returned after the run.
- os_keypair: state=present username=admin password=admin
                project_name=admin name=ansible_key
'''

def main():
    argument_spec = spec.openstack_argument_spec(
        name=dict(required=True),
        public_key=dict(default=None),
    )
    module_kwargs = spec.openstack_module_kwargs()
    module = AnsibleModule(argument_spec, **module_kwargs)

    try:
        nova = shade.openstack_cloud(**module.params)

        if module.params['state'] == 'present':
            for key in nova.list_keypairs():
                if key.name == module.params['name']:
                    if module.params['public_key'] and (module.params['public_key'] != key.public_key ):
                        module.fail_json(msg = "name {} present but key hash not the same as offered.  Delete key first.".format(key['name']))
                    else:
                        module.exit_json(changed = False, result = "Key present")            
            try:
                key = nova.create_keypair(module.params['name'], module.params['public_key'])
            except Exception, e:
                module.exit_json(msg = "Error in creating the keypair: %s" % e.message)
            if not module.params['public_key']:
                module.exit_json(changed = True, key = key.private_key)
            module.exit_json(changed = True, key = None)
        if module.params['state'] == 'absent':
            for key in nova.list_keypairs():
                if key.name == module.params['name']:
                    try:
                        nova.delete_keypair(module.params['name'])
                    except Exception, e:
                        module.fail_json(msg = "The keypair deletion has failed: %s" % e.message)
                    module.exit_json( changed = True, result = "deleted")
            module.exit_json(changed = False, result = "not present")
    except shade.OpenStackCloudException as e:
        module.fail_json(msg=e.message)

# this is magic, see lib/ansible/module_common.py
from ansible.module_utils.basic import *
from ansible.module_utils.openstack import *
main()

