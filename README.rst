=============
shade-ansible
=============

Ansible modules that use shade to talk to OpenStack

These are written for ansible 1.8, which means you may have to run from
the asible git repo.

To use, just pip install this repo, set ANSIBLE_MODULES_PATH to include
the modules dir - so probably `/usr/local/lib/python2.7/site-packages/shade_ansible/modules`.

example.yaml contains an example of a playbook consuming these. It assumes that
there is a cloud named `mordred` in your `os-client-config` compliant
clouds.yaml.

Features
--------

* TODO
