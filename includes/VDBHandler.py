import ConfigParser
import os.path
from Vhost import Vhost


class VDBHandler:
    directory_path = None
    path = None
    user = None
    vhosts = []

    def __init__(self, user):
        self.user = user
        self.directory_path = "/usr/local/etc/virtualhosts"
        self.path = self.directory_path + "/vhosts_database.ini"

        if not os.path.exists(self.path) or not os.path.isfile(self.path):
            print("No config file found. Creating it...")
            self.create_vhosts_database()
            print("Config file created at: " + self.path)

        self.read_vhosts_database()

    def get_vhost(self, alias):
        if self.exists(alias):
            return self.vhosts[self.vhosts.index(alias)]
        return False

    def exists(self, alias):
        try:
            self.vhosts.index(alias)
        except ValueError:
            return False
        return True

    def remove_vhost(self, alias):
        if not self.exists(alias):
            print("Error: Alias not found.")
            exit(1)

        config = ConfigParser.RawConfigParser(allow_no_value=True)
        config.read(self.path)
        config.remove_section(alias)

        with open(self.path, "w") as config_file:
            config.write(config_file)

    def add_vhost(self, vhost):
        self.vhosts.append(vhost)
        config = ConfigParser.RawConfigParser(allow_no_value=True)
        config.add_section(vhost.alias)
        config.set(vhost.alias, "domain", vhost.domain)
        config.set(vhost.alias, "path", vhost.path)
        config.set(vhost.alias, "type", vhost.type)
        config.set(vhost.alias, "database", vhost.database)

        with open(self.path, "a") as config_file:
            config.write(config_file)

    def read_vhosts_database(self):
        config = ConfigParser.RawConfigParser()
        config.read(self.path)

        for vhost in config.sections():
            domain = config.get(vhost, "domain")
            path = config.get(vhost, "path")
            type = config.get(vhost, "type")
            database = config.get(vhost, "database")
            self.vhosts.append(Vhost(vhost, domain, path, type, database))

    def create_vhosts_database(self):
        f = open(self.path, "w")
        f.close()
        os.chown(self.path, self.user.uid, self.user.gid)
