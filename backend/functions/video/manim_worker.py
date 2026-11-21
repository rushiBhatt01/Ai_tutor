"""Resource-limited launcher for trusted, fixed-template Manim scenes.

This process runs before Manim and applies OS limits before replacing itself
with the renderer. It deliberately fails closed on platforms without POSIX
resource limits; callers can then use the Pillow fallback.
"""

import os
import sys


def main(argv=None):
    args = list(sys.argv[1:] if argv is None else argv)
    if "--" not in args:
        return 2
    separator = args.index("--")
    if separator != 4:
        return 2

    try:
        cpu_seconds, memory_bytes, file_bytes, open_files = map(int, args[:4])
        command = args[separator + 1:]
        if not command or min(cpu_seconds, memory_bytes, file_bytes, open_files) <= 0:
            return 2
        if os.name != "posix":
            return 125

        import resource

        resource.setrlimit(resource.RLIMIT_CPU, (cpu_seconds, cpu_seconds + 2))
        resource.setrlimit(resource.RLIMIT_AS, (memory_bytes, memory_bytes))
        resource.setrlimit(resource.RLIMIT_FSIZE, (file_bytes, file_bytes))
        resource.setrlimit(resource.RLIMIT_NOFILE, (open_files, open_files))
        if hasattr(resource, "RLIMIT_CORE"):
            resource.setrlimit(resource.RLIMIT_CORE, (0, 0))
        os.execvpe(command[0], command, os.environ.copy())
    except (ImportError, OSError, ValueError):
        return 125
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
