# Overview

This charm acts as a proxy to OpenStack and provides an [interface][] to provide
a set of credentials for a somewhat limited project user to the applications that
are related to this charm.

## Usage

This charm is a component of Charmed Kubernetes. For full information,
please visit the [official Charmed Kubernetes docs](https://www.ubuntu.com/kubernetes/docs/charm-openstack-integrator).

## Nagios

This charm uses NRPE checks that are able to monitor servers, networks, subnets, floating-ips, security-groups and
ports. These checks can be set through configuration using the "nrpe-<interface_type>-ids" (e.g. "nrpe-server-ids")
option to monitor specific interfaces defined by IDs. The "nrpe-<interface_type>-ids" option could be defined as "all",
however it is only allowed for servers, networks, floating-ips and ports. Along with option "nrpe-<interface_type>-ids"
set to value "all", it's possible to use "nrpe-skip-<interface_type>-ids" to set up interfaces, which will be skipped.

The NRPE script implements the select parameter for ports (--select key=value), which can help filter by the value
of an interface property (e.g. --select name=data-port). However, this option is not configurable via Juju, hence it
remains unsupported in the charm.


[interface]: https://github.com/juju-solutions/interface-openstack-integration
