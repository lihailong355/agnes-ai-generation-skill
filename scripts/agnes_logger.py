#!/usr/bin/env python3
"""Real-time progress logger for Agnes CLI commands.

When enabled, redirects all stderr output to a temp log file and spawns
a ``tail -f`` subprocess so the user sees live progress in the terminal.
Works with any command by wrapping it in a context manager.

Usage::

    with LiveLogger("my-task") as log:
        print("step 1...", file=sys.stderr)
        # ... do work ...
        print("step 2...", file=sys.stderr)
    # tail process is automatically cleaned up
"""

from __future__ import annotations

from types import TracebackType

import subprocess
import sys
import tempfile
import typing

if typing.TYPE_CHECKING:
    from collections.abc import Callable

    _PrintCleanup = Callable[[str, int | None], None]


class LogFileWriter:
    """Write to both a temp log file and the original stderr.

    Writing to the log file enables ``tail -f`` for remote/other-terminal
    viewing.  Writing to ``real_stderr`` ensures the current terminal always
    sees the progress regardless of how stdout/stderr are captured.
    """

    def __init__(self, real_stderr, log_fp):
        self._real_stderr = real_stderr
        self._log_fp = log_fp

    def write(self, data):
        try:
            self._log_fp.write(data)
            self._log_fp.flush()
        except Exception:
            pass
        try:
            self._real_stderr.write(data)
            self._real_stderr.flush()
        except Exception:
            pass

    def flush(self):
        try:
            self._log_fp.flush()
        except Exception:
            pass
        try:
            self._real_stderr.flush()
        except Exception:
            pass

    def isatty(self):
        return False


class LiveLogger:
    """Context manager that starts a ``tail -f`` subprocess and redirects
    ``sys.stderr`` to a temp log file so all progress is visible live.

    When the ``with`` block exits, the tail process is killed and
    ``sys.stderr`` is restored.

    If the caller provides a ``print_cleanup`` callback, it will be called
    at the end with the log path and tail PID for custom reporting.

    Example (with context manager)::

        with LiveLogger("smoke-test") as log:
            print("Starting...", file=sys.stderr)
            # ... work ...
            print("Done!", file=sys.stderr)
        # tail process cleaned up, stderr restored

    Example (with run)::

        LiveLogger.run("video-batch", my_pipeline_fn, args)
    """

    def __init__(self, label: str = "", print_cleanup: _PrintCleanup | None = None):
        self._label = label
        self._print_cleanup = print_cleanup
        self._log_file = tempfile.NamedTemporaryFile(
            prefix="agnes-log-", suffix=".log",
            mode="w", delete=False, encoding="utf-8",
        )
        self._log_path = self._log_file.name
        self._orig_stderr = sys.stderr
        self._tail_pid = None
        self._tail_started = False

    def __enter__(self) -> "LiveLogger":
        # Also start tail -f so users can tail the log from another terminal
        try:
            self._log_file.flush()
            _tail_proc = subprocess.Popen(
                ["tail", "-f", self._log_path],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                bufsize=1,
            )
            # Keep a reference so it doesn't get GC'd mid-read
            self._tail_proc_ref = _tail_proc
            self._tail_started = True
            print(
                f"[Live log tail started, PID={self._tail_pid}, "
                f"log file: {self._log_path}]",
                file=self._orig_stderr, flush=True,
            )
        except Exception as exc:
            self._tail_started = False
            print(
                f"[Log file: {self._log_path}] (tail -f failed: {exc}) "
                f"— writing directly to stderr",
                file=self._orig_stderr, flush=True,
            )
        sys.stderr = LogFileWriter(self._orig_stderr, self._log_file)
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc_val: BaseException | None,
        exc_tb: TracebackType | None,
    ) -> None:
        sys.stderr = self._orig_stderr
        if self._tail_pid:
            try:
                subprocess.run(
                    ["kill", str(self._tail_pid)],
                    capture_output=True,
                )
            except Exception:
                pass
        try:
            self._log_file.close()
        except Exception:
            pass
        if self._print_cleanup is not None:
            self._print_cleanup(self._log_path, self._tail_pid)

    @staticmethod
    def run(label: str, body_fn: Callable[..., None], /, *args, **kwargs) -> None:
        """Start live logging and call *body_fn(args, kwargs)*, then clean up.

        This is the preferred API for commands like ``cmd_video_batch`` — it
        avoids wrapping the entire function body in a ``with`` block.
        """
        logger = LiveLogger(label)
        try:
            logger.__enter__()
            try:
                body_fn(*args, **kwargs)
            finally:
                logger.__exit__(None, None, None)
        except Exception:
            # If __enter__ itself failed, restore stderr and re-raise
            sys.stderr = sys.__stderr__
            raise
