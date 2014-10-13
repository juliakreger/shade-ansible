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

import shade


def openstack_argument_spec(**kwargs):
    spec = dict(
        cloud=dict(default=None),
        auth_url=dict(default=None),
        username=dict(default=None),
        password=dict(default=None),
        project_name=dict(default=None),
        region_name=dict(default=None),
        availability_zone=dict(default=None),
        user_domain_name=dict(default=None),
        project_domain_name=dict(default=None),
        state=dict(default='present', choices=['absent', 'present']),
        wait=dict(default=True, type='bool'),
        timeout=dict(default=180, type='int'),
        endpoint_type=dict(
            default='publicURL', choices=['publicURL', 'internalURL']
        )
    )
    spec.update(kwargs)
    return spec


def openstack_module_kwargs(**kwargs):
    ret = dict(
        required_one_of=[
            ['cloud', 'auth_url'],
            ['cloud', 'username'],
            ['cloud', 'password'],
            ['cloud', 'project_name'],
        ]
    )
    for key in ('mutually_exclusive', 'required_together', 'required_one_of'):
        if key in kwargs:
            if key in ret:
                ret[key].extend(kwargs[key])
            else:
                ret[key] = kwargs[key]

    return ret        
