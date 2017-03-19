# (c) 2005 Ian Bicking and contributors; written for Paste
# (http://pythonpaste.org) Licensed under the MIT license:
# http://www.opensource.org/licenses/mit-license.php
#
# For discussion of daemonizing:
# http://aspn.activestate.com/ASPN/Cookbook/Python/Recipe/278731
#
# Code taken also from QP: http://www.mems-exchange.org/software/qp/ From
# lib/site.py

import argparse
import os
import re
import sys
import textwrap

import hupper
import plaster

from pyramid.scripts.common import parse_vars
from pyramid.path import AssetResolver
from pyramid.settings import aslist

from .util import loadapp, loadserver


def main(argv=sys.argv, quiet=False):
    command = PlServeCommand(argv, quiet=quiet)
    return command.run()


class PlServeCommand(object):

    description = """\
    This command serves a web application that uses a PasteDeploy
    configuration file for the server and application.

    You can also include variable assignments like 'http_port=8080'
    and then use %(http_port)s in your config files.
    """
    default_verbosity = 1

    parser = argparse.ArgumentParser(
        description=textwrap.dedent(description),
        formatter_class=argparse.RawDescriptionHelpFormatter,
        )
    parser.add_argument(
        '-n', '--app-name',
        dest='app_name',
        metavar='NAME',
        help="Load the named application (default main)")
    parser.add_argument(
        '-s', '--server',
        dest='server',
        metavar='SERVER_TYPE',
        help="Use the named server.")
    parser.add_argument(
        '--server-name',
        dest='server_name',
        metavar='SECTION_NAME',
        help=("Use the named server as defined in the configuration file "
              "(default: main)"))
    parser.add_argument(
        '--reload',
        dest='reload',
        action='store_true',
        help="Use auto-restart file monitor")
    parser.add_argument(
        '--reload-interval',
        dest='reload_interval',
        default=1,
        help=("Seconds between checking files (low number can cause "
              "significant CPU usage)"))
    parser.add_argument(
        '-v', '--verbose',
        default=default_verbosity,
        dest='verbose',
        action='count',
        help="Set verbose level (default " + str(default_verbosity) + ")")
    parser.add_argument(
        '-q', '--quiet',
        action='store_const',
        const=0,
        dest='verbose',
        help="Suppress verbose output")
    parser.add_argument(
        'config_uri',
        nargs='?',
        default=None,
        help='The URI to the configuration file.',
        )
    parser.add_argument(
        'config_vars',
        nargs='*',
        default=(),
        help="Variables required by the config file. For example, "
             "`http_port=%%(http_port)s` would expect `http_port=8080` to be "
             "passed here.",
        )

    loadapp = staticmethod(loadapp)  # testing
    loadserver = staticmethod(loadserver)  # testing

    _scheme_re = re.compile(r'^[a-z][a-z]+:', re.I)

    def __init__(self, argv, quiet=False):
        self.args = self.parser.parse_args(argv[1:])
        if quiet:
            self.args.verbose = 0
        self.watch_files = []

    def out(self, msg): # pragma: no cover
        if self.args.verbose > 0:
            print(msg)

    def get_config_vars(self):
        restvars = self.args.config_vars
        return parse_vars(restvars)

    def pserve_file_config(self, filename, global_conf=None):
        here = os.path.abspath(os.path.dirname(filename))

        loader = plaster.get_loader(filename)
        if 'plserve' not in loader.get_sections():
            return
        items = loader.get_settings('plshell')

        watch_files = aslist(items.get('watch_files', ''), flatten=False)

        # track file paths relative to the ini file
        resolver = AssetResolver(package=None)
        for file in watch_files:
            if ':' in file:
                file = resolver.resolve(file).abspath()
            elif not os.path.isabs(file):
                file = os.path.join(here, file)
            self.watch_files.append(os.path.abspath(file))

    def run(self):  # pragma: no cover
        if not self.args.config_uri:
            self.out('You must give a config file')
            return 2
        app_spec = self.args.config_uri

        vars = self.get_config_vars()
        app_name = self.args.app_name

        base = os.getcwd()
        if not self._scheme_re.search(app_spec):
            config_path = os.path.join(base, app_spec)
            app_spec = 'config:' + app_spec
        else:
            config_path = None
        server_name = self.args.server_name
        if self.args.server:
            server_spec = 'egg:pyramid'
            assert server_name is None
            server_name = self.args.server
        else:
            server_spec = app_spec

        if self.args.reload and not hupper.is_active():
            if self.args.verbose > 1:
                self.out('Running reloading file monitor')
            hupper.start_reloader(
                'pyramid_plaster.plserve.main',
                reload_interval=int(self.args.reload_interval),
                verbose=self.args.verbose,
            )
            return 0

        if config_path:
            plaster.setup_logging(config_path)
            self.pserve_file_config(config_path, global_conf=vars)
            self.watch_files.append(config_path)

        if hupper.is_active():
            reloader = hupper.get_reloader()
            reloader.watch_files(self.watch_files)

        server = self.loadserver(
            config_path, name=server_name, relative_to=base, global_conf=vars)

        app = self.loadapp(
            config_path, name=app_name, relative_to=base, global_conf=vars)

        if self.args.verbose > 0:
            if hasattr(os, 'getpid'):
                msg = 'Starting server in PID %i.' % os.getpid()
            else:
                msg = 'Starting server.'
            self.out(msg)

        try:
            server(app)
        except (SystemExit, KeyboardInterrupt) as e:
            if self.args.verbose > 1:
                raise
            if str(e):
                msg = ' ' + str(e)
            else:
                msg = ''
            self.out('Exiting%s (-v to see traceback)' % msg)

if __name__ == '__main__':  # pragma: no cover
    sys.exit(main() or 0)
