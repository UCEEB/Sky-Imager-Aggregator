import time
import socket

from timeout_decorator import timeout


def retry_on_failure(attempts, delay=3, back_off=1):
    """
    Decorate a function to recall it upon false return.

    Parameters
    ----------
    attempts : int
        number of attempts to retry.
    delay : int, default 3
        the delay between retry's.
    back_off : int, default 1
        growth of time delay after each try.
    Returns
    -------
    function or bool
    """

    def deco_retry(f):
        def f_retry(*args, **kwargs):
            m_tries, m_delay = attempts, delay  # make mutable
            rv = f(*args, **kwargs)  # first attempt
            while m_tries > 0:
                if rv is True:  # Done on success
                    return True
                m_tries -= 1
                time.sleep(m_delay)
                m_delay *= back_off
                rv = f(*args, **kwargs)  # Try again
            return False

        return f_retry  # true decorator -> decorated function

    return deco_retry  # @retry(arg[, ...]) -> true decorator


def retry_on_exception(attempts, delay=3, back_off=1):
    """
    Decorate a function to recall it when an exception occurs.

    Parameters
    ----------
    attempts : int
        number of attempts to retry.
    delay : int, default 3
        the delay between retry's.
    back_off : int, default 1
        growth of time delay after each try.
    Returns
    -------
    function or bool
    """

    def deco_retry(f):
        def f_retry(*args, **kwargs):
            m_tries, m_delay = attempts, delay
            while m_tries > 1:
                try:
                    return f(*args, **kwargs)
                except Exception:
                    time.sleep(m_delay)
                    m_tries -= 1
                    m_delay *= back_off
            return f(*args, **kwargs)

        return f_retry

    return deco_retry


def loop_infinitely(time_gap=3):
    """
    Transform functions into a recurrent function executed on a timely basis.

    Parameters
    ----------
    time_gap : int, default 3
        the time gap between each execution (default is 3)
    Returns
    -------
    function
        the recurring function that is decorated
    """

    def deco_retry(f):
        def f_retry(*args, **kwargs):
            while True:
                kick_off = time.gmtime()
                # start when second is a multiple of 10 (ends with 0)
                if kick_off.tm_sec == 0:
                    if time_gap != 0:
                        f(*args, **kwargs)

                        wait = time_gap - (int(time.time()) - time.mktime(kick_off)) - 1

                        if wait > 0:
                            time.sleep(wait)
                    else:
                        f(*args, **kwargs)

        return f_retry

    return deco_retry


def has_internet(host='8.8.8.8', port=53, timeout=20):
    """
    Check if there is internet connection.

    Parameters
    ----------
    host : str, default '8.8.8.8'
        IP to ping. the default is google DNS server.
    port : int, default 53
        the port to ping the server on.
    timeout : int, default 20
        the timeout window for pinging.

    Returns
    -------
    bool
        if there is internet connection True, otherwise False.
    """
    try:
        socket.setdefaulttimeout(timeout)
        socket.socket(socket.AF_INET, socket.SOCK_STREAM).connect((host, port))
        return True
    except Exception:
        return False
