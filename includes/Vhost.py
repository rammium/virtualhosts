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
