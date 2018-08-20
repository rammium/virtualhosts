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
from shutil import copyfile
from shutil import rmtree
from os import walk
from distutils.version import LooseVersion

version = "v0.7"
script_config_dir = "/usr/local/etc/virtualhosts"
script_config_file = "config.ini"
script_config_path = script_config_dir + "/" + script_config_file
mysql_user = ""
mysql_pass = ""
mysql_host = "localhost"
user_home_dir = os.path.expanduser("~")

parser = argparse.ArgumentParser(version=version)
subparsers = parser.add_subparsers(dest='command')

createparser = subparsers.add_parser('create', help='creates a virtualhost using the specified domain and the specified path relative to /Users/<user>/Sites/')
createparser.add_argument('path', help='specify the path')
createparser.add_argument('domain', help='specify the domain (.lo will be appended)')
createparser.add_argument('-b', '--bedrock', help='will set the root to /web', action='store_true')
createparser.add_argument('-s', '--symfony', help='will set the root to /public', action='store_true')
createparser.add_argument('-d', '--database', help='will create a database using the domain as the name', action='store_true')

listparser = subparsers.add_parser('list', help='lists all the created virtualhosts')

updateparser = subparsers.add_parser('update', help='updates the script to the latest version')

skeletonupdateparser = subparsers.add_parser('skeleton-update', help='updates the skeleton files to the latest version')

checkupdateparser = subparsers.add_parser('check-update', help='show the latest version of the script available')

deleteparser = subparsers.add_parser('delete', help='deletes the specified virtualhost')
deleteparser.add_argument('virtualhost', help='specify the virtualhost')
deleteparser.add_argument('-d', '--database', help='will drop the database which has the same name as the domain', action='store_true')

args = parser.parse_args()
command = args.command

if os.geteuid() != 0:
    print("Error: This script must run with root privileges!")
    exit(1)

user_name = ""
if os.environ.has_key('SUDO_USER'):
    user_name = os.environ['SUDO_USER']
else:
    user_name = os.environ['USER']
uid = pwd.getpwnam(user_name).pw_uid
gid = grp.getgrnam("admin").gr_gid

if command == "skeleton-update":
    if os.path.exists(script_config_dir + "/skeletons"):
        rmtree(script_config_dir + "/skeletons")

if not os.path.exists(script_config_dir) or not os.path.isdir(script_config_dir):
    os.makedirs(script_config_dir)
    os.chown(script_config_dir, uid, gid)

if not os.path.exists(script_config_path) or not os.path.isfile(script_config_path):
    print("No config file found. Creating it...")
    config = ConfigParser.RawConfigParser()
    config.add_section("MySQL")
    config.set("MySQL", "mysql_user", mysql_user)
    config.set("MySQL", "mysql_pass", mysql_pass)
    config.set("MySQL", "mysql_host", mysql_host)

    with open(script_config_path, "wb") as configfile:
        config.write(configfile)
    os.chown(script_config_path, uid, gid)
    print("Config file created at: " + script_config_path)

if not os.path.exists(script_config_dir + "/skeletons") or not os.path.isdir(script_config_dir + "/skeletons"):
    os.makedirs(script_config_dir + "/skeletons")
    os.chown(script_config_dir + "/skeletons", uid, gid)

if not os.path.exists(script_config_dir + "/skeletons/skeleton.conf") or not os.path.isfile(script_config_dir + "/skeletons/skeleton.conf"):
    print("Updating main skeleton config...")
    response = urllib.urlopen("https://raw.githubusercontent.com/rammium/virtualhosts/master/skeletons/skeleton.conf")
    with open(script_config_dir + "/skeletons/skeleton.conf", "w+") as skeletonFile:
        skeletonFile.write(response.read())
    os.chown(script_config_dir + "/skeletons/skeleton.conf", uid, gid)

if not os.path.exists(script_config_dir + "/skeletons/skeleton-bedrock.conf") or not os.path.isfile(script_config_dir + "/skeletons/skeleton-bedrock.conf"):
    print("Updating bedrock skeleton config...")
    response = urllib.urlopen("https://raw.githubusercontent.com/rammium/virtualhosts/master/skeletons/skeleton-bedrock.conf")
    with open(script_config_dir + "/skeletons/skeleton-bedrock.conf", "w+") as skeletonFile:
        skeletonFile.write(response.read())
    os.chown(script_config_dir + "/skeletons/skeleton-bedrock.conf", uid, gid)

if not os.path.exists(script_config_dir + "/skeletons/skeleton-symfony.conf") or not os.path.isfile(script_config_dir + "/skeletons/skeleton-symfony.conf"):
    print("Updating symfony skeleton config...")
    response = urllib.urlopen("https://raw.githubusercontent.com/rammium/virtualhosts/master/skeletons/skeleton-symfony.conf")
    with open(script_config_dir + "/skeletons/skeleton-symfony.conf", "w+") as skeletonFile:
        skeletonFile.write(response.read())
    os.chown(script_config_dir + "/skeletons/skeleton-symfony.conf", uid, gid)

if command == "check-update":
    print("Current version: " + version)
    checkURL = "https://api.github.com/repos/rammium/virtualhosts/releases/latest"
    response = urllib.urlopen(checkURL)
    data = json.loads(response.read())
    print("Latest version: " + data["tag_name"])
    exit(0)

if command == "list":
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
    exit(0)

