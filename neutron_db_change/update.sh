#!/bin/bash

cp 3caaf9877f73* /opt/stack/neutron/neutron/db/migration/alembic_migrations/versions/

neutron-db-manage --config-file /etc/neutron/neutron.conf --config-file /etc/neutron/plugins/ml2/ml2_conf.ini upgrade 3caaf9877f73

