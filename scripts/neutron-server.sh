#!/usr/bin/env bash
set -e

DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"

export PYTHONPATH=$DIR/..:$PYTHONPATH
neutron-server --config-file=$DIR/../etc/neutron.conf
