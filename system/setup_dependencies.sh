#! /bin/sh

set -ex
top=$(readlink -f $(dirname "$0")/..)

cd $top/cpanel
# You will want to install nvm from https://github.com/creationix/nvm
# into ~/.nvm as usual.
[ -f $HOME/.nvm/nvm.sh ]
# The -e flag to sh doesn't work with nvm, and the -x is too chatty.
set +ex
. $HOME/.nvm/nvm.sh
echo Installing node.js
nvm install || exit 1 # Uses $top/.nvmrc
nvm exec npm install || exit 1
set -ex

cd $top
git submodule init
git submodule update

cd $top/camdaemon
virtualenv -p python3.4 ENV
ENV/bin/pip install -r requirements.txt

echo Dependencies installed.