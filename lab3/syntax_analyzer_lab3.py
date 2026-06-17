
from __future__ import annotations

import argparse
from dataclasses import dataclass, field
from pathlib import Path
from typing import Iterable, Sequence

from lexer_lab2 import lexical_analyze, read_source_file, validate


class ParserError(Exception):
    """Ошибка синтаксического анализа с координатами проблемного токена."""


@dataclass(frozen=True)
class Token:
    token_type: str
    lexeme: str
    index: int
    line: int
    column: int

    def short(self) -> str:
        return f"({self.token_type}, {self.lexeme})"


@dataclass
class ASTNode:
    """Узел абстрактного синтаксического дерева."""

    kind: str
    value: str | None = None
    children: list["ASTNode"] = field(default_factory=list)

    def add(self, child: "ASTNode | None") -> "ASTNode | None":
        if child is not None:
            self.children.append(child)
        return child

    @property
    def title(self) -> str:
        return f"{self.kind} {self.value}" if self.value is not None else self.kind

    def _tree_lines(self, prefix: str, is_last: bool) -> list[str]:
        connector = "└── " if is_last else "├── "
        lines = [prefix + connector + self.title]
        next_prefix = prefix + ("    " if is_last else "│   ")
        for number, child in enumerate(self.children):
            lines.extend(child._tree_lines(next_prefix, number == len(self.children) - 1))
        return lines

    def to_tree(self) -> str:
        lines = [self.title]
        for number, child in enumerate(self.children):
            lines.extend(child._tree_lines("", number == len(self.children) - 1))
        return "\n".join(lines)


BINARY_PRECEDENCE = {
    "&&": 1,
    "!=": 2,
    ">": 3,
    "<": 3,
    "+": 4,
    "-": 4,
    "*": 5,
}

TYPE_WORDS = {"int", "bool"}


def _offset_to_line_column(source: str, offset: int) -> tuple[int, int]:
    line = source.count("\n", 0, offset) + 1
    last_newline = source.rfind("\n", 0, offset)
    column = offset + 1 if last_newline == -1 else offset - last_newline
    return line, column


def add_token_positions(source: str, raw_tokens: Sequence[tuple[str, str]]) -> list[Token]:
    """Дополняет токены номером, строкой и столбцом исходного текста."""

    positioned: list[Token] = []
    cursor = 0
    for index, (token_type, lexeme) in enumerate(raw_tokens, start=1):
        offset = source.find(lexeme, cursor)
        if offset < 0:
            offset = cursor
        line, column = _offset_to_line_column(source, offset)
        positioned.append(Token(token_type, lexeme, index, line, column))
        cursor = offset + len(lexeme)

    eof_line, eof_column = _offset_to_line_column(source, len(source))
    positioned.append(Token("EOF", "EOF", len(raw_tokens) + 1, eof_line, eof_column))
    return positioned


