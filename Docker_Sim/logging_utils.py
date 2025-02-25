import logging
import sys


class MultilineFormatter(logging.Formatter):
    """
    A custom logging formatter that handles multiline log messages.

    This formatter splits messages by their newline characters and prefixes
    each line with a visual tree-like structure (─, ┬, ├, └). This allows for
    better readability of complex or multiline log messages.

    Usage example
    -------------
    logger = logging.getLogger("my_logger")
    handler = logging.StreamHandler()
    handler.setFormatter(MultilineFormatter())
    logger.addHandler(handler)
    """
    def format(self, record: logging.LogRecord):
        """
        Format a logging record, inserting visual delimiters for multiline messages.

        This overrides the default `format` method to introduce tree-like
        decorations for messages split across multiple lines. Each line is
        formatted separately, and the record's attributes (e.g., name, levelname)
        are manipulated to maintain alignment.

        Parameters
        ----------
        record : logging.LogRecord
            The LogRecord to be processed.

        Returns
        -------
        str
            A string containing the formatted log message(s).
        """
        # Save original message and other attributes
        original_msg = record.msg
        original_fileline = getattr(record, "fileline", "")
        original_levelname = record.levelname
        original_name = record.name

        # Split the message into lines
        lines = original_msg.splitlines()
        output = ""

        for i, line in enumerate(lines):
            if i == 0 and len(lines) == 1:
                record.name = f"[{record.name}]"
                record.msg = f"─ {line}"
                record.fileline = f"[{record.filename}:{record.lineno}]"
            elif i == 0:
                record.name = f"[{record.name}]"
                record.msg = f"┬ {line}"
                record.fileline = f"[{record.filename}:{record.lineno}]"
            elif i < len(lines) - 1:
                record.fileline = ""
                record.name = " " * len(record.name)
                record.levelname = " " * len(record.levelname)
                record.msg = "├──── " + line
            else:
                record.fileline = ""
                record.name = " " * len(record.name)
                record.levelname = " " * len(record.levelname)
                record.msg = "└──── " + line

            # Format the record
            formatted = super().format(record)
            output += formatted

            # Add newline if not the last line
            if i < len(lines) - 1:
                output += "\n"

        # Restore original message and attributes
        record.msg = original_msg
        record.fileline = original_fileline
        record.name = original_name
        record.levelname = original_levelname

        return output


class CenteredFormatter(MultilineFormatter):
    """
    A custom logging formatter that center-aligns the logger name and level.

    This formatter inherits from MultilineFormatter, adding center alignment
    to the `name` and `levelname` fields in each log record.
    """
    def format(self, record):
        """
        Format the log record to center-align the logger name and level.

        Parameters
        ----------
        record : logging.LogRecord
            The LogRecord to be processed.

        Returns
        -------
        str
            A string with the final, formatted message (possibly multiline).
        """
        # Modify the `name` and `levelname` attributes to center-align
        record.name = '{:^14}'.format(record.name)
        record.levelname = '{:^10}'.format(record.levelname)
        return super().format(record)


def register_excepthook(logger):
    """
    Register a global exception hook that logs unhandled exceptions.

    This function redirects the default sys.excepthook to a custom hook that
    logs unhandled exceptions at the DEBUG and CRITICAL levels. It also
    passes KeyboardInterrupt to the original excepthook, preserving the
    default behavior for Ctrl+C interrupts.

    Parameters
    ----------
    logger : logging.Logger
        A logging.Logger instance to which uncaught exceptions will be logged.

    Returns
    -------
    None
    """
    def log_excep(exc_type, exc_value, exc_traceback):
        if issubclass(exc_type, KeyboardInterrupt):
            sys.__excepthook__(exc_type, exc_value, exc_traceback)
            return
        logger.debug(
            "Traceback",
            exc_info=(exc_type, exc_value, exc_traceback)
        )
        logger.critical(
            "Uncaught exception",
            exc_info=(exc_type, exc_value, None)
        )
    sys.excepthook = log_excep


def unregister_excepthook():
    """
    Unregister the custom exception hook, restoring the default Python behavior.

    This function resets sys.excepthook back to sys.__excepthook__, effectively
    removing any custom logging hooks that were registered via register_excepthook.

    Returns
    -------
    None
    """
    sys.excepthook = sys.__excepthook__
