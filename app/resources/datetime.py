import datetime

def get_current_datetime_utc()-> datetime.datetime:
    """
    Returns the current UTC datetime as a naive string (without timezone info).
    
    The datetime is fetched in UTC and the timezone is removed.
    
    Returns:
        str: Current UTC datetime without timezone.
    """
    return datetime.datetime.now(datetime.timezone.utc).replace(tzinfo=None)