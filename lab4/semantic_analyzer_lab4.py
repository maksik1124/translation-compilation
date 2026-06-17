
from __future__ import annotations

import argparse
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable

from syntax_analyzer_lab3 import ASTNode, analyze_source
from lexer_lab2 import read_source_file


class SemanticError(Exception):
    """Семантическая ошибка с типом и пояснением."""


@dataclass
class Symbol:
    name: str
    type_name: str
    scope: str
    role: str
    declared: bool = True
    initialized: bool = False
    declaration_line: int | None = None


@dataclass(frozen=True)
class FunctionSignature:
    name: str
    return_type: str
    parameter_types: tuple[str, ...]


@dataclass(frozen=True)
class Triad:
    operation: str
    operand1: str = "-"
    operand2: str = "-"

    def __str__(self) -> str:
        return f"{self.operation} ({self.operand1}, {self.operand2})"


class SourceLocator:
    """Определяет строки объявлений для информационной таблицы символов."""

    def __init__(self, source: str | None):
        self.lines: dict[tuple[str, str], list[int]] = {}
        if source:
            self._scan(source)

    def _scan(self, source: str) -> None:
        current_function: str | None = None
        brace_depth = 0
        function_depth = 0

        for number, raw_line in enumerate(source.splitlines(), start=1):
            line = raw_line.strip()
            function_match = re.match(
                r"^(?:int|bool)\s+([A-Za-z_]\w*)\s*\(([^)]*)\)\s*\{?",
                line,
            )
            if function_match:
                current_function = function_match.group(1)
                function_depth = brace_depth + line.count("{") - line.count("}")
                params = function_match.group(2).strip()
                if params:
                    for part in params.split(","):
                        match = re.match(r"\s*(?:int|bool)\s+([A-Za-z_]\w*)", part)
                        if match:
                            self.lines.setdefault(
                                (current_function, match.group(1)), []
                            ).append(number)

            if current_function:
                declarations = []
                for_match = re.search(r"\bfor\s*\(\s*(?:int|bool)\s+([A-Za-z_]\w*)", line)
                if for_match:
                    declarations.append(for_match.group(1))
                elif not function_match:
                    decl_match = re.match(r"^(?:int|bool)\s+(.+);$", line)
                    if decl_match:
                        for declarator in decl_match.group(1).split(","):
                            name_match = re.match(r"\s*([A-Za-z_]\w*)", declarator)
                            if name_match:
                                declarations.append(name_match.group(1))
                for name in declarations:
                    self.lines.setdefault((current_function, name), []).append(number)

            brace_depth += line.count("{") - line.count("}")
            if current_function and brace_depth < function_depth:
                current_function = None

    def line_for(self, function: str, name: str) -> int | None:
        values = self.lines.get((function, name), [])
        return values.pop(0) if values else None


