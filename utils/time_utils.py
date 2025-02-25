def format_time(running_time: float) -> str:
    """
    Format a time duration (in seconds) as HH:MM:SS.

    Parameters
    ----------
    running_time : float
        The duration in seconds.

    Returns
    -------
    str
        A string in "HH:MM:SS" format.

    This function takes a floating-point number representing time in seconds and
    converts it to a zero-padded string formatted as hours, minutes, and seconds.
    """
    hrs = int(running_time // 3600)
    mts = int((running_time % 3600) // 60)
    sec = int(running_time % 60)

    return "{:02d}:{:02d}:{:02d}".format(hrs, mts, sec)