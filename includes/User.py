import pwd
import grp
import os.path


class User:
    home_dir = None
    name = None
    uid = None
    gid = None

    def __init__(self):
        self.name = os.environ['SUDO_USER'] if os.environ.has_key('SUDO_USER') else os.environ['USER']
        self.uid = pwd.getpwnam(self.name).pw_uid
        self.gid = grp.getgrnam("admin").gr_gid
        self.home_dir = os.path.expanduser("~")
