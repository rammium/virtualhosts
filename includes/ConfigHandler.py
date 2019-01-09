import ConfigParser
import os.path


class ConfigHandler:
    directory_path = None
    path = None
    options = {}
    user = None

    def __init__(self, user):
        self.user = user
        self.directory_path = "/usr/local/etc/virtualhosts"
        self.path = self.directory_path + "/config.ini"

        if not os.path.exists(self.directory_path) or not os.path.isdir(self.directory_path):
            os.makedirs(self.directory_path)
            os.chown(self.directory_path, self.user.uid, self.user.gid)

        if not os.path.exists(self.path) or not os.path.isfile(self.path):
            print("No config file found. Creating it...")
            self.create_config()
            print("Config file created at: " + self.path)

        self.read_config()

    def read_config(self):
        config = ConfigParser.RawConfigParser()
        config.read(self.path)
        self.options["mysql_user"] = config.get("MySQL", "mysql_user")
        self.options["mysql_pass"] = config.get("MySQL", "mysql_pass")
        self.options["mysql_host"] = config.get("MySQL", "mysql_host")
        self.options["ssh_alias"] = config.get("WP-CLI", "ssh_alias")
        self.options["ssh_port"] = config.get("WP-CLI", "ssh_port")
        self.options["ssh_path_prefix"] = config.get("WP-CLI", "ssh_path_prefix")
        self.options["webroot_path"] = config.get("General", "webroot_path")
        self.options["apache_config_dir"] = config.get("General", "apache_config_dir")
        self.options["apache_reload_command"] = config.get("General", "apache_reload_command")
        self.options["devs_json_url"] = config.get("General", "devs_json_url")
        self.options["webroot_path"] = self.options["webroot_path"].replace("%HOME_DIR%", self.user.home_dir)

    def create_config(self):
        config = ConfigParser.RawConfigParser(allow_no_value=True)
        config.add_section("General")
        config.add_section("MySQL")
        config.add_section("WP-CLI")
        config.set("General", "; For the webroot_path you can use the %HOME_DIR% string which will be replaced with your actual home directory path (example: %HOME_DIR%/Sites/)")
        config.set("General", "; IMPORTANT: All the paths in this section must end with a slash ('/') and must be absolute paths!")
        config.set("General", "webroot_path", "%HOME_DIR%/Sites/")
        config.set("General", "apache_config_dir", "/usr/local/etc/httpd/")
        config.set("General", "apache_reload_command", "sudo apachectl -k graceful")
        config.set("General", "devs_json_url", "")
        config.set("MySQL", "mysql_user", "")
        config.set("MySQL", "mysql_pass", "")
        config.set("MySQL", "mysql_host", "localhost")
        config.set("WP-CLI", "ssh_alias", "dresden")
        config.set("WP-CLI", "ssh_port", "2323")
        config.set("WP-CLI", "ssh_path_prefix", "/home/wp-dev")

        with open(self.path, "wb") as config_file:
            config.write(config_file)
        os.chown(self.path, self.user.uid, self.user.gid)
