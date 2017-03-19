import pkg_resources
import plaster
from pyramid.scripting import prepare
from waitress import serve as waitress_runner


# TODO: remove need for fake global_conf collection here by improving the protocol
def loadapp(config_uri, **global_conf):
    loader = plaster.get_loader(config_uri)
    section = loader.uri.fragment or 'app'
    config = loader.get_settings(section)
    scheme, resource = config.pop('use').split(':', 1)
    assert scheme in {'egg', 'wheel', 'package'}
    if "#" in resource:
        pkg, name = resource.split('#')
    else:
        pkg, name = resource, "main"

    ep = pkg_resources.get_entry_map(pkg)['plaster.app_factory'][name]

    app = ep.load()(**config)

    return app


# TODO: remove need for fake global_conf collection here by improving the protocol
def loadserver(config_uri, **global_conf):
    loader = plaster.get_loader(config_uri)
    section = loader.uri.fragment or 'server'
    config = loader.get_settings(section)
    scheme, resource = config.pop('use').split(':', 1)
    assert scheme in {'egg', 'wheel', 'package'}
    if "#" in resource:
        pkg, name = resource.split('#')
    else:
        pkg, name = resource, "main"

    ep = pkg_resources.get_entry_map(pkg)['plaster.server_factory'][name]

    server = ep.load()(**config)

    return server


def bootstrap(config_uri, request=None, options=None):
    app = loadapp(config_uri)

    env = prepare(request)
    env['app'] = app
    return env


def waitress_factory(**config):
    # I didn't feel like implementing the runner-to-factory adapter protocol above...
    def server(app):
        return waitress_runner(app, **config)
    return server
