#!/usr/bin/python
import Tkinter
from Tkinter import *
import urllib
import json
import ConfigParser
import os
import subprocess
from threading import Thread
from Queue import Queue, Empty


def iter_except(function, exception):
    try:
        while True:
            yield function()
    except exception:
        return


class VirtualHostsGui:
    devs = None
    window = None
    list = None
    devName = None
    devAlias = None
    devUrl = None
    repo = None
    options = {}
    homeDir = None
    database = None
    url = None
    pathEntry = None
    vh = None
    text = None
    cloneWindow = None
    config_path = "/usr/local/etc/virtualhosts/config.ini"

    def __init__(self):
        self.homeDir = os.path.expanduser("~")
        self.read_config()

        if not self.options["devs_json_url"]:
            print("Error: 'devs_json_url' not set in " + self.config_path)
            exit(1)

        self.devs = json.loads(urllib.urlopen(self.options["devs_json_url"]).read())["devs"]
        self.devs.sort(key=self.handle_sort)

        self.window = Tkinter.Tk()
        self.window.title("VirtualHosts")
        self.window.geometry("700x495")
        self.window.resizable(0, 0)
        self.list = Listbox(self.window, width=20, height=29, font='Helvetica 14')
        self.list.bind("<<ListboxSelect>>", self.on_select)

        self.devName = StringVar()
        self.devAlias = StringVar()
        self.devUrl = StringVar()
        self.database = StringVar()
        self.url = StringVar()
        self.repo = StringVar()

        dev_name_label = Label(self.window, textvariable=self.devName, font='Helvetica 18 bold')
        dev_alias_label = Label(self.window, textvariable=self.devAlias, font='Helvetica 16')
        dev_url_label = Label(self.window, textvariable=self.devUrl, font='Helvetica 16')
        config_path_label = Label(self.window, text=self.options["webroot_path"], font='Helvetica 14')
        database_label = Label(self.window, textvariable=self.database, font='Helvetica 16')
        url_label = Label(self.window, textvariable=self.url, font='Helvetica 16')
        repo_label = Label(self.window, textvariable=self.repo, font='Helvetica 16')

        self.pathEntry = Entry(self.window)
        clone_button = Button(self.window, text="Clone", command=self.clone)

        i = 0
        for dev in self.devs:
            self.list.insert(i, dev["name"])
            i += 1

        self.list.grid(row=0, column=0, rowspan=60)
        dev_name_label.grid(row=0, column=1, sticky="W", columnspan=2)
        dev_alias_label.grid(row=1, column=1, sticky="W", columnspan=2)
        dev_url_label.grid(row=2, column=1, sticky="W", columnspan=2)
        database_label.grid(row=3, column=1, sticky="W", columnspan=2)
        url_label.grid(row=4, column=1, sticky="W", columnspan=2)
        repo_label.grid(row=5, column=1, sticky="W", columnspan=2)
        config_path_label.grid(row=59, column=1, sticky="E")
        clone_button.grid(row=59, column=3, sticky="E")
        self.pathEntry.grid(row=59, column=2, sticky="W")
        self.window.mainloop()

    def clone(self):
        self.cloneWindow = Tkinter.Tk()
        self.cloneWindow.title("Cloning...")
        self.cloneWindow.resizable(0, 0)
        self.cloneWindow.protocol("WM_DELETE_WINDOW", self.quit)
        self.text = Text(self.cloneWindow)
        self.text.pack()

        index = int(self.list.curselection()[0])
        domain = self.devs[index]["alias"].replace("_", "-")
        path = self.pathEntry.get().replace(" ", "_")
        database = self.devs[index]["alias"]
        repo = self.devs[index]["repo"]
        alias = self.devs[index]["alias"]
        dev_url = self.devs[index]["url"]

        self.vh = subprocess.Popen(("vh create " + alias + " -d " + domain + " -p " + path + " -db " + database + " -cr " + repo + " -b -cd " + dev_url + " -i -sr").split(), stdout=subprocess.PIPE)

        q = Queue(maxsize=1024)
        t = Thread(target=self.reader_thread, args=[q])
        t.daemon = True
        t.start()

        self.update(q)

        self.cloneWindow.mainloop()

    def quit(self):
        self.vh.kill()
        os.system("osascript -e 'do shell script \"" + self.options["apache_reload_command"] + "\" with administrator privileges'")
        self.cloneWindow.destroy()

    def update(self, q):
        for line in iter_except(q.get_nowait, Empty):
            if line is None:
                self.quit()
                return
            else:
                self.text.insert(INSERT, line)
                break
        self.cloneWindow.after(40, self.update, q)

    def reader_thread(self, q):
        try:
            with self.vh.stdout as pipe:
                for line in iter(pipe.readline, b''):
                    q.put(line)
        finally:
            q.put(None)

    def on_select(self, e):
        w = e.widget
        index = int(w.curselection()[0])
        self.devName.set("Name: " + self.devs[index]["name"])
        self.devAlias.set("Alias: " + self.devs[index]["alias"])
        self.devUrl.set("Dev URL: http://" + self.devs[index]["url"])
        self.database.set("Database: " + self.devs[index]["alias"])
        self.repo.set("Repo: " + self.devs[index]["repo"])
        self.url.set("Local URL: http://" + self.devs[index]["alias"].replace("_", "-") + ".lo")
        self.pathEntry.delete(0, len(self.pathEntry.get()))
        self.pathEntry.insert(0, self.devs[index]["alias"])

    def handle_sort(self, elem):
        return elem["name"]

    def read_config(self):
        config = ConfigParser.RawConfigParser()
        config.read(self.config_path)
        self.options["webroot_path"] = config.get("General", "webroot_path")
        self.options["apache_reload_command"] = config.get("General", "apache_reload_command")
        self.options["devs_json_url"] = config.get("General", "devs_json_url")
        self.options["webroot_path"] = self.options["webroot_path"].replace("%HOME_DIR%", self.homeDir)


VirtualHostsGui()