#! /bin/sh

set -ex
top=$(readlink -f $(dirname "$0")/..)

cd $top/cpanel
# In $top/.nvmrc, there is the version number of Node.js we want.  That
# is the version installed with Raspian.  If you want to ensure that
# you're using the same version, then install nvm from
# https://github.com/creationix/nvm
if [ -f $HOME/.nvm/nvm.sh ] ; then
  # The -e flag to sh doesn't work with nvm, and the -x is too chatty.
  set +ex
  . $HOME/.nvm/nvm.sh
  nvm install || exit 1 # Uses $top/.nvmrc
  nvm exec npm install || exit 1
  set -ex
else
  npm install
fi

cd $top
git submodule init
git submodule update

cd $top/camdaemon
virtualenv -p python3.4 env
env/bin/pip install -r requirements.txt

echo Libraries installed.
