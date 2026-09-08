#!/usr/bin/env python3
"""Optional LAN-bound threaded server adapter for the reviewed upstream revision."""
import argparse
from http.server import ThreadingHTTPServer
import importlib.util
import ipaddress
import os
from pathlib import Path
import subprocess

PIN = 'da374e5f10eff26b7df323ef0c2bc8470b142501'


def address(value):
    ip = ipaddress.IPv4Address(value)
    if not any(ip in ipaddress.IPv4Network(net) for net in ('10.0.0.0/8', '172.16.0.0/12', '192.168.0.0/16')):
        raise argparse.ArgumentTypeError('An owner-controlled private LAN address is required')
    return str(ip)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source', type=Path, default=Path('.private/slopbro'))
    parser.add_argument('--host', required=True, type=address)
    parser.add_argument('--admin-ip', required=True, type=address)
    parser.add_argument('--port', type=int, default=44767)
    parser.add_argument('--webos-version', type=int, default=10)
    args = parser.parse_args()
    if not 1024 <= args.port <= 65535:
        parser.error('Use a TCP port from 1024 through 65535')
    source = args.source.resolve()
    head = subprocess.check_output(['git', '-C', str(source), 'rev-parse', 'HEAD'], text=True).strip()
    dirty = subprocess.check_output(['git', '-C', str(source), 'status', '--porcelain', '--untracked-files=no'], text=True)
    if head != PIN or dirty.strip():
        parser.error('Use the clean, pinned upstream revision documented in README.md')
    spec = importlib.util.spec_from_file_location('slopbro', source / 'slopbro.py')
    upstream = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(upstream)
    upstream.HTTPServer = ThreadingHTTPServer
    original_start = upstream.start_http_server

    def start_server(*positional, **kwargs):
        kwargs['bind_host'] = args.admin_ip
        kwargs['preferred_port'] = args.port
        server = original_start(*positional, **kwargs)
        if server.server_port != args.port:
            server.shutdown()
            server.server_close()
            raise RuntimeError('Requested port occupied; refusing a port outside your firewall exception')
        return server

    upstream.start_http_server = start_server
    os.umask(0o077)
    os.chdir(source)  # Upstream credentials remain in the private checkout.
    return upstream.main(['--debug', '--asset-source', 'dir', '--local-ip', args.admin_ip,
                          '--webos-version', str(args.webos_version), args.host])


if __name__ == '__main__':
    raise SystemExit(main())
