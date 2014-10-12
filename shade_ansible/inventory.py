#!/usr/bin/env python

# Copyright (c) 2012, Marco Vito Moscaritolo <marco@agavee.com>
# Copyright (c) 2013, Jesse Keating <jesse.keating@rackspace.com>
# Copyright (c) 2014, Hewlett-Packard Development Company, L.P.
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

import sys
import time
import re
import os
import argparse
import collections
from novaclient import exceptions
from types import NoneType

try:
    import json
except:
    import simplejson as json

import os_client_config
import shade

NON_CALLABLES = (basestring, bool, dict, int, list, NoneType)


class NovaInventory(object):

    def __init__(self, private=False, refresh=False):
        self.openstack_config = os_client_config.config.OpenStackConfig(
            os_client_config.config.CONFIG_FILES.append(
                '/etc/ansible/openstack.yml'),
            private)
        self.clouds = shade.openstack_clouds(self.openstack_config)
        self.refresh = refresh

        self.cache_max_age = self.openstack_config.get_cache_max_age()
        cache_path = self.openstack_config.get_cache_path()

        # Cache related
        if not os.path.exists(cache_path):
            os.makedirs(cache_path)
        self.cache_file = os.path.join(cache_path, "shade-ansible.cache")

    def is_cache_stale(self):
        ''' Determines if cache file has expired, or if it is still valid '''
        if os.path.isfile(self.cache_file):
            mod_time = os.path.getmtime(self.cache_file)
            current_time = time.time()
            if (mod_time + self.cache_max_age) > current_time:
                return False
        return True

    def get_host_groups(self):
        if self.refresh or self.is_cache_stale():
            groups = self.get_host_groups_from_cloud()
            self.write_cache(groups)
        else:
            return json.load(open(self.cache_file, 'r'))
        return groups

    def write_cache(self, groups):
        with open(self.cache_file, 'w') as cache_file:
            cache_file.write(self.json_format_dict(groups))

    def _get_groups_from_server(self, cloud, server, server_vars):
        groups = []

        region = cloud.region
        cloud_name = cloud.name

        # Create a group for the cloud
        groups.append(cloud_name)

        # Create a group on region
        groups.append(region)

        # And one by cloud_region
        groups.append("%s_%s" % (cloud_name, region))

        # Check if group metadata key in servers' metadata
        group = server.metadata.get('group')
        if group:
            groups.append(group)

        for extra_group in server.metadata.get('groups', '').split(','):
            if extra_group:
                groups.append(extra_group)

        groups.append('instance-%s' % server.id)

        flavor_id = server.flavor['id']
        groups.append('flavor-%s' % flavor_id)
        flavor_name = cloud.get_flavor_name(flavor_id)
        if flavor_name:
            groups.append('flavor-%s' % flavor_name)

        image_id = server.image['id']
        groups.append('image-%s' % image_id)
        image_name = cloud.get_image_name(image_id)
        if image_name:
            groups.append('image-%s' % image_name)

        for key, value in server.metadata.iteritems():
            groups.append('meta_%s_%s' % (key, value))

        az = server_vars.get('az', None)
        if az:
            # Make groups for az, region_az and cloud_region_az
            groups.append(az)
            groups.append('%s_%s' % (region, az))
            groups.append('%s_%s_%s' % (cloud.name, region, az))
        return groups

    def _get_hostvars_from_server(self, cloud, server):
        server_vars = dict()
        # Fist, add an IP address
        if (cloud.private):
            interface_ips = shade.find_nova_addresses(
                getattr(server, 'addresses'), 'fixed', 'private')
        else:
            interface_ips = shade.find_nova_addresses(
                getattr(server, 'addresses'), 'floating', 'public')
        # TODO: I want this to be richer
        server_vars['interface_ip'] = interface_ips[0]

        server_vars.update(to_dict(server))

        server_vars['nova_region'] = cloud.region
        server_vars['openstack_cloud'] = cloud.name

        server_vars['cinder_volumes'] = [
            to_dict(f, slug=False) for f in cloud.get_volumes(server)]

        az = server_vars.get('nova_os-ext-az_availability_zone', None)
        if az:
            server_vars['nova_az'] = az

        return server_vars

    def _get_server_meta(self, cloud, server):
        server_vars = self._get_hostvars_from_server(cloud, server)
        groups = self._get_groups_from_server(cloud, server, server_vars)
        return dict(server_vars=server_vars, groups=groups)

    def get_host_groups_from_cloud(self):
        groups = collections.defaultdict(list)
        hostvars = collections.defaultdict(dict)

        for cloud in self.clouds:

            # Cycle on servers
            for server in cloud.list_servers():

                meta = self._get_server_meta(cloud, server)

                if 'interface_ip' not in meta['server_vars']:
                    # skip this host if it doesn't have a network address
                    continue

                server_vars = meta['server_vars']
                server_vars['ansible_ssh_host'] = server_vars['interface_ip']
                hostvars[server.name] = server_vars

                for group in meta['groups']:
                    groups[group].append(server.name)

        if hostvars:
            groups['_meta'] = {'hostvars': hostvars}
        return groups

    def json_format_dict(self, data):
        return json.dumps(data, sort_keys=True, indent=2)

    def list_instances(self):
        groups = self.get_host_groups()
        # Return server list
        print(self.json_format_dict(groups))

    def get_host(self, hostname):
        groups = self.get_host_groups()
        hostvars = groups['_meta']['hostvars']
        if hostname in hostvars:
            print(self.json_format_dict(hostvars[hostname]))


def to_dict(obj, slug=True, prefix='nova'):
    instance = {}
    for key in dir(obj):
        value = getattr(obj, key)
        if (isinstance(value, NON_CALLABLES) and not key.startswith('_')):
            if slug:
                key = slugify(prefix, key)
            instance[key] = value

    return instance


# TODO: this is something both various modules and plugins could use
def slugify(pre='', value=''):
    sep = ''
    if pre is not None and len(pre):
        sep = '_'
    return '%s%s%s' % (pre,
                       sep,
                       re.sub('[^\w-]', '_', value).lower().lstrip('_'))


def parse_args():
    parser = argparse.ArgumentParser(description='Nova Inventory Module')
    parser.add_argument('--private',
                        action='store_true',
                        help='Use private address for ansible host')
    parser.add_argument('--refresh', action='store_true',
                        help='Refresh cached information')
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument('--list', action='store_true',
                       help='List active servers')
    group.add_argument('--host', help='List details about the specific host')
    return parser.parse_args()


def main():
    args = parse_args()
    try:
        inventory = NovaInventory(args.private, args.refresh)
        if args.list:
            inventory.list_instances()
        elif args.host:
            inventory.get_host(args.host)
    except shade.OpenStackCloudException as e:
        print(e.message)
        sys.exit(1)
    sys.exit(0)


if __name__ == '__main__':
    main()
