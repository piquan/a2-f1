#! /bin/bash

set -ex

# Turn this on if you want to actually install files into /etc (as
# symlinks).  Otherwise, it will just build them.
install=1

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
if [ -n "$install" ] ; then
    if [ -d /etc/nginx/sites-enabled/ ] ; then
        sudo ln -sf $( pwd )/nginx_site.conf /etc/nginx/sites-enabled/a2-f1.conf
    else
        echo This script expects you to have nginx installed, and           >&2
        echo configured with /etc/nginx/sites-enabled/ .  I went ahead and  >&2
        echo build nginx_site.conf for you, but installing it is up to you. >&2
        echo                                                                >&2
    fi
fi

run_handlebars a2-f1.target
run_handlebars a2-f1-camdaemon.service
run_handlebars a2-f1-cpanel.service
if [ -n "$install" ] ; then
    if [ -d /etc/systemd/ ] ; then
        sudo systemctl enable $(pwd)/a2-f1.target $(pwd)/a2-f1-camdaemon.service $(pwd)/a2-f1-cpanel.service
    else
        echo This script expects you to be using systemd, but it looks like >&2
        echo you have a different init.  You can look at the \*.service     >&2
        echo files to get an idea of what you need to run.                  >&2
        echo                                                                >&2
    fi
fi

run_handlebars tmpfiles.conf
if [ -n "$install" ] ; then
    if [ -d /etc/tmpfiles.d/ ] ; then
        sudo ln -sf $(pwd)/tmpfiles.conf /etc/tmpfiles.d/a2-f1.conf
    else
        echo This script expects you to be using tmpfiles.d, but it looks   >&2
        echo like you do not have it installed.  You can look at            >&2
        echo tmpfiles.conf to get an idea of what directories are needed.   >&2
        echo                                                                >&2
    fi
fi
