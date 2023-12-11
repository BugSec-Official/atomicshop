import ast
from typing import Union


class FunctionNotFoundException(Exception):
    def __init__(self, function_name: str):
        message = f"Function '{function_name}' not found."
        super().__init__(message)


class ClassNotFoundException(Exception):
    def __init__(self, class_name: str):
        message = f"Class '{class_name}' not found."
        super().__init__(message)


class FunctionInClassNotFoundException(Exception):
    def __init__(self, class_name: str, function_name: str):
        message = f"Function '{function_name}' not found in class '{class_name}'."
        super().__init__(message)


class CodeBlockVisitor(ast.NodeVisitor):
    def __init__(self, class_name: str = None, function_name: str = None):
        """
        AST visitor wrapper to find the start and end line of a class or function.
        If both class_name and function_name are specified, will find the function inside the class.

        :param class_name: string, name of the class to find. If None, will find a function.
        :param function_name: string, name of the function to find. If None, will find a class.
        """

        if class_name is None and function_name is None:
            raise ValueError("Both class_name and function_name cannot be None.")

        self.class_name = class_name
        self.function_name = function_name
        # List of tuples. Each tuple contains start and end line numbers of the code block.
        self.code_blocks_start_end: list[tuple[int, int]] = list()
        self.in_class = False
        self.class_found = False
        self.function_found = False

    def visit_ClassDef(self, node):
        if self.class_name == node.name:
            self.in_class = True
            self.class_found = True
            # Record the class's line numbers if no function name is specified
            if not self.function_name:
                self.code_blocks_start_end.append((node.lineno, node.end_lineno))
            else:
                self.generic_visit(node)
            self.in_class = False
        elif self.class_name is None:
            # Visit the class if no specific class is being searched for
            self.generic_visit(node)

    def visit_FunctionDef(self, node):
        if self.function_name == node.name:
            if (self.class_name and self.in_class) or self.class_name is None:
                self.code_blocks_start_end.append((node.lineno, node.end_lineno))
                self.function_found = True


def find_code_block(
        filename: str,
        class_name: Union[str, None] = None,
        function_name: Union[str, None] = None
) -> list[tuple[int, int]]:
    """
    Use AST to find the start and end lines of the class or function, or function inside a class if both are specified.
    :param filename: string, path to the python file.
    :param class_name: string, name of the class to find. If None, will find a function.
    :param function_name: string, name of the function to find. If None, will find a class.
    :return: list of tuples. Each tuple is (int, int) start and end line numbers of the code block.
    """

    if class_name is None and function_name is None:
        raise ValueError("Both class_name and function_name cannot be None.")

    with open(filename, 'r') as file:
        node = ast.parse(file.read())

    visitor = CodeBlockVisitor(class_name, function_name)
    visitor.visit(node)

    if class_name and not any(node.name == class_name for node in ast.walk(node) if isinstance(node, ast.ClassDef)):
        raise ClassNotFoundException(class_name)

    if function_name and not any(
            node.name == function_name for node in ast.walk(node) if isinstance(node, ast.FunctionDef)):
        if class_name:
            raise FunctionInClassNotFoundException(class_name, function_name)
        else:
            raise FunctionNotFoundException(function_name)

    if not visitor.code_blocks_start_end:
        if class_name:
            raise ClassNotFoundException(class_name)
        else:
            raise FunctionNotFoundException(function_name)

    return visitor.code_blocks_start_end
