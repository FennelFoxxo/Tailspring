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

    parser.add_argument('--thread-executable-mapping',
                        dest='thread_executable_dict',
                        required=True,
                        nargs='*',
                        action=KeyValueAction,
                        help='Key-value pairs mapping executable names in the configuration file to the path of the executable')

    parser.add_argument('--output-header',
                        dest='output_header_file_handle',
                        required=True,
                        type=argparse.FileType('w'),
                        help='Path to the output generated header file')

    args = parser.parse_args()

    initializeGlobals(  config_file=args.config_file,
                        get_sel4_info_path=args.get_sel4_info_path,
                        output_header_file_handle=args.output_header_file_handle,
                        thread_executables_dict=args.thread_executable_dict)

if __name__ == '__main__':
    processArgs()

    header_string = ts_core.genTailspringHeader(config, thread_executables)
    output_header_file.write(header_string)