class Parser:
    """Синтаксический анализатор методом рекурсивного спуска."""

    def __init__(self, tokens: Sequence[Token]):
        self.tokens = list(tokens)
        self.pos = 0

    @property
    def current(self) -> Token:
        return self.tokens[self.pos]

    def peek(self, distance: int = 1) -> Token:
        position = min(self.pos + distance, len(self.tokens) - 1)
        return self.tokens[position]

    def check(self, token_type: str | None = None, lexeme: str | None = None) -> bool:
        token = self.current
        if token_type is not None and token.token_type != token_type:
            return False
        if lexeme is not None and token.lexeme != lexeme:
            return False
        return True

    def match(self, token_type: str | None = None, lexeme: str | None = None) -> Token | None:
        if self.check(token_type, lexeme):
            token = self.current
            self.pos += 1
            return token
        return None

    def expect(
        self,
        token_type: str | None = None,
        lexeme: str | None = None,
        expected: str | None = None,
    ) -> Token:
        token = self.match(token_type, lexeme)
        if token is not None:
            return token

        if expected is None:
            if token_type is not None and lexeme is not None:
                expected = f"{token_type} '{lexeme}'"
            elif token_type is not None:
                expected = token_type
            elif lexeme is not None:
                expected = f"'{lexeme}'"
            else:
                expected = "допустимая лексема"
        self.error(expected)
        raise AssertionError("unreachable")

    def error(self, expected: str, detail: str | None = None) -> None:
        token = self.current
        message = [
            "Синтаксическая ошибка",
            f"Позиция: токен {token.index}, строка {token.line}, столбец {token.column}",
            f"Найдено: {token.short()}",
            f"Ожидалось: {expected}",
        ]
        if detail:
            message.append(f"Пояснение: {detail}")
        raise ParserError("\n".join(message))

    # program ::= include* using_namespace? function+ EOF
    def parse_program(self) -> ASTNode:
        program = ASTNode("Program")

        while self.check("KEYWORD", "#include"):
            program.add(self.parse_include())

        if self.check("KEYWORD", "using"):
            program.add(self.parse_using_namespace())

        function_count = 0
        while not self.check("EOF", "EOF"):
            program.add(self.parse_function())
            function_count += 1

        if function_count == 0:
            self.error("определение функции")
        self.expect("EOF", "EOF", "конец потока токенов")
        return program

    # include ::= '#include' '<' IDENTIFIER '>'
    def parse_include(self) -> ASTNode:
        self.expect("KEYWORD", "#include", "директива #include")
        self.expect("DELIMITER", "<", "разделитель '<' после #include")
        header = self.expect("IDENTIFIER", expected="имя заголовочного файла")
        self.expect("DELIMITER", ">", "разделитель '>' после имени заголовка")
        return ASTNode("Include", header.lexeme)

    # using_namespace ::= 'using' 'namespace' ('std' | IDENTIFIER) ';'
    def parse_using_namespace(self) -> ASTNode:
        self.expect("KEYWORD", "using", "ключевое слово using")
        self.expect("KEYWORD", "namespace", "ключевое слово namespace")

        if self.check("KEYWORD", "std") or self.check("IDENTIFIER"):
            name = self.current
            self.pos += 1
        else:
            self.error("имя пространства имён")

        self.expect("DELIMITER", ";", "разделитель ';' после using namespace")
        return ASTNode("UsingNamespace", name.lexeme)

    def parse_type(self) -> Token:
        token = self.current
        if token.token_type == "KEYWORD" and token.lexeme in TYPE_WORDS:
            self.pos += 1
            return token
        self.error("тип данных int или bool")
        raise AssertionError("unreachable")

    # function ::= type IDENTIFIER '(' parameters? ')' block
    def parse_function(self) -> ASTNode:
        return_type = self.parse_type()
        name = self.expect("IDENTIFIER", expected="имя функции")
        self.expect("DELIMITER", "(", "открывающая круглая скобка '(' после имени функции")

        parameters = ASTNode("Parameters")
        if not self.check("DELIMITER", ")"):
            parameters = self.parse_parameters()

        self.expect("DELIMITER", ")", "закрывающая круглая скобка ')' после параметров")
        body = self.parse_block()

        node = ASTNode("Function", name.lexeme)
        node.add(ASTNode("ReturnType", return_type.lexeme))
        node.add(parameters)
        node.add(body)
        return node

    # parameters ::= parameter (',' parameter)*
    def parse_parameters(self) -> ASTNode:
        node = ASTNode("Parameters")
        node.add(self.parse_parameter())
        while self.match("DELIMITER", ","):
            node.add(self.parse_parameter())
        return node

    # parameter ::= type IDENTIFIER
    def parse_parameter(self) -> ASTNode:
        type_token = self.parse_type()
        name = self.expect("IDENTIFIER", expected="имя параметра")
        node = ASTNode("Parameter", name.lexeme)
        node.add(ASTNode("Type", type_token.lexeme))
        return node

    # block ::= '{' statement* '}'
    def parse_block(self) -> ASTNode:
        self.expect("DELIMITER", "{", "открывающая фигурная скобка '{'")
        node = ASTNode("Body")

        while not self.check("DELIMITER", "}"):
            if self.check("EOF", "EOF"):
                self.error("закрывающая фигурная скобка '}'", "блок программы не закрыт")
            node.add(self.parse_statement())

        self.expect("DELIMITER", "}", "закрывающая фигурная скобка '}'")
        return node

    def parse_statement(self) -> ASTNode:
        token = self.current

        if token.token_type == "KEYWORD" and token.lexeme in TYPE_WORDS:
            return self.parse_var_decl()
        if self.check("KEYWORD", "return"):
            return self.parse_return()
        if self.check("KEYWORD", "if"):
            return self.parse_if()
        if self.check("KEYWORD", "for"):
            return self.parse_for()
        if self.check("KEYWORD", "while"):
            return self.parse_while()
        if self.check("KEYWORD", "cout"):
            return self.parse_output()

        if self.check("IDENTIFIER"):
            continuation = self.peek().lexeme
            if continuation == "=":
                return self.parse_assignment()
            if continuation == "++":
                return self.parse_increment()
            if continuation == "(":
                return self.parse_call_statement()

        self.error("объявление, оператор, вызов функции или управляющая конструкция")
        raise AssertionError("unreachable")

    # var_decl ::= type declarator (',' declarator)* ';'
    def parse_var_decl(self, consume_semicolon: bool = True) -> ASTNode:
        type_token = self.parse_type()
        node = ASTNode("VarDecl")
        node.add(ASTNode("Type", type_token.lexeme))
        node.add(self.parse_declarator())

        while self.match("DELIMITER", ","):
            node.add(self.parse_declarator())

        if consume_semicolon:
            self.expect("DELIMITER", ";", "разделитель ';' после объявления переменной")
        return node

    # declarator ::= IDENTIFIER ('=' expression)?
    def parse_declarator(self) -> ASTNode:
        name = self.expect("IDENTIFIER", expected="имя переменной")
        variable = ASTNode("Variable", name.lexeme)
        if self.match("OPERATOR", "="):
            initializer = ASTNode("Initializer")
            initializer.add(self.parse_expression())
            variable.add(initializer)
        return variable

    # assignment ::= IDENTIFIER '=' expression ';'
    def parse_assignment(self, consume_semicolon: bool = True) -> ASTNode:
        name = self.expect("IDENTIFIER", expected="левая часть присваивания")
        self.expect("OPERATOR", "=", "оператор присваивания '='")

        node = ASTNode("Assign")
        node.add(ASTNode("Target", name.lexeme))
        value = ASTNode("Value")
        value.add(self.parse_expression())
        node.add(value)

        if consume_semicolon:
            self.expect("DELIMITER", ";", "разделитель ';' после присваивания")
        return node

    # increment ::= IDENTIFIER '++' ';'
    def parse_increment(self, consume_semicolon: bool = True) -> ASTNode:
        name = self.expect("IDENTIFIER", expected="имя изменяемой переменной")
        self.expect("OPERATOR", "++", "оператор постфиксного инкремента '++'")
        if consume_semicolon:
            self.expect("DELIMITER", ";", "разделитель ';' после инкремента")
        return ASTNode("PostfixIncrement", name.lexeme)

    # call_stmt ::= call_expression ';'
    def parse_call_statement(self) -> ASTNode:
        expression = self.parse_call_expression()
        self.expect("DELIMITER", ";", "разделитель ';' после вызова функции")
        expression.kind = "Call"
        return expression

    # return_stmt ::= 'return' expression ';'
    def parse_return(self) -> ASTNode:
        self.expect("KEYWORD", "return", "ключевое слово return")
        node = ASTNode("Return")
        node.add(self.parse_expression())
        self.expect("DELIMITER", ";", "разделитель ';' после return")
        return node

    # if_stmt ::= 'if' '(' expression ')' block ('else' block)?
    def parse_if(self) -> ASTNode:
        self.expect("KEYWORD", "if", "ключевое слово if")
        self.expect("DELIMITER", "(", "открывающая круглая скобка '(' после if")
        condition = ASTNode("Condition")
        condition.add(self.parse_expression())
        self.expect("DELIMITER", ")", "закрывающая круглая скобка ')' после условия if")

        node = ASTNode("If")
        node.add(condition)
        then_branch = ASTNode("Then")
        then_branch.add(self.parse_block())
        node.add(then_branch)

        if self.match("KEYWORD", "else"):
            else_branch = ASTNode("Else")
            else_branch.add(self.parse_block())
            node.add(else_branch)
        return node

    # for_stmt ::= 'for' '(' (var_decl | assignment) ';' expression ';'
    #              (increment | assignment) ')' block
    def parse_for(self) -> ASTNode:
        self.expect("KEYWORD", "for", "ключевое слово for")
        self.expect("DELIMITER", "(", "открывающая круглая скобка '(' после for")

        initialization = ASTNode("Initialization")
        if self.current.token_type == "KEYWORD" and self.current.lexeme in TYPE_WORDS:
            initialization.add(self.parse_var_decl(consume_semicolon=False))
        elif self.check("IDENTIFIER") and self.peek().lexeme == "=":
            initialization.add(self.parse_assignment(consume_semicolon=False))
        else:
            self.error("объявление или присваивание в секции инициализации for")
        self.expect("DELIMITER", ";", "первый разделитель ';' в заголовке for")

        condition = ASTNode("Condition")
        condition.add(self.parse_expression())
        self.expect("DELIMITER", ";", "второй разделитель ';' в заголовке for")

        update = ASTNode("Update")
        if self.check("IDENTIFIER") and self.peek().lexeme == "++":
            update.add(self.parse_increment(consume_semicolon=False))
        elif self.check("IDENTIFIER") and self.peek().lexeme == "=":
            update.add(self.parse_assignment(consume_semicolon=False))
        else:
            self.error("инкремент или присваивание в секции изменения for")

        self.expect("DELIMITER", ")", "закрывающая круглая скобка ')' после заголовка for")

        node = ASTNode("For")
        node.add(initialization)
        node.add(condition)
        node.add(update)
        node.add(self.parse_block())
        return node

    # while_stmt ::= 'while' '(' expression ')' block
    def parse_while(self) -> ASTNode:
        self.expect("KEYWORD", "while", "ключевое слово while")
        self.expect("DELIMITER", "(", "открывающая круглая скобка '(' после while")
        condition = ASTNode("Condition")
        condition.add(self.parse_expression())
        self.expect("DELIMITER", ")", "закрывающая круглая скобка ')' после условия while")

        node = ASTNode("While")
        node.add(condition)
        node.add(self.parse_block())
        return node

    # output ::= 'cout' '<<' output_part ('<<' output_part)* ';'
    def parse_output(self) -> ASTNode:
        self.expect("KEYWORD", "cout", "оператор вывода cout")
        self.expect("OPERATOR", "<<", "оператор вывода '<<'")
        node = ASTNode("Output")
        node.add(self.parse_output_part())

        while self.match("OPERATOR", "<<"):
            node.add(self.parse_output_part())

        self.expect("DELIMITER", ";", "разделитель ';' после cout")
        return node

    def parse_output_part(self) -> ASTNode:
        if self.match("KEYWORD", "endl"):
            return ASTNode("Endl")
        return self.parse_expression()

    # expression ::= primary (binary_operator expression)*
    # Реализовано как приоритетный разбор (precedence climbing).
    def parse_expression(self, min_precedence: int = 1) -> ASTNode:
        left = self.parse_primary()

        while self.current.token_type == "OPERATOR":
            operator = self.current.lexeme
            precedence = BINARY_PRECEDENCE.get(operator)
            if precedence is None or precedence < min_precedence:
                break

            self.pos += 1
            right = self.parse_expression(precedence + 1)
            binary = ASTNode("BinaryExpr", operator)
            binary.add(left)
            binary.add(right)
            left = binary

        return left

    # primary ::= IDENTIFIER | CONSTANT | call | '(' expression ')'
    def parse_primary(self) -> ASTNode:
        if self.match("DELIMITER", "("):
            expression = self.parse_expression()
            self.expect("DELIMITER", ")", "закрывающая круглая скобка ')' в выражении")
            return expression

        if self.check("IDENTIFIER"):
            if self.peek().lexeme == "(":
                return self.parse_call_expression()
            token = self.current
            self.pos += 1
            return ASTNode("Identifier", token.lexeme)

        token = self.current
        constant_kinds = {
            "CONSTANT_INT": "IntLiteral",
            "CONSTANT_STRING": "StringLiteral",
            "CONSTANT_BOOL": "BoolLiteral",
        }
        if token.token_type in constant_kinds:
            self.pos += 1
            return ASTNode(constant_kinds[token.token_type], token.lexeme)

        self.error("идентификатор, константа, вызов функции или выражение в скобках")
        raise AssertionError("unreachable")

    # call ::= IDENTIFIER '(' arguments? ')'
    def parse_call_expression(self) -> ASTNode:
        name = self.expect("IDENTIFIER", expected="имя вызываемой функции")
        self.expect("DELIMITER", "(", "открывающая круглая скобка '(' в вызове функции")
        node = ASTNode("CallExpr", name.lexeme)
        arguments = ASTNode("Arguments")

        if not self.check("DELIMITER", ")"):
            arguments.add(self.parse_expression())
            while self.match("DELIMITER", ","):
                arguments.add(self.parse_expression())

        self.expect("DELIMITER", ")", "закрывающая круглая скобка ')' после аргументов")
        node.add(arguments)
        return node


