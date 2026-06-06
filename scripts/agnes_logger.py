#!/usr/bin/env python3
"""Minimal live logger for Agnes CLI commands.

Redirects all stderr output to a temp log file and writes to the original
stderr so progress is visible live.  When the context exits, a summary
of the captured output is printed.

Usage::

    with LiveLogger("my-task") as log:
        print("step 1...", file=sys.stderr)
        # ... do work ...
        print("step 2...", file=sys.stderr)
    # stderr is restored, log summary printed
"""

from __future__ import annotations

import sys
import tempfile
import typing

if typing.TYPE_CHECKING:
    from collections.abc import Callable

    _PrintCleanup = Callable[[str, int | None], None]


class LogFileWriter:
    """Write to both a temp log file and the original stderr.

    Writing to the log file enables later review.  Writing to ``real_stderr``
    ensures the current terminal always sees the progress.
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
    """Context manager that redirects ``sys.stderr`` to a temp log file
    and writes to the original stderr so progress is visible live.

    When the ``with`` block exits, ``sys.stderr`` is restored and a
    summary of the captured output is printed.

    If the caller provides a ``print_cleanup`` callback, it will be called
    at the end with the log path and tail PID for custom reporting.

    Example (with context manager)::

        with LiveLogger("smoke-test") as log:
            print("Starting...", file=sys.stderr)
            # ... work ...
            print("Done!", file=sys.stderr)
        # stderr restored, log summary printed

    Example (with run)::

        LiveLogger.run("video-batch", my_pipeline_fn, args)
    """

    def __init__(
        self,
        label: str = "",
        print_cleanup: _PrintCleanup | None = None,
    ):
        self._label = label
        self._print_cleanup = print_cleanup
        self._log_file = tempfile.NamedTemporaryFile(
            prefix="agnes-log-", suffix=".log",
            mode="w", delete=False, encoding="utf-8",
        )
        self._log_path = self._log_file.name
        self._orig_stderr = sys.stderr

    def __enter__(self) -> "LiveLogger":
        sys.stderr = LogFileWriter(self._orig_stderr, self._log_file)
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc_val: BaseException | None,
        exc_tb: object,
    ) -> None:
        sys.stderr = self._orig_stderr
        try:
            self._log_file.close()
        except Exception:
            pass
        if self._print_cleanup is not None:
            self._print_cleanup(self._log_path, None)
        else:
            # Print a summary of the log so the user sees what happened
            try:
                with open(self._log_path, "r", encoding="utf-8") as f:
                    content = f.read()
                if content:
                    print(
                        f"\n{'='*60}",
                        f"\n[LiveLogger log: {self._log_path}]",
                        f"\n{'='*60}\n",
                        file=self._orig_stderr, flush=True,
                    )
                    print(content, end="", file=self._orig_stderr, flush=True)
            except Exception:
                pass

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
