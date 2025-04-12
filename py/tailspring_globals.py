import tailspring_types as ts_types

import yaml
import json
import subprocess
from pathlib import Path
from enum import Enum

class PagingEnums(Enum):
    PML4 = 1
    PDPT = 2
    PD = 3
    PT = 4
    Page = 5

sel4_name_mapping = {
    'tcb': 'seL4_TCBObject',
    'frame': 'seL4_X86_4K',
    'endpoint': 'seL4_EndpointObject',
    PagingEnums.PML4:   'seL4_X64_PML4Object',
    PagingEnums.PDPT:   'seL4_X86_PDPTObject',
    PagingEnums.PD:     'seL4_X86_PageDirectoryObject',
    PagingEnums.PT:     'seL4_X86_PageTableObject'
}

class Container:
    def __init__(self, attributes):
        self.__dict__.update(attributes)
    def __getitem__(self, attribute):
        return self.__dict__[attribute]


class Env:
    class DictWrapper(dict):
        def __init__(self, attributes):
            for key, value in attributes.items():
                if type(value) == dict:
                    value = Env.DictWrapper(value)
                self.__dict__[key] = value
                self[key] = value

    class ToolWrapper:
        def __init__(self, path):
            self.path = path

        def call(self, args, cwd=None):
            command = [self.path] + args
            return subprocess.run(command, capture_output=True, encoding='utf-8', cwd=cwd).stdout

    def addAttribute(self, attribute_name, attribute_value, tool=False):
        if tool:
            self.__dict__[attribute_name] = self.ToolWrapper(attribute_value)
            return
        if type(attribute_value) == dict:
            self.__dict__[attribute_name] = self.DictWrapper(attribute_value)
        else:
            self.__dict__[attribute_name] = attribute_value



def emitLine(*args):
    global env
    env.output_header_file.write('\n'.join(args) + '\n')

env = Env()

def initializeGlobals(args):
    config_dict = yaml.safe_load(args.config_file)

    # Need to de-duplicate startup threads that are listed in multiple vspaces - each thread needs its own name
    thread_names_duplicate_count = {} # Keep track of how many times each thread name has been encountered
    vspace_items = config_dict['vspaces'].items() # Save temporary because we're going to be modifying this dict
    startup_threads_dict_dedup = {}

    for vspace_name, thread_name in vspace_items:
        # Find how many times we've seen this thread name before
        thread_name_duplicate_count = thread_names_duplicate_count[thread_name] if thread_name in thread_names_duplicate_count else 0

        # Get the path to the executable corresponding to this thread's name
        startup_thread_path = args.startup_threads_dict[thread_name]

        # Generate a unique name
        unique_name = f"{thread_name}__{thread_name_duplicate_count}"

        # Update config dict and startup threads dict with new unique name
        config_dict['vspaces'][vspace_name] = unique_name
        startup_threads_dict_dedup[unique_name] = startup_thread_path

        # Increment duplicate count
        thread_names_duplicate_count[thread_name] = thread_name_duplicate_count + 1

    # Config
    env.addAttribute('config', config_dict)

    # Get seL4 info
    seL4_constants_raw = subprocess.run([args.get_sel4_info_path], capture_output=True, encoding='utf-8').stdout
    seL4_constants_dict = json.loads(seL4_constants_raw)
    env.addAttribute('seL4_constants', seL4_constants_dict)

    # GCC path
    env.addAttribute('gcc', args.gcc_path, tool=True)

    # Temp dir path
    env.addAttribute('temp_dir', Path(args.temp_dir))

    # Startup threads mapping
    env.addAttribute('startup_threads', {})
    for key, filename in startup_threads_dict_dedup.items():
        env.startup_threads[key] = ts_types.ThreadData(filename)

    # Output files
    env.addAttribute('output_header_file', open(args.output_header_file, 'w'))
    env.addAttribute('output_startup_threads_obj_file', args.output_startup_threads_obj_path)
