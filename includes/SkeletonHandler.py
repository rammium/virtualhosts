import os.path
import urllib


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
