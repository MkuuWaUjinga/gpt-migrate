import subprocess
import typer
from yaspin import yaspin
from pathlib import Path
from tree_sitter import Language, Parser, Node
from collections.abc import Iterator
from typing import List

from config import EXTENSION_TO_TREE_SITTER_GRAMMAR_REPO, EXTENSION_TO_LANGUAGE

def decompose_file(file_path: str) -> Iterator[Node]:
    # Do a first-level parse tree decomposition of the file at file_path
    with yaspin(text="Decomposing file", spinner="dots") as spinner:
        repo_url = EXTENSION_TO_TREE_SITTER_GRAMMAR_REPO.get(file_path.split('.')[-1])

        if not repo_url:
            success_text = typer.style("Couldn't find tree-sitter grammar for programming language {}. Aborting decomposition of file.".format(EXTENSION_TO_LANGUAGE.get(file_path.split('.')[-1])), fg=typer.colors.RED)
            typer.echo(success_text)

        repo_name = repo_url.split('/')[-1]
        if not Path("cache/tree-sitter/" + repo_name).exists():
            Path("cache/tree-sitter").mkdir(parents=True, exist_ok=True)
            result = subprocess.run(["git", "clone", repo_url], cwd="cache/tree-sitter", stdout=subprocess.PIPE, stderr=subprocess.STDOUT, check=True, text=True)

        grammar_lib_path = Path("cache/tree-sitter/my-languages.so")
        if grammar_lib_path.exists():
            grammar_lib_path.unlink()

        Language.build_library(
            'cache/tree-sitter/my-languages.so',
            ['cache/tree-sitter/' + repo_name]
        )

        lang = Language('cache/tree-sitter/my-languages.so', repo_url.split('-')[-1])
        parser = Parser()
        parser.set_language(lang)

        with open(file_path) as f:
            source_code = f.read()  

        tree = parser.parse(bytes(source_code, "utf8"))

        root_node = tree.root_node

        for child in root_node.children:
            yield child
        
        spinner.ok("✅ ")

def get_identifiers(node: Node, only_outer_scope=False) -> Node:
    # Do a breadth-first search of the parse tree to find all identifiers
    outer_scope_level = None
    queue = [(node, 0)]
    while queue:
        node, level = queue.pop(0)
        if only_outer_scope and outer_scope_level is not None and level > outer_scope_level:
            return
        if node.type == 'identifier': # TODO: might be brittle. Some language grammars potentially don't have this node type.
            yield node.text
            if only_outer_scope:
                outer_scope_level = level
        
        for child in node.children:
            queue.append((child, level + 1))
            
def get_in_file_deps(nodes: List[Node]):
    top_level_identifiers = [set(get_identifiers(node, only_outer_scope=True)) for node in nodes]
    in_file_deps = []
    for i, node in enumerate(nodes):
        node_infile_deps = []
        for j, top_level_identifier in enumerate(top_level_identifiers):
            for identifier in get_identifiers(node):
                # Add code snippet if top-level identifier is used in current node and is not the same node
                if identifier in top_level_identifier and i != j:
                    node_infile_deps.append(nodes[j].text)
        # Remove potential duplicates
        in_file_deps.append(list(dict.fromkeys(node_infile_deps)))
    return in_file_deps

if __name__ == "__main__":
    from parser import decompose_file
    nodes = list(decompose_file("test.py"))
    print(nodes)
    deps = get_in_file_deps(nodes)
    print(deps)