"""
This module is experimental and should not be used in production.
Probably not working already.
"""

import ast
import sys


class FunctionNotFoundException(Exception):
    pass


class LineNotFoundException(Exception):
    pass


class MyTransformer(ast.NodeTransformer):
    """
    A simple transformer that replaces a line in a function using the ast module.
    """
    def __init__(self, function_name: str, original_line: str, patched_line: str):
        self.function_name: str = function_name
        self.original_line: str = original_line
        self.patched_line: str = patched_line
        self.function_found: bool = False
        self.line_found: bool = False

    def visit_FunctionDef(self, node):
        if node.name == self.function_name:
            self.function_found = True
            self.generic_visit(node)
        return node

    def visit_Assign(self, node):
        if self.function_found:
            # Check if this is an assignment to 'command'
            if isinstance(node.targets[0], ast.Name) and node.targets[0].id == 'command':
                # Check if the value is a binary operation (e.g., 1 + 4)
                if isinstance(node.value, ast.BinOp) and isinstance(node.value.left, ast.Num) and isinstance(node.value.right, ast.Num):
                    left_value = node.value.left.n
                    right_value = node.value.right.n
                    # Check if the operation matches the expected original (e.g., 1 + 4)
                    if left_value == 1 and right_value == 4:
                        self.line_found = True
                        # Replace the line with the patched line
                        return ast.parse(self.patched_line).body[0].value
        return node

    def convert_node_to_code(self, node):
        # Handle different types of nodes
        if isinstance(node, ast.JoinedStr):
            return ''.join(self.convert_node_to_code(value) for value in node.values)
        elif isinstance(node, ast.Str):
            return repr(node.s)
        elif isinstance(node, ast.FormattedValue):
            return f'{{ {self.convert_node_to_code(node.value)} }}'
        elif isinstance(node, ast.Name):
            return node.id
        elif isinstance(node, ast.Attribute):
            return f'{self.convert_node_to_code(node.value)}.{node.attr}'
        elif isinstance(node, ast.Assign):
            targets = ''.join(self.convert_node_to_code(t) for t in node.targets)
            value = self.convert_node_to_code(node.value)
            return f'{targets} = {value}'
        # Add more cases as needed
        return ''


class MyTransformerAstor(ast.NodeTransformer):
    """
    Same as MyTransformer, but uses astor to replace the line.
    The problem with astor is that it is not maintained on regular basis.
    But astor is a better choice if you want to preserve the formatting of the original code.
    """
    def __init__(self, function_name, original_line, patched_line):
        import astor
        self.function_name = function_name
        self.original_line = original_line
        self.patched_line = patched_line
        self.function_found = False
        self.line_found = False

    def visit_FunctionDef(self, node):
        if node.name == self.function_name:
            self.function_found = True
            self.generic_visit(node)
        return node

    def visit_Assign(self, node):
        if self.function_found and isinstance(node.value, ast.JoinedStr):
            if self.original_line in astor.to_source(node):
                self.line_found = True
                # Replace the line with the patched line
                return ast.parse(self.patched_line).body[0].value
        return node


def import_and_patch_module(
        module_name_to_be_imported: str,
        file_path: str,
        function_name_to_find: str,
        original_line_to_be_patched: str,
        patched_line: str
):
    """
    Imports a module and patches a line in a function.

    :param module_name_to_be_imported: string, the name of the module to be imported.
    :param file_path: string, the path to the python file containing the function to be patched.
    :param function_name_to_find: string, the name of the function to be patched.
    :param original_line_to_be_patched: string, the original line to be patched.
    :param patched_line: string, the patched line that will replace the original line.
    :return:

    Usage:
        try:
            module_name = 'your_module_name'
            file_path = 'path/to/your/module.py'
            function_name = 'process_object'
            original_line = "command = f'{file_path}'"
            patched_line = "command = f'\"{file_path}\"'"

            patched_module = import_and_patch_module(module_name, file_path, function_name, original_line, patched_line)
            # Use `patched_module` as needed
        except FunctionNotFoundException as e:
            print(f"Error: {e}")
        except LineNotFoundException as e:
            print(f"Error: {e}")
    """

    # Read the source file
    with open(file_path, 'r') as file:
        source = file.read()

    # Parse the source code into an AST
    parsed_source = ast.parse(source)

    # Transform the AST with the specified parameters
    transformer = MyTransformerAstor(function_name_to_find, original_line_to_be_patched, patched_line)
    new_ast = transformer.visit(parsed_source)

    # Check if the function and line were found
    if not transformer.function_found:
        raise FunctionNotFoundException(f"Function '{function_name_to_find}' not found in {file_path}")
    if not transformer.line_found:
        raise LineNotFoundException(
            f"Line '{original_line_to_be_patched}' not found in function '{function_name_to_find}'")

    # Compile the modified AST
    compiled_code = compile(new_ast, filename=file_path, mode='exec')

    # Create a new module to hold the compiled code
    new_module = type(sys)(module_name_to_be_imported)
    new_module.__file__ = file_path

    # Execute the compiled code in the context of the new module
    exec(compiled_code, new_module.__dict__)

    return new_module
