"""
Serve command for Pecan.
"""
import os
import sys
import time
import subprocess

from pecan.commands import BaseCommand


class ServeCommand(BaseCommand):
    """
    Serves a Pecan web application.

    This command serves a Pecan web application using the provided
    configuration file for the server and application.
    """

    arguments = BaseCommand.arguments + ({
        'name': '--reload',
        'help': 'Watch for changes and automatically reload.',
        'default': False,
        'action': 'store_true'
    },)

    def run(self, args):
        super(ServeCommand, self).run(args)
        app = self.load_app()
        self.serve(app, app.config)

    def create_subprocess(self):
        self.server_process = subprocess.Popen(
            [arg for arg in sys.argv if arg != '--reload'],
            stdout=sys.stdout, stderr=sys.stderr
        )

    def watch_and_spawn(self, conf):
        from watchdog.observers import Observer
        from watchdog.events import (
            FileSystemEventHandler, FileSystemMovedEvent, FileModifiedEvent,
            DirModifiedEvent
        )

        print 'Monitoring for changes...'
        self.create_subprocess()

        parent = self

        class AggressiveEventHandler(FileSystemEventHandler):
            def should_reload(self, event):
                for t in (
                    FileSystemMovedEvent, FileModifiedEvent, DirModifiedEvent
                ):
                    if isinstance(event, t):
                        return True
                return False

            def on_modified(self, event):
                if self.should_reload(event):
                    parent.server_process.kill()
                    parent.create_subprocess()

        # Determine a list of file paths to monitor
        paths = self.paths_to_monitor(conf)

        event_handler = AggressiveEventHandler()
        for path, recurse in paths:
            observer = Observer()
            observer.schedule(
                event_handler,
                path=path,
                recursive=recurse
            )
            observer.start()

        try:
            while True:
                time.sleep(1)
        except KeyboardInterrupt:
            pass

    def paths_to_monitor(self, conf):
        paths = []

        for package_name in getattr(conf.app, 'modules', []):
            module = __import__(package_name, fromlist=['app'])
            if hasattr(module, 'app') and hasattr(module.app, 'setup_app'):
                paths.append((
                    os.path.dirname(module.__file__),
                    True
                ))
                break

        paths.append((os.path.dirname(conf.__file__), False))
        return paths

    def _serve(self, app, conf):
        from wsgiref.simple_server import make_server

        host, port = conf.server.host, int(conf.server.port)
        srv = make_server(host, port, app)

        print 'Starting server in PID %s' % os.getpid()

        if host == '0.0.0.0':
            print 'serving on 0.0.0.0:%s, view at http://127.0.0.1:%s' % \
                (port, port)
        else:
            print "serving on http://%s:%s" % (host, port)

        try:
            srv.serve_forever()
        except KeyboardInterrupt:
            # allow CTRL+C to shutdown
            pass

    def serve(self, app, conf):
        """
        A very simple approach for a WSGI server.
        """

        if self.args.reload:
            try:
                self.watch_and_spawn(conf)
            except ImportError:
                print('The `--reload` option requires `watchdog` to be '
                      'installed.')
                print('   $ pip install watchdog')
        else:
            self._serve(app, conf)


def gunicorn_run():
    """
    The ``gunicorn_pecan`` command for launching ``pecan`` applications
    """
    try:
        from gunicorn.app.wsgiapp import WSGIApplication
    except ImportError as exc:
        args = exc.args
        arg0 = args[0] if args else ''
        arg0 += ' (are you sure `gunicorn` is installed?)'
        exc.args = (arg0,) + args[1:]
        raise

    class PecanApplication(WSGIApplication):

        def init(self, parser, opts, args):
            if len(args) != 1:
                parser.error("No configuration file was specified.")

            self.cfgfname = os.path.normpath(
                os.path.join(os.getcwd(), args[0])
            )
            self.cfgfname = os.path.abspath(self.cfgfname)
            if not os.path.exists(self.cfgfname):
                parser.error("Config file not found: %s" % self.cfgfname)

            from pecan.configuration import _runtime_conf, set_config
            set_config(self.cfgfname, overwrite=True)

            # If available, use the host and port from the pecan config file
            cfg = {}
            if _runtime_conf.get('server'):
                server = _runtime_conf['server']
                if hasattr(server, 'host') and hasattr(server, 'port'):
                    cfg['bind'] = '%s:%s' % (
                        server.host, server.port
                    )
            return cfg

        def load(self):
            from pecan.deploy import deploy
            return deploy(self.cfgfname)

    PecanApplication("%(prog)s [OPTIONS] config.py").run()
