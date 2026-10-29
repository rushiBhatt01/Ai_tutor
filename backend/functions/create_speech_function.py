import os
import subprocess
import sys
import time


def create_speech(text: str, path: str, voice: str, max_retries: int = 2) -> str:
    """
    Synthesize speech using edge-tts with robust error handling and safeguards.

    Args:
        text: Text to synthesize.
        path: Output file path (.wav or .mp3).
        voice: Voice identifier (e.g. 'en-IE-ConnorNeural').
        max_retries: Maximum retry attempts for transient network errors.

    Returns:
        The validated output path.

    Raises:
        ValueError: If text or path is empty.
        RuntimeError: If synthesis fails or produces an empty/invalid audio file.
    """
    if not text or not text.strip():
        raise ValueError("Cannot synthesize speech from empty or whitespace-only text.")
    if not path:
        raise ValueError("Audio output path must be specified.")

    # Ensure parent directory exists
    parent_dir = os.path.dirname(os.path.abspath(path))
    if parent_dir:
        os.makedirs(parent_dir, exist_ok=True)

    # Use sys.executable -m edge_tts to guarantee using the active Python interpreter
    command = [
        sys.executable,
        "-m",
        "edge_tts",
        "--voice",
        voice,
        "--text",
        text,
        "--write-media",
        path,
    ]

    last_error = None
    for attempt in range(1, max_retries + 1):
        # Remove any pre-existing zero-byte or corrupt file at path
        if os.path.exists(path) and os.path.getsize(path) == 0:
            try:
                os.remove(path)
            except OSError:
                pass

        try:
            result = subprocess.run(
                command,
                capture_output=True,
                text=True,
                check=False,
                timeout=60,
            )

            if result.returncode != 0:
                err_msg = result.stderr.strip() or f"Process exited with code {result.returncode}"
                raise RuntimeError(f"edge-tts CLI failed (code {result.returncode}): {err_msg}")

            # Verify the output file exists and is non-empty
            if not os.path.exists(path):
                raise RuntimeError(f"edge-tts did not create the expected audio file at {path}")

            file_size = os.path.getsize(path)
            if file_size < 100:  # Valid audio files are larger than header-only/empty bytes
                try:
                    os.remove(path)
                except OSError:
                    pass
                raise RuntimeError(
                    f"edge-tts produced an empty/truncated audio file ({file_size} bytes) at {path}"
                )

            # Success
            return path

        except Exception as e:
            last_error = e
            if attempt < max_retries:
                time.sleep(1.0)
                continue

    # If all attempts failed, clean up any 0-byte file left behind
    if os.path.exists(path) and os.path.getsize(path) < 100:
        try:
            os.remove(path)
        except OSError:
            pass

    raise RuntimeError(
        f"create_speech failed after {max_retries} attempt(s) for path '{path}'. Cause: {last_error}"
    ) from last_error