class SemanticAnalyzer:
    """Обход AST, проверка типов и генерация промежуточного кода."""

    ARITHMETIC_OPERATORS = {"+", "-", "*"}
    RELATIONAL_OPERATORS = {"<", ">"}

    def __init__(self, source: str | None = None):
        self.symbols: list[Symbol] = []
        self.functions: dict[str, FunctionSignature] = {}
        self.triads: list[Triad] = []
        self.scope_stack: list[str] = []
        self.current_function = ""
        self.current_return_type = ""
        self.return_found = False
        self.scope_counters: dict[tuple[str, str], int] = {}
        self.locator = SourceLocator(source)

    @property
    def current_scope(self) -> str:
        return "/".join(self.scope_stack)

    def error(self, error_type: str, message: str) -> None:
        raise SemanticError(
            f"Семантическая ошибка: {error_type}\nПояснение: {message}"
        )

    def add_triad(self, operation: str, operand1: str = "-", operand2: str = "-") -> str:
        self.triads.append(Triad(operation, str(operand1), str(operand2)))
        return f"^{len(self.triads)}"

    def enter_scope(self, kind: str | None = None) -> None:
        if kind is None:
            self.scope_stack.append(self.current_function)
            return
        parent = self.current_scope
        key = (parent, kind)
        number = self.scope_counters.get(key, 0) + 1
        self.scope_counters[key] = number
        self.scope_stack.append(f"{kind}#{number}")

    def leave_scope(self) -> None:
        self.scope_stack.pop()

    def add_symbol(
        self,
        name: str,
        type_name: str,
        role: str,
        initialized: bool,
    ) -> Symbol:
        if any(item.name == name and item.scope == self.current_scope for item in self.symbols):
            self.error(
                "повторное объявление",
                f"Идентификатор '{name}' уже объявлен в области '{self.current_scope}'.",
            )
        line = self.locator.line_for(self.current_function, name)
        symbol = Symbol(
            name=name,
            type_name=type_name,
            scope=self.current_scope,
            role=role,
            initialized=initialized,
            declaration_line=line,
        )
        self.symbols.append(symbol)
        return symbol

    def find_symbol(self, name: str) -> Symbol | None:
        for depth in range(len(self.scope_stack), 0, -1):
            scope = "/".join(self.scope_stack[:depth])
            for item in reversed(self.symbols):
                if item.name == name and item.scope == scope:
                    return item
        return None

    def require_symbol(self, name: str, require_initialized: bool = False) -> Symbol:
        symbol = self.find_symbol(name)
        if symbol is None:
            self.error(
                "использование необъявленной переменной",
                f"Переменная '{name}' используется до объявления в доступной области видимости.",
            )
        if require_initialized and not symbol.initialized:
            self.error(
                "использование неинициализированной переменной",
                f"Переменная '{name}' используется до присваивания значения.",
            )
        return symbol

    def analyze(self, ast: ASTNode) -> "SemanticAnalyzer":
        if ast.kind != "Program":
            self.error("некорректный корень AST", "Ожидался узел Program.")
        self.collect_functions(ast)
        for node in ast.children:
            if node.kind == "Function":
                self.analyze_function(node)
        return self

    def collect_functions(self, ast: ASTNode) -> None:
        for node in ast.children:
            if node.kind != "Function":
                continue
            name = node.value or ""
            return_type = self.child(node, "ReturnType").value or ""
            parameters = self.child(node, "Parameters")
            parameter_types = tuple(
                self.child(parameter, "Type").value or ""
                for parameter in parameters.children
            )
            if name in self.functions:
                self.error(
                    "повторное объявление функции",
                    f"Функция '{name}' уже определена.",
                )
            self.functions[name] = FunctionSignature(name, return_type, parameter_types)

    @staticmethod
    def child(node: ASTNode, kind: str) -> ASTNode:
        for child in node.children:
            if child.kind == kind:
                return child
        raise SemanticError(
            f"Семантическая ошибка: повреждённое AST\n"
            f"Пояснение: в узле '{node.kind}' отсутствует дочерний узел '{kind}'."
        )

    def analyze_function(self, node: ASTNode) -> None:
        self.current_function = node.value or ""
        self.current_return_type = self.child(node, "ReturnType").value or ""
        self.return_found = False
        self.enter_scope()

        parameters = self.child(node, "Parameters")
        for parameter in parameters.children:
            name = parameter.value or ""
            type_name = self.child(parameter, "Type").value or ""
            self.add_symbol(name, type_name, "параметр", True)

        self.analyze_body(self.child(node, "Body"))
        if self.current_return_type != "void" and not self.return_found:
            self.error(
                "отсутствует return",
                f"Функция '{self.current_function}' должна возвращать значение типа "
                f"'{self.current_return_type}'.",
            )
        self.leave_scope()

    def analyze_body(self, node: ASTNode) -> None:
        for child in node.children:
            self.analyze_statement(child)

    def analyze_statement(self, node: ASTNode) -> None:
        handlers = {
            "VarDecl": self.analyze_var_decl,
            "Assign": self.analyze_assign,
            "PostfixIncrement": self.analyze_increment,
            "Call": self.analyze_call_statement,
            "Return": self.analyze_return,
            "If": self.analyze_if,
            "For": self.analyze_for,
            "While": self.analyze_while,
            "Output": self.analyze_output,
        }
        handler = handlers.get(node.kind)
        if handler is None:
            self.error(
                "неподдерживаемый оператор",
                f"Для узла '{node.kind}' не определено семантическое правило.",
            )
        handler(node)

    def analyze_var_decl(self, node: ASTNode) -> None:
        type_name = self.child(node, "Type").value or ""
        for variable in node.children[1:]:
            if variable.kind != "Variable":
                continue
            name = variable.value or ""
            initialized = False
            place: str | None = None
            if variable.children:
                initializer = self.child(variable, "Initializer")
                value_type, place = self.analyze_expression(initializer.children[0])
                if value_type != type_name:
                    self.error(
                        "несоответствие типов",
                        f"Переменной '{name}' типа '{type_name}' нельзя присвоить "
                        f"значение типа '{value_type}'.",
                    )
                initialized = True
            self.add_symbol(name, type_name, "переменная", initialized)
            if place is not None:
                self.add_triad("=", name, place)

    def analyze_assign(self, node: ASTNode) -> None:
        target_name = self.child(node, "Target").value or ""
        symbol = self.require_symbol(target_name)
        value_node = self.child(node, "Value").children[0]
        value_type, place = self.analyze_expression(value_node)
        if symbol.type_name != value_type:
            self.error(
                "несоответствие типов",
                f"Переменной '{target_name}' типа '{symbol.type_name}' нельзя "
                f"присвоить значение типа '{value_type}'.",
            )
        symbol.initialized = True
        self.add_triad("=", target_name, place)

    def analyze_increment(self, node: ASTNode) -> None:
        name = node.value or ""
        symbol = self.require_symbol(name, require_initialized=True)
        if symbol.type_name != "int":
            self.error(
                "некорректный тип инкремента",
                f"Оператор '++' применим только к int, но '{name}' имеет тип "
                f"'{symbol.type_name}'.",
            )
        self.add_triad("++", name, "-")

    def analyze_call_statement(self, node: ASTNode) -> None:
        self.analyze_call(node)

    def analyze_return(self, node: ASTNode) -> None:
        value_type, place = self.analyze_expression(node.children[0])
        if value_type != self.current_return_type:
            self.error(
                "несоответствие типа return",
                f"Функция '{self.current_function}' должна возвращать "
                f"'{self.current_return_type}', но выражение имеет тип '{value_type}'.",
            )
        self.return_found = True
        self.add_triad("return", place, "-")

    def analyze_if(self, node: ASTNode) -> None:
        condition = self.child(node, "Condition").children[0]
        condition_type, place = self.analyze_expression(condition)
        if condition_type != "bool":
            self.error(
                "некорректный тип условия",
                "Условие оператора if должно иметь тип bool.",
            )
        self.add_triad("if", place, "-")

        then_node = self.child(node, "Then")
        self.enter_scope("if")
        self.analyze_body(then_node.children[0])
        self.leave_scope()

        else_nodes = [child for child in node.children if child.kind == "Else"]
        if else_nodes:
            self.add_triad("else", "-", "-")
            self.enter_scope("else")
            self.analyze_body(else_nodes[0].children[0])
            self.leave_scope()
        self.add_triad("endif", "-", "-")

    def analyze_for(self, node: ASTNode) -> None:
        self.enter_scope("for")
        initialization = self.child(node, "Initialization")
        self.analyze_statement(initialization.children[0])

        condition = self.child(node, "Condition").children[0]
        condition_type, place = self.analyze_expression(condition)
        if condition_type != "bool":
            self.error(
                "некорректный тип условия",
                "Условие цикла for должно иметь тип bool.",
            )
        self.add_triad("for", place, "-")
        self.analyze_body(self.child(node, "Body"))
        update = self.child(node, "Update")
        self.analyze_statement(update.children[0])
        self.add_triad("endfor", "-", "-")
        self.leave_scope()

    def analyze_while(self, node: ASTNode) -> None:
        condition = self.child(node, "Condition").children[0]
        condition_type, place = self.analyze_expression(condition)
        if condition_type != "bool":
            self.error(
                "некорректный тип условия",
                "Условие цикла while должно иметь тип bool.",
            )
        self.add_triad("while", place, "-")
        self.enter_scope("while")
        self.analyze_body(self.child(node, "Body"))
        self.leave_scope()
        self.add_triad("endwhile", "-", "-")

    def analyze_output(self, node: ASTNode) -> None:
        for part in node.children:
            value_type, place = self.analyze_expression(part)
            if value_type not in {"int", "bool", "string", "endl"}:
                self.error(
                    "некорректный тип вывода",
                    f"Значение типа '{value_type}' нельзя вывести через cout.",
                )
            self.add_triad("out", place, "-")

    def analyze_expression(self, node: ASTNode) -> tuple[str, str]:
        if node.kind == "IntLiteral":
            return "int", node.value or "0"
        if node.kind == "BoolLiteral":
            return "bool", node.value or "false"
        if node.kind == "StringLiteral":
            return "string", node.value or '""'
        if node.kind == "Endl":
            return "endl", "endl"
        if node.kind == "Identifier":
            name = node.value or ""
            symbol = self.require_symbol(name, require_initialized=True)
            return symbol.type_name, name
        if node.kind in {"CallExpr", "Call"}:
            return self.analyze_call(node)
        if node.kind == "BinaryExpr":
            operator = node.value or ""
            left_type, left_place = self.analyze_expression(node.children[0])
            right_type, right_place = self.analyze_expression(node.children[1])

            if operator in self.ARITHMETIC_OPERATORS:
                if left_type != "int" or right_type != "int":
                    self.error(
                        "некорректные типы операндов",
                        f"Оператор '{operator}' можно применять только к int.",
                    )
                return "int", self.add_triad(operator, left_place, right_place)

            if operator in self.RELATIONAL_OPERATORS:
                if left_type != "int" or right_type != "int":
                    self.error(
                        "некорректные типы операндов",
                        f"Оператор '{operator}' можно применять только к int.",
                    )
                return "bool", self.add_triad(operator, left_place, right_place)

            if operator == "!=":
                if left_type != right_type or left_type not in {"int", "bool"}:
                    self.error(
                        "некорректные типы операндов",
                        "Операнды '!=' должны иметь одинаковый тип int или bool.",
                    )
                return "bool", self.add_triad(operator, left_place, right_place)

            if operator == "&&":
                if left_type != "bool" or right_type != "bool":
                    self.error(
                        "некорректные типы операндов",
                        "Оператор '&&' требует два операнда типа bool.",
                    )
                return "bool", self.add_triad(operator, left_place, right_place)

            self.error(
                "неизвестный оператор",
                f"Для оператора '{operator}' не задано семантическое правило.",
            )

        self.error(
            "неизвестное выражение",
            f"Не удалось определить тип узла '{node.kind}'.",
        )
        raise AssertionError("unreachable")

    def analyze_call(self, node: ASTNode) -> tuple[str, str]:
        function_name = node.value or ""
        signature = self.functions.get(function_name)
        if signature is None:
            self.error(
                "вызов необъявленной функции",
                f"Функция '{function_name}' не определена.",
            )
        arguments = self.child(node, "Arguments")
        actual: list[tuple[str, str]] = [
            self.analyze_expression(argument) for argument in arguments.children
        ]
        if len(actual) != len(signature.parameter_types):
            self.error(
                "неверное количество аргументов",
                f"Функция '{function_name}' ожидает {len(signature.parameter_types)} "
                f"аргумент(а), получено {len(actual)}.",
            )
        for index, ((actual_type, _), expected_type) in enumerate(
            zip(actual, signature.parameter_types), start=1
        ):
            if actual_type != expected_type:
                self.error(
                    "несоответствие типов аргументов",
                    f"Аргумент {index} функции '{function_name}' должен иметь тип "
                    f"'{expected_type}', получен '{actual_type}'.",
                )
        operands = [place for _, place in actual]
        operand1 = operands[0] if operands else "-"
        operand2 = operands[1] if len(operands) > 1 else "-"
        result = self.add_triad(f"call {function_name}", operand1, operand2)
        return signature.return_type, result

    def symbols_text(self) -> str:
        headers = [
            "Имя", "Тип", "Область", "Роль", "Объявлена", "Инициализирована", "Строка"
        ]
        rows = []
        for item in self.symbols:
            rows.append([
                item.name,
                item.type_name,
                item.scope,
                item.role,
                "+" if item.declared else "-",
                "+" if item.initialized else "-",
                str(item.declaration_line or "-"),
            ])
        widths = [max(len(headers[i]), *(len(row[i]) for row in rows)) for i in range(len(headers))]
        line = "+".join("-" * (width + 2) for width in widths)
        output = [
            " | ".join(headers[i].ljust(widths[i]) for i in range(len(headers))),
            line,
        ]
        output.extend(
            " | ".join(row[i].ljust(widths[i]) for i in range(len(headers)))
            for row in rows
        )
        return "\n".join(output)

    def triads_text(self) -> str:
        return "\n".join(
            f"{number}) {triad}" for number, triad in enumerate(self.triads, start=1)
        )


def semantic_analyze(ast: ASTNode, source: str | None = None) -> SemanticAnalyzer:
    return SemanticAnalyzer(source).analyze(ast)


def build_argument_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Семантический анализатор ЛР № 4")
    parser.add_argument("source", nargs="?", default="clean_test.cpp")
    parser.add_argument("--triads-output", metavar="FILE")
    return parser


def main(argv: Iterable[str] | None = None) -> int:
    args = build_argument_parser().parse_args(argv)
    try:
        source_path = Path(args.source)
        source = read_source_file(str(source_path))
        _, ast = analyze_source(source)
        analyzer = semantic_analyze(ast, source)
        print("РЕЗУЛЬТАТ СЕМАНТИЧЕСКОГО АНАЛИЗА\n")
        print("ТАБЛИЦА СИМВОЛОВ")
        print(analyzer.symbols_text())
        print("\nСемантический анализ завершён успешно. Ошибок не найдено.\n")
        print("ТРИАДЫ")
        print(analyzer.triads_text())
        if args.triads_output:
            Path(args.triads_output).write_text(analyzer.triads_text() + "\n", encoding="utf-8")
        return 0
    except (OSError, SemanticError) as error:
        print(error)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
