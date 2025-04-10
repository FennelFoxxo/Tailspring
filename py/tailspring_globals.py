import tailspring_types as ts_types

import yaml
import json
import subprocess

class Container:
    def __init__(self, attributes):
        self.__dict__.update(attributes)
    def __getitem__(self, attribute):
        return self.__dict__[attribute]

class SeL4ConstantsWrapper:
    def updateDict(self, seL4_generated_dict):
        self.literals = Container(seL4_generated_dict["literals"])
        self.found_symbols = Container(seL4_generated_dict["found_symbols"])
        self.object_sizes = Container(seL4_generated_dict["object_sizes"])

class ConfigWrapper:
    def loadConfig(self, config_dict):
        self.caps = config_dict['caps']
        self.cap_modifications = config_dict['cap_modifications']
        self.cnodes = config_dict['cnodes']
        self.caps = config_dict['caps']

class OutputFileWrapper:
    def updateFileHandle(self, file_handle):
        self.file = file_handle
    def write(self, content):
        self.file.write(content)

seL4_constants = SeL4ConstantsWrapper()
config = ConfigWrapper()
thread_executables = None
output_file = OutputFileWrapper()


def initializeGlobals(config_file, get_sel4_info_path, output_file_, thread_executables_dict):
    global seL4_constants, config, thread_executables, output_file
    
    config.loadConfig(yaml.safe_load(config_file))
    
    seL4_constants_raw = subprocess.check_output(get_sel4_info_path, shell=False, encoding='utf-8')
    seL4_constants_dict = json.loads(seL4_constants_raw)
    seL4_constants.updateDict(seL4_constants_dict)
    
    output_file.updateFileHandle(output_file_)
    
    thread_executables = thread_executables_dict

__all__ = ['seL4_constants', 'config', 'thread_executables', 'output_file', 'initializeGlobals']