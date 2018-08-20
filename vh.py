#!/usr/bin/python
import sys
import os.path
import subprocess
import urllib
import json
import zipfile
import tempfile
import argparse
from os import walk
from distutils.version import LooseVersion

version = "v0.5"

parser = argparse.ArgumentParser(version=version)
subparsers = parser.add_subparsers(dest='command')

createparser = subparsers.add_parser('create', help='creates a virtualhost using the specified domain and the specified path relative to /Users/<user>/Sites/')
createparser.add_argument('path', help='specify the path')
createparser.add_argument('domain', help='specify the domain (.lo will be appended)')
createparser.add_argument('-b', '--bedrock', help='will set the root to /web', action='store_true')
createparser.add_argument('-s', '--symfony', help='will set the root to /public', action='store_true')
# createparser.add_argument('-d', '--database', help='will create a database using the domain as the name', action='store_true')

listparser = subparsers.add_parser('list', help='lists all the created virtualhosts')

updateparser = subparsers.add_parser('update', help='updates the script to the latest version')

checkupdateparser = subparsers.add_parser('check-update', help='show the latest version of the script available')

deleteparser = subparsers.add_parser('delete', help='deletes the specified virtualhost')
deleteparser.add_argument('virtualhost', help='specify the virtualhost')

args = parser.parse_args()
command = args.command

if os.geteuid() != 0:
    print("Error: This script must run with root privileges!")
    exit(1)

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
    vhostName = args.virtualhost

    if not os.path.isfile("/usr/local/etc/httpd/extra/vhosts/" + vhostName + ".lo.conf"):
        print("Error: A virtualhost with this name does not exist!")
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