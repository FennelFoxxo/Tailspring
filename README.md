# Tailspring
Tailspring is a tool, designed to be used with the seL4 microkernel, to configure and start threads on system boot. Given a configuration file (specifying the intended system state) and a list of executables (the compiled programs for the threads which should be launched), Tailspring will generate an executable that should be set as the root task. The data for each thread is embedded within the Tailspring loader. On system boot, the Tailspring loader will load each thread into memory, set up capabilities, and pass arguments to each thread, all according to the configuration file.

# How it works
Most of the work is done up-front by a Python script which is run when the project is compiled. Here is the basic overview of what the script does:
- Just before the script is run, CMake generates a "get_sel4_info" executable which is linked with the seL4 kernel. The Python script runs this program, which outputs some info about how seL4 is configured (arch, object sizes, endianness).
- The script parses the configuration file. Every capability to be created is assigned a slot number, and a list of retype, modify, move, and copy operations is generated.
- The list of paging structures (e.g. page table, page directory) is generated for every VSpace. The paging structures are generated such that every necessary address range is mapped. This includes the executable data itself, along with the stack and IPC buffer.
- The stack for each thread is generated. The arguments specified in the config file, the address of the IPC buffer, and the address of the sysinfo function (required for musllibc to function) are used to generate the byte data for the stack, which the seL4 runtime expects to be formatted a specific way.
- The data for each thread is split into seperate object files. This includes each thread's segments, which get their own .o file, and their stacks. The idea is that these object files are linked at the beginning of the Tailspring loader, so we can rely on the system's bootloader to do the hard work of allocating memory for the threads.
- The object files are linked together into a single startup_threads.o file.
- Finally, the script finalizes the list of cap operations and generates a header file with this list.
- When the script has finished, CMake compiles the Tailspring loader. It includes the generates header and links with startup_threads.o using a custom linker script that places the contents of startup_threads.o at the very beginning of the executable.

In comparison, the thread loader itself is kept relatively simple:
- Every operation listed in the generated header is iterated over. Each operation is simple, and might involve retyping memory into a specific capability, moving/copying/minting/mutating caps, mapping a paging structure or a frame, setting up or starting a TCB, or mapping a binary chunk into memory.
- With regards to mapping a chunk into memory, this ties back to the generated object files. seL4 gives the root task a list of frame caps that contain the root task itself. We know the lowest address in the root task (provided by the _startup_threads_data_start symbol in the linker script) and the starting address of where the object file ended up in the Tailspring loader executable (ld automatically adds symbols when creating an object file from binary data). Given these, we can calculate which frames correspond to the object file we want to map. From there it's simple - for each frame, unmap it from the current VSpace and map it into the destination VSpace at the destination address.
- After it's done, the Tailspring loader halts forever.

# How to use
## Config file
The config file specifies the capabilities and threads to create, and how caps should be distributed. It is a yaml file composed of 5 sections:
- `caps`
  - A dictionary specifying caps to be created from scratch (retyped). All necessary caps, including TCBs and IPC buffer frames, but NOT cnodes, should be listed here. For each key-value pair, the key is the internal name of the cap to be used throughout the config file, and the value is the type of the cap.
    - Valid types include `tcb`, `endpoint`, `pml4`, `pdpt`, `page_directory`, `page_table`, `x86_4K`, `frame`, and `vspace`
- `cap_modifications`
  - A dictionary of dictionaries specifying how caps should be modified by changing their rights and badge. For each key-value pair, the key is the name of the new derived cap, and the value is a dictionary with the following syntax:
    - `original`: required - specifies the base cap to be derived from.
    - `rights`: required - list of rights, specifies the rights the derived cap should have. Valid rights include `write`, `read`, `grant`, and `grant_reply`.
    - `badge`: optional - numerical value of the badge the derived cap should have. Only really makes sense for endpoint and notifications.
- `cnodes`
  - A dictionary of dictionaries specifying cnodes to be created. For each key-value pair, the key is the name of the cnode to be created, and the value is a dictionary with the following syntax:
    - `size`: required - specifies the size bits of the cnode. The actual number of slots is 2^size.
    - `guard`: required - specifies the guard bits of the cnode.
    - For every other key-value pair where the key is numeric, the value is the name of the cap that should be placed in the slot given by the key (e.g. `3: my_endpoint` specifies that the `my_endpoint` cap should be placed in slot 3 of this cnode).
