#!/usr/bin/python
import sys
import os.path
import subprocess
import urllib
import json
import zipfile
import tempfile
from os import walk
from distutils.version import LooseVersion

version = "v0.2"
availableCommands = ['create', 'delete', 'help', 'list']

def update():
    checkURL = "https://api.github.com/repos/rammium/virtualhosts/releases/latest"
    response = urllib.urlopen(checkURL)
    data = json.loads(response.read())

    newVersion = data["tag_name"]
    if LooseVersion(version) >= LooseVersion(newVersion):
        return

    print("Updating virtualhosts script...")
    if data and data["zipball_url"]:
        newScriptZip = urllib.urlopen(data["zipball_url"]).read()

        temp = tempfile.TemporaryFile()
        temp.write(newScriptZip)
        temp.seek(0)

        with zipfile.ZipFile("file.zip", "r") as zip_ref:
            zip_ref.extractall(os.path.dirname(os.path.realpath(__file__)))

        temp.close()
        os.execl(sys.executable, *([sys.executable] + sys.argv))

def help():
    print("Virtualhost Commands:\n")
    print("Command\t\t\tFlag\t\t\tDescription")
    print("create <path> <domain>\t\t\t\tCreates a virtualhost using the specified domain and the specified path relative to /Users/<user>/Sites/")
    print("\t\t\t[-b | --bedrock]\tThe document root will have /web appended")
    print("\t\t\t[-s | --symfony]\tThe document root will have /public appended")
    print("delete <domain>\t\t\t\t\tDeletes the specified virtualhost")
    print("list\t\t\t\t\t\tShows all the created virtualhosts")
    print("help\t\t\t\t\t\tShows the available commands")

if os.geteuid() != 0:
    print("Error: This script must run with root privileges!")
    exit(1)

update()

if len(sys.argv) <= 1 or sys.argv[1] == "":
    help()
    exit(1)

command = sys.argv[1]

if command not in availableCommands:
    print("Error: You must specify a command!")
    help()
    exit(1)

if command == "delete" and (len(sys.argv) <= 2 or sys.argv[2] == ""):
    print("Error: You must specify the virtualhost name! Example: vh delete <domain>")
    exit(1)

if sys.argv[1] == "create" and (len(sys.argv) <= 3 or sys.argv[3] == ""):
    print("Error: You must specify the virtualhost name! Example: vh create <path> <domain>")
    help()
    exit(1)

vhostType = False
if len(sys.argv) >= 5 and (sys.argv[4] == "--bedrock" or sys.argv[4] == "-b"):
    vhostType = "bedrock"

if len(sys.argv) >= 5 and (sys.argv[4] == "--symfony" or sys.argv[4] == "-s"):
    vhostType = "symfony"

if command == "help":
    help()
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
    vhostName = sys.argv[3]
    vhostPath = sys.argv[2]

    if os.path.isfile("/usr/local/etc/httpd/extra/vhosts/" + vhostName + ".lo.conf"):
        print("Error: A virtualhost with this name already exists!")
        exit(1)

    skeletonPath = "/usr/local/etc/httpd/extra/skeleton.conf"

    if vhostType:
        skeletonPath = "/usr/local/etc/httpd/extra/skeleton-" + vhostType + ".conf"

    with open(skeletonPath) as f:
        newVhost = f.read()

    newVhost = newVhost.replace("%VHOSTNAME%", vhostName)
    newVhost = newVhost.replace("%VHOSTPATH%", vhostPath)

    with open("/usr/local/etc/httpd/extra/vhosts/" + vhostName + ".lo.conf", "w+") as vhostFile:
        vhostFile.write(newVhost)

    with open("/usr/local/etc/httpd/extra/httpd-vhosts.conf", "a+") as vhostMainFile:
        vhostMainFile.write("Include /usr/local/etc/httpd/extra/vhosts/" + vhostName + ".lo.conf\n")

    subprocess.check_call("sudo apachectl -k restart".split())

    print("Virtualhost " + vhostName + ".lo created! Link: http://" + vhostName + ".lo/")
    exit(0)

if command == "delete":
    vhostName = sys.argv[2]

    if os.path.isfile("/usr/local/etc/httpd/extra/vhosts/" + vhostName + ".lo.conf"):
        print("Error: A virtualhost with this name already exists!")
        exit(1)

    os.remove("/usr/local/etc/httpd/extra/vhosts/" + vhostName + ".lo.conf")

    with open("/usr/local/etc/httpd/extra/httpd-vhosts.conf") as vhostMainFile:
        vhostsMainContents = vhostMainFile.read()

    vhostsMainContents = vhostsMainContents.replace("Include /usr/local/etc/httpd/extra/vhosts/" + vhostName + ".lo.conf\n", "")

    with open("/usr/local/etc/httpd/extra/httpd-vhosts.conf", "w+") as vhostMainFile:
        vhostMainFile.write(vhostsMainContents)

    subprocess.check_call("sudo apachectl -k restart".split())

    print("Virtualhost " + vhostName + ".lo deleted!")
    exit(0)
