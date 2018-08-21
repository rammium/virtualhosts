#!/usr/bin/python
import sys
import os.path
import subprocess
import urllib
import json
import zipfile
import tempfile
import argparse
import ConfigParser
import pwd
import grp
import time
from shutil import copyfile
from shutil import rmtree
from os import walk
from distutils.version import LooseVersion

class VirtualHosts:
    args = None
    user = None
    config = None
    skeletons = None
    version = "v1.0.0"

    def __init__(self):
        start = time.time()
        self.init_parsers()
        self.user = User()
        self.config = ConfigHandler(self.user)
        skeletons = ["main", "bedrock", "symfony"]
        self.skeletons = SkeletonHandler(skeletons, self.config.directory_path + "/skeletons", self.user)
        self.handle_command()
        print("Finished in " + str(round(time.time() - start, 3)) + " seconds.")

    def init_parsers(self):
        parser = argparse.ArgumentParser(version=self.version)
        subparsers = parser.add_subparsers(dest='command')

        createparser = subparsers.add_parser('create', help='creates a virtualhost using the specified domain and the specified path relative to /Users/<user>/Sites/')
        createparser.add_argument('domain', help='specify the domain (.lo will be appended)')
        createparser.add_argument('-p', '--path', help='specify the path, if not specified, will default to the "$webroot_path/<domain>"')
        createparser.add_argument('-b', '--bedrock', help='will set the root to /web', action='store_true')
        createparser.add_argument('-s', '--symfony', help='will set the root to /public', action='store_true')
        createparser.add_argument('-d', '--database', help='will create a database using the domain as the name', action='store_true')
        createparser.add_argument('-cr', '--clone-repo', help='will clone the specified repo')
        createparser.add_argument('-cd', '--clone-dev', help='will run composer install and the wp clonedev start command', action='store_true')
        createparser.add_argument('-i', '--install', help='will run composer install', action='store_true')

        deleteparser = subparsers.add_parser('delete', help='deletes the specified virtualhost')
        deleteparser.add_argument('virtualhost', help='specify the virtualhost')
        deleteparser.add_argument('-d', '--database', help='will drop the database which has the same name as the domain', action='store_true')
        deleteparser.add_argument('-r', '--remove', help='will remove the whole specified directory')

        subparsers.add_parser('list', help='lists all the created virtualhosts')
        subparsers.add_parser('update', help='updates the script to the latest version')
        subparsers.add_parser('skeleton-update', help='updates the skeleton files to the latest version')
        subparsers.add_parser('check-update', help='show the latest version of the script available')

        self.args = parser.parse_args()

    def handle_command(self):
        commands = {
            "skeleton-update" : self.skeleton_update,
            "check-update" : self.check_update,
            "list" : self.list,
            "create" : self.create,
            "delete" : self.delete,
            "update" : self.update,
        }
        commands[self.args.command]()

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
        files = []

        for (dirpath, dirnames, filenames) in walk("/usr/local/etc/httpd/extra/vhosts/"):
            files.extend(filenames)
            break

        if not len(files):
            print("No virtualhosts created!")
            exit(0)

        print("Created virtualhosts:\n")
        for file in files:
            filenametokens = file.split('.')
            print(filenametokens[0])

    def create(self):
        vhost_name = args.domain
        vhost_path = webroot_path

        if self.args.path:
            vhost_path += self.args.path
        else:
            vhost_path += self.args.domain

        if os.path.exists("/usr/local/etc/httpd/extra/vhosts/" + vhost_name + ".lo.conf"):
            print("Error: A virtualhost with this name already exists!")
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
            subprocess.check_call(("composer install").split(), cwd=vhost_path, stdout=subprocess.PIPE, stderr=subprocess.PIPE)

        vhost_type = 'main'

        if self.args.symfony:
            vhost_type = 'symfony'

        if self.args.bedrock:
            vhost_type = 'bedrock'

        if (self.args.clone_dev and not self.args.database) or (self.args.clone_dev and not self.args.bedrock):
            print("Warning: Cloning the development site requires the -b/--bedrock and -d/--database flags. Cloning will be skipped.")

        print("Creating virtualhost file...")
        with open(self.skeletons.get_path(vhost_type)) as f:
            new_vhost = f.read()

        new_vhost = new_vhost.replace("%VHOSTNAME%", vhost_name)
        new_vhost = new_vhost.replace("%VHOSTPATH%", vhost_path)
        new_vhost = new_vhost.replace("%USERNAME%", self.user.name)
        new_vhost = new_vhost.replace("%HOME_DIR%", self.user.home_dir)

        with open("/usr/local/etc/httpd/extra/vhosts/" + vhost_name + ".lo.conf", "w+") as vhost_file:
            vhost_file.write(new_vhost)

        with open("/usr/local/etc/httpd/extra/httpd-vhosts.conf", "a+") as vhost_main_file:
            vhost_main_file.write("Include /usr/local/etc/httpd/extra/vhosts/" + vhost_name + ".lo.conf\n")

        if self.args.database:
            print("Creating database...")
            subprocess.check_call(("mysqladmin --user=" + self.options["mysql_user"] + " --password=" + self.options["mysql_pass"] + " create " + vhost_name).split())

            if self.args.bedrock:
                if self.args.clone_dev and not os.path.exists(vhost_path + "/wp-cli/clonedev/command.php"):
                    self.args.clone_dev = False
                    print("Warning: Development site cannot be cloned because the WP-CLI command was not found. Cloning will be skipped.")

                print("Generating env file...")
                if os.path.exists(vhost_path + "/.env.example"):
                    copyfile(vhost_path + "/.env.example", vhost_path + "/.env")

                with open(vhost_path + "/.env") as f:
                    env_contents = f.read()

                env_contents = env_contents.replace("database_name", vhost_name)
                env_contents = env_contents.replace("database_user", self.options["mysql_user"])
                env_contents = env_contents.replace("database_password", self.options["mysql_pass"])
                env_contents = env_contents.replace("database_host", self.options["mysql_host"])
                env_contents = env_contents.replace("example.com", vhost_name + ".lo")

                if self.args.clone_dev:
                    ssh_path = raw_input("Enter development site domain (example: wp-test.dpdev.ch): ")
                    ssh_path = ssh_path.replace(" ", "")
                    env_contents = env_contents.replace("DEV_SSH_STRING=''", "DEV_SSH_STRING='" + self.options["ssh_alias"] + ":" + self.options["ssh_port"] + self.options["ssh_path_prefix"] + "/" + ssh_path + "'")

                with open(vhost_path + "/.env", "w+") as env_file:
                    env_file.write(env_contents)

                os.chown(vhost_path + "/.env", self.user.uid, self.user.gid)

        if self.args.clone_dev and self.args.bedrock and self.args.database:
            print("Cloning development site...")
            subprocess.check_call(("wp core install --url=http://" + vhost_name + ".lo/ --title=Local --admin_user=admin --admin_email=admin@admin.lo --allow-root").split(), cwd=vhost_path, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
            subprocess.check_call("wp clonedev start".split(), cwd=vhost_path)

        print("Reloading apache (requires sudo access)...")
        subprocess.check_call("sudo apachectl -k graceful".split())

        print("Virtualhost " + vhost_name + ".lo created! URL: http://" + vhost_name + ".lo/")

    def delete(self):
        vhost_name = self.args.virtualhost

        if not os.path.isfile("/usr/local/etc/httpd/extra/vhosts/" + vhost_name + ".lo.conf"):
            print("Error: A virtualhost with this name does not exist!")
            exit(1)

        print("Deleting virtualhost file...")
        os.remove("/usr/local/etc/httpd/extra/vhosts/" + vhost_name + ".lo.conf")

        with open("/usr/local/etc/httpd/extra/httpd-vhosts.conf") as vhost_main_file:
            vhost_main_contents = vhost_main_file.read()

        vhost_main_contents = vhost_main_contents.replace("Include /usr/local/etc/httpd/extra/vhosts/" + vhost_name + ".lo.conf\n", "")

        with open("/usr/local/etc/httpd/extra/httpd-vhosts.conf", "w+") as vhost_main_file:
            vhost_main_file.write(vhost_main_contents)

        if self.args.remove and os.path.exists(self.options["webroot_path"] + self.args.remove):
            print("Removing the specified directory...")
            rmtree(self.options["webroot_path"] + self.args.remove)

        if self.args.database:
            print("Dropping the database...")
            subprocess.check_call(("mysqladmin --user=" + self.options["mysql_user"] + " --password=" + self.options["mysql_pass"] + " drop " + vhost_name).split())

        print("Reloading apache (requires sudo access)...")
        subprocess.check_call("sudo apachectl -k graceful".split())

        print("Virtualhost " + vhost_name + ".lo deleted!")

    def update(self):
        response = urllib.urlopen("https://api.github.com/repos/rammium/virtualhosts/releases/latest")
        data = json.loads(response.read())

        new_version = data["tag_name"]
        if LooseVersion(self.version) >= LooseVersion(new_version):
            print("You are already running the latest version!")
            exit(0)

        print("Updating virtualhosts script...")
        if data and data["zipball_url"]:
            new_script_zip = urllib.urlopen(data["zipball_url"]).read()
            particular_temp_dir = tempfile.gettempdir() + "/vhupdate" + version

            if not os.path.exists(particular_temp_dir):
                os.makedirs(particular_temp_dir)

            temp = tempfile.NamedTemporaryFile()
            temp.write(new_script_zip)
            temp.seek(0)

            with zipfile.ZipFile(temp.name, "r") as zip_ref:
                zip_ref.extractall(particular_temp_dir)

            repo_temp_dir = [os.path.join(particularTempDir, o) for o in os.listdir(particular_temp_dir)
                               if os.path.isdir(os.path.join(particular_temp_dir, o))][0]

            with open(repo_temp_dir + "/vh.py", "r") as new_script_file:
                new_script = new_script_file.read()

            with open(os.path.realpath(__file__), "w") as old_script_file:
                old_script_file.write(new_script)

            temp.close()
            print("Script updated from " + self.version + " to " + new_version + ".")


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

class Skeleton:
    name = None

    def __init__(self, name):
        self.name = name

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
        self.options["webroot_path"] = self.options["webroot_path"].replace("%HOME_DIR%", self.user.home_dir)

    def create_config(self):
        config = ConfigParser.RawConfigParser(allow_no_value=True)
        config.add_section("General")
        config.add_section("MySQL")
        config.add_section("WP-CLI")
        config.set("General", "; For the webroot_path you can use the %HOME_DIR% string which will be replaced with your actual home directory path (example: %HOME_DIR%/Sites/)")
        config.set("General", "; The webroot_path must end with a slash ('/')")
        config.set("General", "webroot_path", "%HOME_DIR%/Sites/")
        config.set("MySQL", "mysql_user", "")
        config.set("MySQL", "mysql_pass", "")
        config.set("MySQL", "mysql_host", "localhost")
        config.set("WP-CLI", "ssh_alias", "dresden")
        config.set("WP-CLI", "ssh_port", "2323")
        config.set("WP-CLI", "ssh_path_prefix", "/home/wp-dev")

        with open(script_config_path, "wb") as configfile:
            config.write(configfile)
        os.chown(script_config_path, self.user.uid, self.user.gid)

VirtualHosts()