- `vspaces`
  - A dictionary of vspaces to be created. For each key-value pair, the key specifies the name of the vspace, and the value is the name of the thread binary that should be loaded into the vspace (more on this later).
- `threads`
  - A dictionary of dictionaries specifying threads to be created. For each key-value pair, the key is the name of the TCB for the thread being configured (should have already been created in the `caps` section) and the value is a dictionary with the following syntax:
    - `cspace`: required - specifies the cnode to use as this thread's cspace. The cnode should have already been listed in the `cnodes` section.
    - `vspace`: required - specifies the vspace to use as this thread's vspace. The vspace should have already been listed in the `vspaces` section.
    - `ipc_buffer`: required - specifies a frame to use for this thread's ipc buffer. The cap should have already been created in the `caps` section.
    - `stack_size`: required - specifies the desired size of this thread's stack, in bytes.
    - `entry`: optional - overrides the entry address of the thread, as the default entry address is the e_entry value in the ELF file header. If provided, this should be the name of a symbol in the ELF file.
    - `args`: optional - a list of arguments that should be passed to the thread. Even if no arguments are provided, the name of this thread/TCB will be passed as the first argument to the thread.

An example config file is given:
```
caps:
    consumer_thread: tcb
    consumer_ipc: frame

    producer1_thread: tcb
    producer1_ipc: frame

    producer2_thread: tcb
    producer2_ipc: frame

    shared_endpoint: endpoint

cap_modifications:
    consumer_endpoint:
        original: shared_endpoint
        rights: [read]
    producer1_endpoint:
        original: shared_endpoint
        rights: [write]
        badge: 1234
    producer2_endpoint:
        original: shared_endpoint
        rights: [write]
        badge: 5678

cnodes:
    consumer_cspace:
        size: 5
        guard: 59
        1: consumer_endpoint
    producer1_cspace:
        size: 5
        guard: 59
        1: producer1_endpoint
    producer2_cspace:
        size: 5
        guard: 59
        1: producer2_endpoint

vspaces:
    shared_vspace: thread_elf

threads:
    consumer_thread:
        cspace: consumer_cspace
        vspace: shared_vspace
        ipc_buffer: consumer_ipc
        stack_size: 4096
    producer1_thread:
        cspace: producer1_cspace
        vspace: shared_vspace
        ipc_buffer: producer1_ipc
        stack_size: 4096
        entry: main2
        args: [foo, bar]
    producer2_thread:
        cspace: producer2_cspace
        vspace: shared_vspace
        ipc_buffer: producer2_ipc
        stack_size: 4096
        entry: main2
        args: [foo2, bar2]
```

## VSpaces and ELF files
Sometimes, you might want multiple threads to share the same vspace - perhaps you want a thread to handle IO while another thread does processing, and there is no need to separate the address spaces. Sometimes, the threads should have different vspaces but still be running the same program - perhaps you want multiple VMs that each run the same program but should definitely have separate address spaces. This can be accomplished using Tailspring. In the `vspaces` section, vspace names and thread binaries are provided. The thread binary specifies the unique program that should be loaded. So, if you create two vspaces that each use the same thread binary, then two completely separate vspaces will be created that share the same program data. On the other hand, if multiple threads are created that use the same vspace, then they will all have a shared vspace.

The name of the thread binary (i.e. the value in the vspace section's key-value pairs) is not the path of the thread executable. Rather, the thread binary names refer to the `TAILSPRING_THREAD_DICT` CMake variable (more on this below)

## CMake
Two CMake variables are required to be set:
`RUNTIME_CONFIGS_DIR` - the path that the Tailspring config file is located under. The default config filename is `tailspringconfig.yaml`, but this can be overriden by setting the `TAILSPRING_CONFIG_FILENAME` cache variable
`TAILSPRING_THREAD_DICT` - a mapping of thread binary names to their paths. This can use generator expressions. A dependency for the Tailspring loader is automatically created on each path provided. An example is given below:
```
list(
    APPEND
        TAILSPRING_THREAD_DICT
        thread_elf=$<TARGET_FILE:child_thread>
)
```

Finally, the Tailspring loader target is created with the name `tailspring`. Set this as the root task using `DeclareRootserver(tailspring)`
