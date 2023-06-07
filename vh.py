#!python
from shutil import copyfile
from shutil import rmtree
from distutils.version import LooseVersion

import ConfigParser
import os.path
import subprocess
import urllib
import json
import zipfile
import tempfile
import argparse
import time
import stat
import pwd
import grp


class VirtualHosts:
    args = None
    user = None
    config = None
    skeletons = None
    vhosts = None
    version = "v1.3.1"

    def __init__(self):
        start = time.time()
        self.init_parsers()
        self.user = User()
        self.config = ConfigHandler(self.user)
        skeletons = ["main", "bedrock", "symfony"]
        self.skeletons = SkeletonHandler(skeletons, self.config.directory_path + "/skeletons", self.user)
        self.vhosts = VDBHandler(self.user)
        self.handle_command()
        print("Finished in " + str(round(time.time() - start, 3)) + " seconds.")

    def init_parsers(self):
        parser = argparse.ArgumentParser(version=self.version)
        subparsers = parser.add_subparsers(dest='command')

        createparser = subparsers.add_parser('create', help='creates a new virtualhost')
        createparser.add_argument('alias', help='specify the alias')
        createparser.add_argument('-d', '--domain', help='specify the domain (.lo will be appended), will be the same as alias if not specified')
        createparser.add_argument('-p', '--path', help='specify the path, if not specified, will default to the "$webroot_path/<domain>"')
        createparser.add_argument('-b', '--bedrock', help='will set the root to /web', action='store_true')
        createparser.add_argument('-s', '--symfony', help='will set the root to /public', action='store_true')
        createparser.add_argument('-db', '--database', help='will create a database using the specified name')
        createparser.add_argument('-cr', '--clone-repo', help='will clone the specified repo')
        createparser.add_argument('-cd', '--clone-dev', help='will run the "wp clonedev start" command', nargs='?', const="none")
        createparser.add_argument('-i', '--install', help='will run "composer install"', action='store_true')
        createparser.add_argument('-sr', '--skip-reload', help='will skip reloading apache', action='store_true')

        deleteparser = subparsers.add_parser('delete', help='deletes a virtualhost')
        deleteparser.add_argument('alias', help='specify the alias')
        deleteparser.add_argument('-d', '--database', help='will drop the linked database', action='store_true')
        deleteparser.add_argument('-r', '--remove', help='will remove the linked directory', action='store_true')
        deleteparser.add_argument('-s', '--skip-db-check', help='will remove the virtualhost config file without checking the vhosts database', action='store_true')

        infoparser = subparsers.add_parser('info', help='lists all stored information about a virtualhost')
        infoparser.add_argument('alias', help='specify the alias')

        updateparser = subparsers.add_parser('update', help='updates the script to the latest version (requires root privileges)')
        updateparser.add_argument('-f', '--force', help='forces the script to update', action='store_true')

        subparsers.add_parser('list', help='lists all the created virtualhosts')
        subparsers.add_parser('skeleton-update', help='updates the skeleton files to the latest version')
        subparsers.add_parser('check-update', help='show the latest version of the script available')
        subparsers.add_parser('reconfig', help='recreates the config file. WARNING: will delete your current config file!')

        self.args = parser.parse_args()

    def handle_command(self):
        commands = {
            "skeleton-update": self.skeleton_update,
            "check-update": self.check_update,
            "list": self.list,
            "create": self.create,
            "delete": self.delete,
            "update": self.update,
            "info": self.info,
            "reconfig": self.reconfig,
        }
        commands[self.args.command]()

    def reconfig(self):
        answer = raw_input("Are you sure you want to overwrite your current config file with the default one? [y/N]: ")

        if not (answer == "y" or answer == "Y"):
            print("Aborted.")
            exit(0)

        self.config.create_config()

    def skeleton_update(self):
        print("Updating skeleton configs...")
        if os.path.exists(self.skeletons.path):
            rmtree(self.skeletons.path)
        self.skeletons.update()

    def check_update(self):
        print("Current version: " + self.version)
        response = urllib.urlopen("https://api.github.com/repos/rammium/virtualhosts/releases/latest")
        data = json.loads(response.read())
        print("Latest version: " + data["tag_name"])

    def list(self):
        if not self.vhosts.vhosts:
            print("No virtualhosts created.")
            exit(0)

        print("Virtualhosts:")
        for vhost in self.vhosts.vhosts:
            print(vhost.alias + " -> " + vhost.domain + ".lo")

    def info(self):
        if not self.vhosts.exists(self.args.alias):
            print("Error: Alias not found!")
            exit(1)

        vhost = self.vhosts.get_vhost(self.args.alias)
        print("Virtualhost '" + vhost.alias + "':")
        print("Domain: " + vhost.domain + ".lo")
        print("Type: " + vhost.type)
        print("Database: " + vhost.database)
        print("Path: " + self.config.options["webroot_path"] + vhost.path)
        print("Virtualhost config: " + self.config.options["apache_config_dir"] + "extra/vhosts/" + vhost.domain + ".lo.conf")

    def create(self):
        self.args.domain = self.args.domain if self.args.domain else self.args.alias
        vhost_name = self.args.domain
        vhost_path = self.config.options["webroot_path"]

        db_name = ""
        if self.args.database:
            db_name = self.args.domain if not self.args.database else self.args.database

        if self.args.path:
            vhost_addon_path = self.args.path
        else:
            vhost_addon_path = self.args.domain
        vhost_path += vhost_addon_path

        if self.vhosts.exists(self.args.alias):
            print("Error: A virtualhost with the same alias already exists!")
            exit(1)

        if os.path.exists(self.config.options["apache_config_dir"] + "extra/vhosts/" + vhost_name + ".lo.conf"):
            print("Error: A virtualhost config file with this name already exists!")
            exit(1)

        if self.args.clone_repo and os.path.exists(vhost_path):
            print("Error: The specified path already exists, cannot clone the repository! Path: " + vhost_path)
            exit(1)

        if self.args.clone_repo:
            print("Cloning the repository...")
            subprocess.check_call(("git clone " + self.args.clone_repo + " " + vhost_path).split(), stdout=subprocess.PIPE, stderr=subprocess.PIPE)

        if self.args.install and not os.path.exists(vhost_path + "/composer.json"):
            print("Error: The specified path does not contain a composer.json file, cannot run composer install! Path: " + vhost_path)
            exit(1)

        if self.args.install:
            print("Running composer install...")
            subprocess.check_call("composer install".split(), cwd=vhost_path, stdout=subprocess.PIPE, stderr=subprocess.PIPE)

        vhost_type = 'main'

        if self.args.symfony:
            vhost_type = 'symfony'

        if self.args.bedrock:
            vhost_type = 'bedrock'

        self.vhosts.add_vhost(Vhost(self.args.alias, vhost_name, vhost_addon_path, vhost_type, db_name))

        if (self.args.clone_dev and not self.args.database) or (self.args.clone_dev and not self.args.bedrock):
            print("Warning: Cloning the development site requires the -b/--bedrock and -d/--database flags. Cloning will be skipped.")

        print("Creating virtualhost file...")
        with open(self.skeletons.get_path(vhost_type)) as f:
            new_vhost = f.read()

        new_vhost = new_vhost.replace("%VHOSTNAME%", vhost_name)
        new_vhost = new_vhost.replace("%VHOSTPATH%", vhost_path)
        new_vhost = new_vhost.replace("%USERNAME%", self.user.name)
        new_vhost = new_vhost.replace("%HOME_DIR%", self.user.home_dir)

        with open(self.config.options["apache_config_dir"] + "extra/vhosts/" + vhost_name + ".lo.conf", "w+") as vhost_file:
            vhost_file.write(new_vhost)

        with open(self.config.options["apache_config_dir"] + "extra/httpd-vhosts.conf", "a+") as vhost_main_file:
            vhost_main_file.write("Include " + self.config.options["apache_config_dir"] + "extra/vhosts/" + vhost_name + ".lo.conf\n")

        if self.args.database:
            print("Creating database...")
            subprocess.check_call(("mysqladmin --user=" + self.config.options["mysql_user"] + " --password=" + self.config.options["mysql_pass"] + " create " + db_name).split())

            if self.args.bedrock:
                if self.args.clone_dev and not os.path.exists(vhost_path + "/wp-cli/clonedev/command.php"):
                    self.args.clone_dev = False
                    print("Warning: Development site cannot be cloned because the WP-CLI command was not found. Cloning will be skipped.")

                print("Generating env file...")
                if os.path.exists(vhost_path + "/.env.example"):
                    copyfile(vhost_path + "/.env.example", vhost_path + "/.env")
                else:
                    print("Error: No .env.example file found in " + vhost_path)
                    exit(1)

                with open(vhost_path + "/.env") as f:
                    env_contents = f.read()

                env_contents = env_contents.replace("DB_NAME=wordpress", "DB_NAME=" + db_name)
                env_contents = env_contents.replace("DB_USER=wordpress", "DB_USER=" + self.config.options["mysql_user"])
                env_contents = env_contents.replace("DB_PASSWORD=wordpress", "DB_PASSWORD=" + self.config.options["mysql_pass"])
                env_contents = env_contents.replace("DB_HOST=database", "DB_HOST=" + self.config.options["mysql_host"])
                env_contents = env_contents.replace("WP_HOME=http://" + vhost_name + ".lndo.site", "WP_HOME=http://" + vhost_name + ".lo")

                if self.args.clone_dev:
                    ssh_path = ""
                    if self.args.clone_dev == "none":
                        ssh_path_flag = True
                        while ssh_path_flag:
                            ssh_path = raw_input("Enter development site domain (example: wp-test.dpdev.ch): ")
                            ssh_path = ssh_path.replace(" ", "")

                            ssh_path_ok = raw_input("Is '" + ssh_path + "' correct? [Y/n]: ")

                            if ssh_path_ok == "y" or ssh_path_ok == "Y" or ssh_path_ok == "":
                                ssh_path_flag = False
                    else:
                        ssh_path = self.args.clone_dev

                    env_contents = env_contents.replace("DEV_SSH_STRING=''", "DEV_SSH_STRING='" + self.config.options["ssh_alias"] + ":" + self.config.options["ssh_port"] + self.config.options["ssh_path_prefix"] + "/" + ssh_path + "'")

                with open(vhost_path + "/.env", "w+") as env_file:
                    env_file.write(env_contents)

                os.chown(vhost_path + "/.env", self.user.uid, self.user.gid)

        if self.args.clone_dev and self.args.bedrock and self.args.database:
            print("Cloning development site...")
            subprocess.check_call(("wp core install --url=http://" + vhost_name + ".lo/ --title=Local --admin_user=admin --admin_email=admin@admin.lo --allow-root").split(), cwd=vhost_path, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
            subprocess.check_call("wp clonedev start".split(), cwd=vhost_path)

        if not self.args.skip_reload:
            print("Reloading apache...")
            subprocess.check_call(self.config.options["apache_reload_command"].split())

        print("Virtualhost " + vhost_name + ".lo created! URL: http://" + vhost_name + ".lo/")

    def delete(self):
        vhost_name = self.args.alias
        vhost_domain = vhost_name

        if not self.args.skip_db_check:
            if not self.vhosts.exists(vhost_name):
                print("Error: Alias not found!")
                exit(1)

            vhost = self.vhosts.get_vhost(vhost_name)
            vhost_domain = vhost.domain
            self.vhosts.remove_vhost(vhost_name)

        print("Deleting virtualhost...")

        if not os.path.isfile(self.config.options["apache_config_dir"] + "extra/vhosts/" + vhost_domain + ".lo.conf"):
            print("Warning: Could not find the virtualhost config file. Will be skipped.")
        else:
            os.remove(self.config.options["apache_config_dir"] + "extra/vhosts/" + vhost_domain + ".lo.conf")

        with open(self.config.options["apache_config_dir"] + "extra/httpd-vhosts.conf") as vhost_main_file:
            vhost_main_contents = vhost_main_file.read()

        vhost_main_contents = vhost_main_contents.replace("Include " + self.config.options["apache_config_dir"] + "extra/vhosts/" + vhost_domain + ".lo.conf\n", "")

        with open(self.config.options["apache_config_dir"] + "extra/httpd-vhosts.conf", "w+") as vhost_main_file:
            vhost_main_file.write(vhost_main_contents)

        if not self.args.skip_db_check:
            if self.args.remove and os.path.exists(self.config.options["webroot_path"] + vhost.path):
                print("Removing the specified directory...")
                rmtree(self.config.options["webroot_path"] + vhost.path)

            if self.args.database and vhost.database:
                print("Dropping the database...")
                subprocess.check_call(("mysqladmin --user=" + self.config.options["mysql_user"] + " --password=" + self.config.options["mysql_pass"] + " drop " + vhost.database).split())

        print("Reloading apache...")
        subprocess.check_call(self.config.options["apache_reload_command"].split())

        print("Virtualhost " + vhost_domain + ".lo deleted!")

    def update(self):
        response = urllib.urlopen("https://api.github.com/repos/rammium/virtualhosts/releases/latest")
        data = json.loads(response.read())

        new_version = data["tag_name"]
        if LooseVersion(self.version) >= LooseVersion(new_version) and not self.args.force:
            print("You are already running the latest version!")
            exit(0)

        print("Updating virtualhosts script...")
        if data and data["zipball_url"]:
            new_script_zip = urllib.urlopen(data["zipball_url"]).read()
            particular_temp_dir = tempfile.gettempdir() + "/vhupdate" + self.version

            if not os.path.exists(particular_temp_dir):
                os.makedirs(particular_temp_dir)

            temp = tempfile.NamedTemporaryFile()
            temp.write(new_script_zip)
            temp.seek(0)

            with zipfile.ZipFile(temp.name, "r") as zip_ref:
                zip_ref.extractall(particular_temp_dir)

            repo_temp_dir = [os.path.join(particular_temp_dir, o) for o in os.listdir(particular_temp_dir)
                               if os.path.isdir(os.path.join(particular_temp_dir, o))][0]

            with open(repo_temp_dir + "/vh.py", "r") as new_script_file:
                new_script = new_script_file.read()

            with open(repo_temp_dir + "/vh-gui.py", "r") as new_script_file:
                new_gui_script = new_script_file.read()

            with open(os.path.realpath(__file__), "w") as old_script_file:
                old_script_file.write(new_script)

            with open(os.path.dirname(os.path.realpath(__file__)) + "/vh-gui", "w") as old_script_file:
                old_script_file.write(new_gui_script)

            temp.close()

            os.chown(os.path.realpath(__file__), self.user.uid, self.user.gid)
            os.chown(os.path.dirname(os.path.realpath(__file__)) + "/vh-gui", self.user.uid, self.user.gid)
            st = os.stat(os.path.realpath(__file__))
            os.chmod(os.path.realpath(__file__), st.st_mode | stat.S_IEXEC)
            st = os.stat(os.path.dirname(os.path.realpath(__file__)) + "/vh-gui")
            os.chmod(os.path.dirname(os.path.realpath(__file__)) + "/vh-gui", st.st_mode | stat.S_IEXEC)

            print("Script updated from " + self.version + " to " + new_version + ".")


class Vhost:
    alias = None
    domain = None
    path = None
    type = None
    database = None

    def __init__(self, alias, domain, path, type = "main", database = ""):
        self.alias = alias
        self.domain = domain
        self.path = path
        self.type = type
        self.database = database

    def __eq__(self, alias):
        return self.alias == alias


class ConfigHandler:
    directory_path = None
    path = None
    options = {}
    user = None

    def __init__(self, user):
        self.user = user
        self.directory_path = "/opt/homebrew/etc/virtualhosts"
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
        config.set("General", "apache_config_dir", "/opt/homebrew/etc/httpd/")
        config.set("General", "apache_reload_command", "brew services restart httpd")
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


class VDBHandler:
    directory_path = None
    path = None
    user = None
    vhosts = []

    def __init__(self, user):
        self.user = user
        self.directory_path = "/opt/homebrew/etc/virtualhosts"
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


class Skeleton:
    name = None

    def __init__(self, name):
        self.name = name


class SkeletonHandler:
    path = None
    user = None
    skeletons = []

    def __init__(self, skeletons, path, user):
        self.path = path
        self.user = user
        self.skeletons = skeletons

        self.update()

    def add(self, name):
        self.skeletons.append(name)

    def update(self):
        if not os.path.exists(self.path) or not os.path.isdir(self.path):
            os.makedirs(self.path)
            os.chown(self.path, self.user.uid, self.user.gid)

        for skeleton in self.skeletons:
            path = self.get_path(skeleton)

            if not os.path.exists(path) or not os.path.isfile(path):
                response = urllib.urlopen("https://raw.githubusercontent.com/rammium/virtualhosts/master/skeletons/skeleton-" + skeleton + ".conf")
                with open(path, "w+") as skeleton_file:
                    skeleton_file.write(response.read())
                os.chown(path, self.user.uid, self.user.gid)
                print("- Updated " + skeleton + " skeleton")

    def get_path(self, name):
        return self.path + "/skeleton-" + name + ".conf"


VirtualHosts()
