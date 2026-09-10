import sys

# Keep a deployed skill directory clean: importing the package below would
# otherwise write __pycache__/*.pyc beside the sources, leaving build artifacts
# inside the skill. Must be set BEFORE `book_to_skill` is imported.
sys.dont_write_bytecode = True
from book_to_skill.utils import main as utils_main

def main():
    # Force UTF-8 stdout/stderr to avoid UnicodeEncodeError on Windows console
    for _stream in (sys.stdout, sys.stderr):
        try:
            _stream.reconfigure(encoding="utf-8")
        except (AttributeError, ValueError):
            # Ignore if the stream does not support reconfigure (e.g. mock streams during testing)
            pass
    utils_main()

# Expose main for packaging console scripts entry points
if __name__ == "__main__":
    main()
