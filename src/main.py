import ast
import glob
import os
import logging
from argparse import ArgumentParser
from typing import Iterable, Any, Tuple, Dict
from graphviz import Digraph
from graphviz.backend import FORMATS

__version__ = "0.1.0"

TRACE = 5
logging.addLevelName(TRACE, "TRACE")


class TraceLogger(logging.getLoggerClass()):
    def trace(self, msg, *args, **kwargs):
        self.log(TRACE, msg, *args, **kwargs)

logging.setLoggerClass(TraceLogger)
logging.basicConfig(level=logging.NOTSET)

logger = logging.getLogger("migraph")

verbosity2loglevel = {
    0: logging.INFO,
    1: logging.DEBUG,
    2: TRACE
}


def get_migrations_paths(dj_root: str):
    logger.debug("Search migrations files of project %s", dj_root)
    return glob.iglob(os.path.normpath(os.path.join(dj_root, '**/migrations/*.py')), recursive=True)


def get_dependencies(file_: Any) -> Iterable[Any]:
    dependencies = []

    class ClassDefVisitor(ast.NodeVisitor):
        def visit_ClassDef(self, node: ast.ClassDef):

            class AssignVisitor(ast.NodeVisitor):
                def visit_Assign(self, node: ast.Assign):
                    logger.trace("Found assign node: %s", node.targets[0].id)
                    if len(node.targets) == 1 and node.targets[0].id == 'dependencies':
                        migrations_id = [(t.elts[0].s, t.elts[1].s) for t in
                                         filter(lambda n: isinstance(n, ast.Tuple), node.value.elts)]
                        logger.trace("Dependencies of %s found: %s", file_, migrations_id)
                        dependencies.extend(migrations_id)
            if node.name == 'Migration':
                logger.trace("Found migration class definition in %s", file_)
                AssignVisitor().visit(node)

    logger.debug("Start processing of %s", file_)
    migration_src = open(file_, mode='r').read()
    module_ = ast.parse(migration_src)  # type: ast.Module
    ClassDefVisitor().visit(module_)
    logger.debug("Dependencies of %s: %s", file_, dependencies)
    return dependencies


def add_edge(from_: Tuple[str, str], to: Tuple[str, str]):
    logger.trace("Adding edge from %s to %s", from_, to)
    from_app = from_[0]
    from_migration = from_[1]
    from_name = from_app+'__'+from_migration
    from_app_graph = app_graphs.setdefault(from_app, Digraph(name='cluster__' + from_app,
                                                             graph_attr=dict(label=from_app)))  # type: Digraph
    from_app_graph.node(from_name, from_migration)

    to_app = to[0]
    to_migration = to[1]
    to_app_graph = app_graphs.setdefault(to_app, Digraph(name='cluster__'+to_app,
                                                         graph_attr=dict(label=to_app)))  # type: Digraph
    to_name = to_app+'__'+to_migration
    to_app_graph.node(to_name, to_migration)

    to_app_graph.edge(from_name, to_name)


def get_app_migration(path: str)->(str, str):
    migration_path, migration_name = os.path.split(path)
    return os.path.basename(os.path.dirname(migration_path)), os.path.splitext(migration_name)[0]

if __name__ == "__main__":

    arg_parser = ArgumentParser(prog="migraph", description="Visualize django migrations graph")
    arg_parser.add_argument('project_path', default='.', help="path to django project")
    arg_parser.add_argument('-o', '--output', default='.', help="where to save dot file")
    arg_parser.add_argument('-n', '--name', default='migrations', help="name of out dot file")
    arg_parser.add_argument('-v', '--view', action='store_true', help="open result image immediately")
    arg_parser.add_argument('-V', '--verbose', action='count', default=0, help="verbose level. Up to 2")
    arg_parser.add_argument('--version', action='version', version="%(prog)s "+__version__)

    image_group = arg_parser.add_mutually_exclusive_group()
    image_group.add_argument('-f', '--format', default='svg', choices=FORMATS, help="image output format")
    image_group.add_argument('--no-image', dest='render', action='store_false', default=True, help="don't render")

    args = arg_parser.parse_args()

    # handle conflict manually as argparse library does not allow one argument in multiple groups, see http://bugs.python.org/issue10984
    if not args.render and args.view:
        arg_parser.print_usage()
        logger.error("migraph: error: argument -v/--view: not allowed with argument --no-image")

    logger.setLevel(verbosity2loglevel[args.verbose])

    django_root = args.project_path

    graph = Digraph(graph_attr=dict(label="Migration graph of {} Django project".format(django_root)), name=args.name,
                    format=args.format)

    app_graphs = {}  # type: Dict[str, Digraph]

    for file_path in get_migrations_paths(django_root):
        logger.trace("Processing migration %s", file_path)
        app, migration_name = get_app_migration(file_path)
        logger.trace("app: %s, migration name: %s", app, migration_name)
        for dep in get_dependencies(file_path):
            add_edge(from_=(app, migration_name), to=dep)

    for _, subgraph in app_graphs.items():
        graph.subgraph(subgraph)

    if args.render:
        out_path = graph.render(directory=args.output, view=args.view)
        logger.debug("Saved image to %s", os.path.abspath(out_path))
    else:
        out_path = graph.save(directory=args.output)
        logger.debug("Saved dotfile to %s", os.path.abspath(out_path))

