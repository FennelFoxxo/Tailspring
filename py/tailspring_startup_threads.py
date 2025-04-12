from tailspring_types import *
from tailspring_globals import *

def getLinkerScript():
    final_section_name = '.startup_threads_data'
    return f'SECTIONS {{ {final_section_name} : {{ *(.data) }} }}'

def genStartupThreadsObjFile():
    segment_load_ops = []
    # Generate all our individual object files for each segment
    for vspace_name, thread_name in env.config.vspaces.items():
        thread_data = env.startup_threads[thread_name]
        for i in range(thread_data.getNumSegments()):
            segment_load_ops.append(genSegmentObjectFile(thread_data.getSegment(i), thread_name, i))

    # Write a small linker script
    linker_script_path = env.temp_dir / 'script.ld'
    with open(linker_script_path, 'w') as f:
        f.write(getLinkerScript())

    # Combine each object file into final object file
    env.gcc.call([  '-static', '-nostdlib', '-Wl,-r,--build-id=none', '-Wl,-T', linker_script_path, '-o', env.output_startup_threads_obj_file]
                    + [op.getPath() for op in segment_load_ops])

    return segment_load_ops


def genSegmentObjectFile(segment, thread_name, segment_number):
    obj_file_name_no_ext = f'startup_thread_{thread_name}_segment_{segment_number}'

    # Write raw segment data to file
    with open(env.temp_dir / f'{obj_file_name_no_ext}.bin', 'wb') as f:
        p_filesz = f.write(segment.data())

        # We only wrote p_filesz byets, but we actually need to reserve p_memsz bytes
        p_memsz = segment['p_memsz']
        padding_needed = 4096 - (p_memsz % 4096)
        f.write(b'0'*(p_memsz - p_filesz + padding_needed))

    # Use linker to package binary data as linkable object file
    env.gcc.call([  '-static', '-nostdlib', '-fno-lto', '-Wl,-r,-b,binary',   # Flags
                    f'{obj_file_name_no_ext}.bin',  # Input file
                    '-o', f'{obj_file_name_no_ext}.o' # Output file
                ], cwd=env.temp_dir)
    return SegmentLoadOperation(segment['p_vaddr'], segment['p_memsz'], env.temp_dir, obj_file_name_no_ext)