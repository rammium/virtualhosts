# VirtualHosts

Features:
- Create a virtualhost by specifying a domain and the path to the root.
- Create a database using a simple flag.
- Support for bedrock and symfony.
- Generate the .env file for bedrock.
- Run composer install.
- Clone a repository.
- List all created virtualhosts.
- Delete a specific virtualhost and optionally delete the database and directory too.
- Uses configurable skeleton files for virtualhost config which can be auto updated.
- Auto updater.

For a list of all available commands run `$ vh -h`.

For the available flags for a specific command run `$ vh <command> -h`.

## Example installation
Download the script `vh.py` from https://github.com/rammium/virtualhosts/releases/latest to your home directory.

Run `$ chmod +x ~/vh.py` to make it executable.

Run `$ mv ~/vh.py /usr/local/bin/vh` so you can access it globally using the `$ vh` command.
