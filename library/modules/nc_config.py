#!/usr/bin/python
# -*- coding: utf-8 -*-

# Copyright: (c) 2019, Marc Crebassa <aalaesar@gmail.com>
# GNU General Public License v3.0+ (see COPYING or https://www.gnu.org/licenses/gpl-3.0.txt)

ANSIBLE_METADATA = {
    'metadata_version': '1.1',
    'status': ['preview'],
    'supported_by': 'community'
}

DOCUMENTATION = '''
---
module: nc_config

short_description: This module allows to edit Nextcloud's main configuration.

version_added: "2.4"

description:
    - >
      This is a python wrapper around the Nextcloud command line interface.
      This module is focused on configuring the core configuration of nextcloud. It must be run as the owner of the occ file, usually the webserver user."

options:
    path:
        description:
            - Absolute path to the nexcloud directory
        required: true
    system:
        description:
            - >
              A dictionnary containing key-values and/or dictionnary of key-values.
              For key-value, the *key* has to be the parameter's name while the *value* can be of type `integer, string, boolean or float`.
        required: true

    state:
        description:
            - define the state expected for the parameters. `present or absent`
              If `state=present`, Entries with the same index value in the nextcloud configuration will be replaced  and removed if `state=absent`.
              When using an empty value or dictionnary, the key or entire array will be removed if `state=absent` but ignored if `state=present`.
        required: false

author:
    - Marc Crebassa (@aalaesar)
'''

EXAMPLES = '''
# Configure Nexcloud strusted domains
- name: Nexcloud accept all expected domains
  nc_config:
    path: /var/www/nextcloud/
    system:
      trsuted_domain

# pass in a message and have changed true
- name: Test with a message and changed output
  my_test:
    name: hello world
    new: true

# fail the module
- name: Test failure of the module
  my_test:
    name: fail me
'''

RETURN = '''#'''

from ansible.module_utils.basic import AnsibleModule
import os,sys,json

def run_module():
    # define available arguments/parameters a user can pass to the module
    module_args = dict(
        path=dict(
            type='str',
            required=True
            ),
        configuration=dict(
            type='dict',
            required=True,
            aliases= ['config','conf']
            ),
        applications=dict(
            type='dict',
            required=True,
            aliases= ['apps']
            ),
        state=dict(
            type='str',
            choices=['present', 'absent'],
            required=False,
            default='present'
            )
    )
    result = dict(
        changed=False
    )
    module = AnsibleModule(
        argument_spec=module_args,
        supports_check_mode=True
    )
    #  remove occ if present in the path
    if (module.params['path'].split('/')[-1] == 'occ'):
        occ = os.path.dirname(module.params['path'])
        try:
            assert 'occ' in os.listdir(module.params['path'])
        except AssertionError:
            module.fail_json(msg='Command line tool not found in {}'.format(module.params['path']), **result)
        except OSError:
            module.fail_json(msg='{} is not a valid directory'.format(module.params['path']), **result)
    else:
        occ = module.params['path']
    # Verify it can be executed
    try:
        assert os.access(occ, os.X_OK)
    except AssertionError:
        module.fail_json(msg='Unable to run command line interface. Check owner/permissions.', **result)

    # load current configuration
    OcCurrentConfig = json.loads(module.run_command('php occ config:list --output=json --private', cwd=occ))
    OcSystemConfig = OcCurrentConfig['system']
    OcTypesMap = dict(
        unicode = "string",
        bool = "boolean",
        int = "integer",
        float = "float",
        str = "string"
    )
    # OcAppsConfig = OcCurrentConfig['apps']
    OcSystemSet = "php occ config:system:set"
    OcSystemDelete = "php occ config:system:delete"

    for conf,value_ in module.params['configuration']:
        if (type(value_) is dict) and value_:
            try:
                # if config dict exists in the current config but is not a dict :
                # fail the module.
                if type(OcSystemConfig[conf]) is not dict:
                    module.fail_json(msg='Incompatible parameter: not an array', **result)
            except KeyError:
                # if the config dict doesn't exists (and is expected) : create it.
                if (module.params['state'] == 'present'):
                    for k,v in value_:
                        fullCommand_ = [OcSystemSet, conf, str(k) , "--value='"+v+"'", '--type='+OcTypesMap[type(v)] ]
                        if not module.check_mode:
                            module.run_command(' '.join(fullCommand_), cwd=occ)
                        result['changed'] = True
            else:
                # if the config dict exists, check each key:
                for k,v in value_:
                    fullCommand_ = [OcSystemSet, conf, str(k) , "--value='"+str(v)+"'", '--type='+OcTypesMap[type(v)] ]
                    try:
                        # if key exists in current config and is not equal to expected value:
                        if (OcSystemConfig[conf][k] != v) and (module.params['state'] == 'present'):
                            # fullCommand_ = [OcSystemSet, conf, str(k) , "--value='"+v+"'" ]
                            if not module.check_mode:
                                module.run_command(' '.join(fullCommand_), cwd=occ)
                            result['changed'] = True
                        # if key is required to be absent: delete it.
                        elif module.params['state'] == 'absent':
                            fullCommand_ = [OcSystemDelete, conf, str(k)]
                            if not module.check_mode:
                                module.run_command(' '.join(fullCommand_), cwd=occ)
                            result['changed'] = True
                    except KeyError:
                    # if key doesn't exists (and is expected) create it.
                        if module.params['state'] == 'present':
                            if not module.check_mode:
                                module.run_command(' '.join(fullCommand_), cwd=occ)
                            result['changed'] = True
               
        elif type(value_) is list:
            module.fail_json(msg='Incompatible parameter: can\'t be a list', **result)
        elif type(value_) in [unicode, str, bool, int, float]:
            fullCommand_ = [OcSystemSet, conf, "--value='"+str(value_)+"'", '--type='+OcTypesMap[type(value_)]]
            # if value exists in the current configuration and is required to be absent
            if (conf in OcSystemConfig.keys()) and (module.params['state'] == 'absent'):
                # then remove it
                if not module.check_mode:
                    module.run_command(' '.join([OcSystemDelete, conf]), cwd=occ)
                result['changed'] = True
            # if value exists in the current configuration and is required to be present
            # and is different, update !
            elif (conf in OcSystemConfig.keys()) and OcSystemConfig[conf] != value_:
                if not module.check_mode:
                    module.run_command(' '.join(fullCommand_), cwd=occ)
                result['changed'] = True

                
        elif not value_:
            # if value is empty...
            # ...and it exists in the current configuration and is required to be absent
            if (conf in OcSystemConfig.keys()) and (module.params['state'] == 'absent'):
                # then remove it
                if not module.check_mode:
                    module.run_command(' '.join([OcSystemDelete, conf]), cwd=occ)
                result['changed'] = True
            



    # in the event of a successful module execution, you will want to
    # simple AnsibleModule.exit_json(), passing the key/value results
    module.exit_json(**result)

def main():
    run_module()

if __name__ == '__main__':
    main()