def analyze_source(source: str) -> tuple[list[tuple[str, str]], ASTNode]:
    """Запускает лексический и синтаксический анализ исходного текста."""

    raw_tokens = lexical_analyze(source)
    validate(raw_tokens)
    tokens = add_token_positions(source, raw_tokens)
    ast = Parser(tokens).parse_program()
    return raw_tokens, ast


def resolve_input_path(path_argument: str | None) -> Path:
    if path_argument:
        path = Path(path_argument)
        if not path.exists():
            raise FileNotFoundError(f"Исходный файл не найден: {path}")
        return path

    candidates = (
        Path("lab2/clean_test.cpp"),
        Path("clean_test.cpp"),
        Path("clean_test(1).cpp"),
    )
    for path in candidates:
        if path.exists():
            return path
    raise FileNotFoundError(
        "Не найден входной файл. Передайте путь аргументом, например: "
        "python syntax_analyzer_lab3.py lab2/clean_test.cpp"
    )


def build_argument_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Синтаксический анализатор тестовой программы из ЛР № 1"
    )
    parser.add_argument(
        "source",
        nargs="?",
        help="путь к очищенному C++-файлу (по умолчанию ищется lab2/clean_test.cpp)",
    )
    parser.add_argument(
        "--ast-output",
        metavar="FILE",
        help="дополнительно сохранить текстовое представление AST в файл",
    )
    return parser


def main(argv: Iterable[str] | None = None) -> int:
    args = build_argument_parser().parse_args(argv)

    try:
        source_path = resolve_input_path(args.source)
        source = read_source_file(str(source_path))
        if not source.strip():
            print("Ошибка: входной файл пуст.")
            return 1

        raw_tokens, ast = analyze_source(source)
        tree = ast.to_tree()

        print(f"Входной файл: {source_path}")
        print(f"Получено токенов из lexer_lab2.py: {len(raw_tokens)}")
        print("Синтаксический анализ завершён успешно.\n")
        print("АБСТРАКТНОЕ СИНТАКСИЧЕСКОЕ ДЕРЕВО")
        print(tree)

        if args.ast_output:
            output_path = Path(args.ast_output)
            output_path.write_text(tree + "\n", encoding="utf-8")
            print(f"\nAST сохранено в файл: {output_path}")
        return 0

    except (ParserError, FileNotFoundError) as error:
        print(error)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
