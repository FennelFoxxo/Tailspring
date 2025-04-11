from tailspring_types import *
from tailspring_globals import *

def getLinkerScript():
    final_section_name = '.startup_threads_data'
    return f'SECTIONS {{ {final_section_name} : {{ *(.data) }} }}'

def genStartupThreadsObjFile():
    segment_load_ops = []
    # Generate all our individual object files for each segment
    for vspace_name, thread_name in config.vspaces.items():
        thread_data = startup_threads[thread_name]
        for i in range(thread_data.getNumSegments()):
            segment_load_ops.append(genSegmentObjectFile(thread_data.getSegment(i), thread_name, i))
    
    # Write a small linker script
    linker_script_path = f'{temp_dir.path}/script.ld'
    with open(linker_script_path, 'w') as f:
        f.write(getLinkerScript())
    
    # Combine each object file into final object file
    gcc.call([  '-static', '-nostdlib', '-Wl,-r,--build-id=none', '-Wl,-T', linker_script_path, '-o', output_startup_threads_obj_file.path]
                + [op.getPath() for op in segment_load_ops])
    
    return segment_load_ops


def genSegmentObjectFile(segment, thread_name, segment_number):
    obj_file_name_no_ext = f'startup_thread_{thread_name}_segment_{segment_number}'
    
    # Write raw segment data to file
    with open(f'{temp_dir.path}/{obj_file_name_no_ext}.bin', 'wb') as f:
        p_filesz = f.write(segment.data())
        
        # We only wrote p_filesz byets, but we actually need to reserve p_memsz bytes
        p_memsz = segment['p_memsz']
        padding_needed = 4096 - (p_memsz % 4096)
        f.write(b'0'*(p_memsz - p_filesz + padding_needed))
    
    # Use linker to package binary data as linkable object file
    gcc.call([  '-static', '-nostdlib', '-fno-lto', '-Wl,-r,-b,binary',   # Flags
                f'{obj_file_name_no_ext}.bin',  # Input file
                '-o', f'{obj_file_name_no_ext}.o' # Output file
            ], cwd=temp_dir.path)
    return SegmentLoadOperation(segment['p_vaddr'], segment['p_memsz'], temp_dir.path, obj_file_name_no_ext)