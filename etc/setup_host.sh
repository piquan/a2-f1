#! /bin/bash

set -ex

# Turn these on if you want to actually install files into /etc (as
# symlinks where possible).  Otherwise, it will just build them.
# Possible values are systemd, nginx, tmpfiles, and upstart.
# Note: systemd and upstart should not be installed simultaneously.
# Debian >= 7.0 "Wheezy" and Ubuntu >= 15.04 "Vivid Vervet" use
# systemd, while earlier versions use upstart.
#
# Recent Raspbian / Debian / Ubuntu:
#install="systemd nginx tmpfiles"
# Slightly earlier Raspbian / Debian / Ubuntu:
install="upstart nginx"
# Manual:
#install=""

if [ ! -f ../config/default.json ] ; then
    echo You need to create or symlink ../config/default.json from one 2>&1
    echo of the templates first. >&2
    exit 1
fi

[ -d node_modules/handlebars ] || npm install handlebars
runtime_config="{\"user\":\"$(id -un)\",\"group\":\"$(id -gn)\",\"top\":\"$(git rev-parse --show-toplevel)\"}"
run_handlebars() {
    echo $runtime_config
    echo $runtime_config | node expand.js ../config/default.json "$1".hbs > "$1"
}

run_handlebars nginx_site.conf
case "$install" in *nginx*)
    sudo ln -sf $( pwd )/nginx_site.conf \
        /etc/nginx/sites-enabled/a2-f1.conf
    ;;
esac

run_handlebars a2-f1.target
run_handlebars a2-f1-camdaemon.service
run_handlebars a2-f1-cpanel.service
case "$install" in *systemd*)
    sudo systemctl enable $(pwd)/a2-f1.target \
        $(pwd)/a2-f1-camdaemon.service $(pwd)/a2-f1-cpanel.service
    ;;
esac

run_handlebars a2-f1.upstart
run_handlebars a2-f1-camdaemon.upstart
run_handlebars a2-f1-cpanel.upstart
case "$install" in *upstart*)
    sudo cp a2-f1.upstart /etc/init/a2-f1.conf
    sudo cp a2-f1-camdaemon.upstart /etc/init/a2-f1-camdaemon.conf
    sudo cp a2-f1-cpanel.upstart /etc/init/a2-f1-cpanel.conf
    ;;
esac

run_handlebars tmpfiles.conf
case "$install" in *tmpfiles*)
    sudo ln -sf $(pwd)/tmpfiles.conf /etc/tmpfiles.d/a2-f1.conf
    ;;
esac