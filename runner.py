#!/usr/bin/python3
import grp
import os
import pwd
from signal import signal, SIGINT, SIGTERM
from sys import exit

from SkyImageAgg.SkyImager import SkyScanner


def drop_privileges(uid_name, gid_name):
    if os.getuid() != 0:
        return
    # Get the uid/gid from the name
    running_uid = pwd.getpwnam(uid_name).pw_uid
    running_gid = grp.getgrnam(gid_name).gr_gid
    # Reset group access list
    os.initgroups(uid_name, running_gid)
    # Try setting the new uid/gid
    os.setgid(running_gid)
    os.setuid(running_uid)
    # Ensure a very conservative umask
    old_umask = os.umask(0o77)


def get_shutdown_handler(message=None):
    """
    Build a shutdown handler, called from the signal methods
    :param message:
        The message to show on the second line of the LCD, if any. Defaults to None
    """
    def handler(signum, frame):
        # If we want to do anything on shutdown you can add it here.
        print(message)
        exit(0)
    return handler


signal(SIGINT, get_shutdown_handler('SIGINT received'))
signal(SIGTERM, get_shutdown_handler('SIGTERM received'))

# Become 'pi' to avoid running as root
drop_privileges(uid_name='pi', gid_name='pi')

s = SkyScanner()
s.main()

