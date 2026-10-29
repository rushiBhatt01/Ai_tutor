import os
import sys

# Forward directly to the canonical functions.create_script_function implementation
from functions.create_script_function import create_script, sanitize_script_for_tts

__all__ = ["create_script", "sanitize_script_for_tts"]
