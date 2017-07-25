import ast
import glob
import sys
import os
from typing import Iterable, Any, Tuple, Dict
from graphviz import Digraph

django_root = sys.argv[1]


def get_migrations_paths(dj_root: str):
    print("Finding migrations files in dir ", dj_root)
    return glob.iglob(os.path.normpath(os.path.join(dj_root, '**/migrations/*.py')), recursive=True)


def get_dependencies(file_: Any) -> Iterable[Any]:
    dependencies = []

    class ClassDefVisitor(ast.NodeVisitor):
        def visit_ClassDef(self, node: ast.ClassDef):

            class AssignVisitor(ast.NodeVisitor):
                def visit_Assign(self, node: ast.Assign):
                    print("Meet assign:", node.targets[0])
                    if len(node.targets) == 1 and node.targets[0].id == 'dependencies':
                        print("Dependencies found:", node)
                        migrations_id = map(lambda t: (t.elts[0].s, t.elts[1].s),
                                            filter(lambda n: isinstance(n, ast.Tuple), node.value.elts))
                        dependencies.extend(list(migrations_id))
            if node.name == 'Migration':
                print("Meet migration class definition:", node)
                AssignVisitor().visit(node)

    migration_src = open(file_, mode='r').read()
    # print("Processing AST of module {}".format(migration_src))
    module_ = ast.parse(migration_src)  # type: ast.Module
    ClassDefVisitor().visit(module_)
    return dependencies


graph = Digraph(name='{} migration graph'.format(django_root), format='png')

app_graphs = {}  # type: Dict[str, Digraph]


def add_edge(from_: Tuple[str, str], to: Tuple[str, str]):
    print("adding edge from {} to {}".format(from_, to))
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

for file_path in get_migrations_paths(django_root):
    print("Processing {} migration".format(file_path))
    app, migration_name = get_app_migration(file_path)
    print("app: ", app, "migration name: ", migration_name)
    for dep in get_dependencies(file_path):
        add_edge(from_=(app, migration_name), to=dep)


for _, subgraph in app_graphs.items():
    graph.subgraph(subgraph)
print("rendering")
graph.render('migrations')
