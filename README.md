# A2-F1 Robot Control System

This is the program to run a robot I'm building.  More details as things become develoed.

This is designed to run on a Raspberry Pi running Raspbian Jesse (it can probably be adapted to Wheezy), or be run on a normal host for development purposes.

You'll need Python 3.4, virtualenv, Node.js (ideally either v0.10.29, or have [nvm](https://github.com/creationix/nvm) installed), npm, and nginx.  Raspbian comes with these pre-installed.

To get started, after cloning the repo, switch to the `config` directory.  Symlink or copy one of the template config files to `default.json`.  (While the Node.js code uses [node-config](https://www.npmjs.com/package/config) to pick which files to read, the Python code only reads `default.json`.)

Switch to the `etc` directory, and run `./setup_libraries.sh`.  This will load all the dependencies and set up virtualenv and node_modules directories.  It will issue some non-fatal warnings on most systems, such as optional dependencies, or tests with syntax errors under Python 3.4.  That's ok.

If you want to install the appropriate system config files in `/etc`, then edit `./setup_host.sh` and change the `install=` line to suit the environment.

To build (and optionally install) the system config files, run `./setup_host.sh`.

If you're using systemd, run `sudo systemctl start a2-f1`.  You can view the output of the actual daemons using `systemctl -l status a2-f1-camdaemon` (or `a2-f1-cpanel`, etc).  If you're using upstart, you can start with `sudo service a2-f1 start`, and view the logs in /var/log/upstart/a2-f1*.
