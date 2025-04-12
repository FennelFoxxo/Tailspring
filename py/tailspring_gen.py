import argparse
from elftools.elf.elffile import ELFFile
from elftools.common.exceptions import ELFError

import tailspring_core as ts_core
from tailspring_globals import *

class KeyValueAction(argparse.Action):
    def __call__(self, parser, namespace, values, option_string=None):
        result = {}
        if isinstance(values, list):
            for value in values:
                if '=' in value:
                    key, val = value.split('=', 1)
                    result[key] = val
        setattr(namespace, self.dest, result)

def isValidFile(parser, arg):
    try:
        with open(arg, 'r') as f:
            f.close()
        return arg
    except IOError:
        parser.error(f'"{arg}" is not a valid path')

def processArgs():
    parser = argparse.ArgumentParser(
        prog='Tailspring Parser',
        description='Generates C headers from a configuration file for the Tailspring thread loader')

    parser.add_argument('--config',
                        dest='config_file',
                        required=True,
                        type=argparse.FileType('r'),
                        help='Path to the configuration file')

    parser.add_argument('--get-sel4-info',
                        dest='get_sel4_info_path',
                        required=True,
                        type=lambda x: isValidFile(parser, x),
                        help='Path to the compiled get_sel4_info binary')

    parser.add_argument('--gcc-path',
                        dest='gcc_path',
                        required=True,
                        help='Path to the GCC compiler (used for linking)')

    parser.add_argument('--temp-dir',
                        dest='temp_dir',
                        required=True,
                        help='Path to a directory to place generated intermediate files')

    parser.add_argument('--startup-threads-mapping',
                        dest='startup_threads_dict',
                        required=True,
                        nargs='*',
                        action=KeyValueAction,
                        help='Key-value pairs mapping startup thread names in the config file to the executable path')

    parser.add_argument('--output-header',
                        dest='output_header_file',
                        required=True,
                        help='Path to the output generated header file')

    parser.add_argument('--output-startup-threads-obj',
                        dest='output_startup_threads_obj_path',
                        required=True,
                        help='Path to the output generated object file containing startup thread data')

    return parser.parse_args()

if __name__ == '__main__':
    args = processArgs()
    initializeGlobals(args)

    ts_core.genTailspringData()