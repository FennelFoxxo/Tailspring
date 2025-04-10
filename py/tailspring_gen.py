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
    
    parser.add_argument('config_file', type=argparse.FileType('r'), help='Path to the configuration file')
    parser.add_argument('get_sel4_info_program', type=lambda x: isValidFile(parser, x), help='Path to the compiled get_sel4_info binary')
    parser.add_argument('output_file', type=argparse.FileType('w'), help='Path to the output generated header file')
    parser.add_argument('thread_executables', nargs='*', action=KeyValueAction, help='Key-value pairs mapping executable names in the configuration file to the executable path')
    
    args = parser.parse_args()
    
    initializeGlobals(args.config_file, args.get_sel4_info_program, args.output_file, args.thread_executables)

if __name__ == '__main__':
    processArgs()

    header_string = ts_core.genTailspringHeader(config, thread_executables)
    output_file.write(header_string)