if command == "create":
    vhostType = False

    if args.symfony:
        vhostType = 'symfony'

    if args.bedrock:
        vhostType = 'bedrock'

    vhostName = args.domain
    vhostPath = args.path

    if os.path.isfile("/usr/local/etc/httpd/extra/vhosts/" + vhostName + ".lo.conf"):
        print("Error: A virtualhost with this name already exists!")
        exit(1)

    print("Creating virtualhost file...")
    skeletonPath = script_config_dir + "/skeletons/skeleton.conf"

    if vhostType:
        skeletonPath = script_config_dir + "/skeletons/skeleton-" + vhostType + ".conf"

    with open(skeletonPath) as f:
        newVhost = f.read()

    newVhost = newVhost.replace("%VHOSTNAME%", vhostName)
    newVhost = newVhost.replace("%VHOSTPATH%", vhostPath)
    newVhost = newVhost.replace("%USERNAME%", user_name)

    with open("/usr/local/etc/httpd/extra/vhosts/" + vhostName + ".lo.conf", "w+") as vhostFile:
        vhostFile.write(newVhost)

    with open("/usr/local/etc/httpd/extra/httpd-vhosts.conf", "a+") as vhostMainFile:
        vhostMainFile.write("Include /usr/local/etc/httpd/extra/vhosts/" + vhostName + ".lo.conf\n")

    if args.database:
        print("Creating database...")
        subprocess.check_call(("sudo mysqladmin create " + vhostName).split())

        if args.bedrock:
            print("Generating env file...")
            if os.path.exists(user_home_dir + "/Sites/" + vhostPath + "/.env.example"):
                copyfile(user_home_dir + "/Sites/" + vhostPath + "/.env.example",
                         user_home_dir + "/Sites/" + vhostPath + "/.env")

            config = ConfigParser.RawConfigParser()
            config.read(script_config_path)
            mysql_user = config.get("MySQL", "mysql_user")
            mysql_pass = config.get("MySQL", "mysql_pass")
            mysql_host = config.get("MySQL", "mysql_host")

            with open(user_home_dir + "/Sites/" + vhostPath + "/.env") as f:
                env_contents = f.read()
            env_contents = env_contents.replace("database_name", vhostName)
            env_contents = env_contents.replace("database_user", mysql_user)
            env_contents = env_contents.replace("database_password", mysql_pass)
            env_contents = env_contents.replace("database_host", mysql_host)
            env_contents = env_contents.replace("example.com", vhostName + ".lo")

            with open(user_home_dir + "/Sites/" + vhostPath + "/.env", "w+") as envFile:
                envFile.write(env_contents)

            os.chown(user_home_dir + "/Sites/" + vhostPath + "/.env", uid, gid)

    subprocess.check_call("sudo apachectl -k restart".split())

    print("Virtualhost " + vhostName + ".lo created! Link: http://" + vhostName + ".lo/")
    exit(0)

if command == "delete":
    vhostName = args.virtualhost

    if not os.path.isfile("/usr/local/etc/httpd/extra/vhosts/" + vhostName + ".lo.conf"):
        print("Error: A virtualhost with this name does not exist!")
        exit(1)

    print("Deleting virtualhost file...")
    os.remove("/usr/local/etc/httpd/extra/vhosts/" + vhostName + ".lo.conf")

    with open("/usr/local/etc/httpd/extra/httpd-vhosts.conf") as vhostMainFile:
        vhostsMainContents = vhostMainFile.read()

    vhostsMainContents = vhostsMainContents.replace("Include /usr/local/etc/httpd/extra/vhosts/" + vhostName + ".lo.conf\n", "")

    with open("/usr/local/etc/httpd/extra/httpd-vhosts.conf", "w+") as vhostMainFile:
        vhostMainFile.write(vhostsMainContents)

    if args.database:
        print("Dropping the database...")
        subprocess.check_call(("sudo mysqladmin drop " + vhostName).split())

    subprocess.check_call("sudo apachectl -k restart".split())

    print("Virtualhost " + vhostName + ".lo deleted!")
    exit(0)

if command == "update":
    checkURL = "https://api.github.com/repos/rammium/virtualhosts/releases/latest"
    response = urllib.urlopen(checkURL)
    data = json.loads(response.read())

    newVersion = data["tag_name"]
    if LooseVersion(version) >= LooseVersion(newVersion):
        print("You are already running the latest version!")
        exit(0)

    print("Updating virtualhosts script...")
    if data and data["zipball_url"]:
        newScriptZip = urllib.urlopen(data["zipball_url"]).read()

        tempDir = tempfile.gettempdir()
        particularTempDir = tempDir + "/vhupdate" + version
        if not os.path.exists(particularTempDir):
            os.makedirs(particularTempDir)

        temp = tempfile.NamedTemporaryFile()
        temp.write(newScriptZip)
        temp.seek(0)

        with zipfile.ZipFile(temp.name, "r") as zip_ref:
            zip_ref.extractall(particularTempDir)

        repoNameTempDir = [os.path.join(particularTempDir, o) for o in os.listdir(particularTempDir)
                           if os.path.isdir(os.path.join(particularTempDir, o))][0]

        with open(repoNameTempDir + "/vh.py", "r") as newScriptFile:
            newScript = newScriptFile.read()

        with open(os.path.realpath(__file__), "w") as oldScriptFile:
            oldScriptFile.write(newScript)

        temp.close()
        print("Script updated from " + version + " to " + newVersion + ".")