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
        self.vspaces = config_dict['vspaces']

class PathWrapper:
    def updatePath(self, path):
        self.path = path
    def write(self, content):
        with open(self.path, 'w') as f:
            f.write(content)

class ToolWrapper:
    def updatePath(self, path):
        self.path = path
    def call(self, args, cwd=None):
        command = [self.path] + args
        return subprocess.run(command, capture_output=True, encoding='utf-8', cwd=cwd).stdout

config = ConfigWrapper()
seL4_constants = SeL4ConstantsWrapper()
gcc = ToolWrapper()
ld = ToolWrapper()
objcopy = ToolWrapper()
temp_dir = PathWrapper()
startup_threads = {}
output_header_file = PathWrapper()
output_startup_threads_obj_file = PathWrapper()


def initializeGlobals(args):
    global config, seL4_constants, startup_threads, output_header_file, gcc, objcopy

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
    config.loadConfig(config_dict)

    # Get seL4 info
    seL4_constants_raw = subprocess.run([args.get_sel4_info_path], capture_output=True, encoding='utf-8').stdout
    seL4_constants_dict = json.loads(seL4_constants_raw)
    seL4_constants.updateDict(seL4_constants_dict)

    # GCC path
    gcc.updatePath(args.gcc_path)

    # Objcopy path
    objcopy.updatePath(args.objcopy_path)

    # Temp dir path
    temp_dir.updatePath(args.temp_dir)

    # Startup threads mapping
    for key, filename in startup_threads_dict_dedup.items():
        startup_threads[key] = ts_types.ThreadData(filename)

    # Output files
    output_header_file.updatePath(args.output_header_file_handle)
    output_startup_threads_obj_file.updatePath(args.output_startup_threads_obj_path)

__all__ = [ 'config', 'seL4_constants', 'gcc', 'objcopy', 'temp_dir', 'startup_threads',
            'output_header_file','output_startup_threads_obj_file', 'initializeGlobals']