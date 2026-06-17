import re
import sys

def read_source_file(filename):
    try:
        with open(filename, "r", encoding="utf-8") as f:
            return f.read()
    except UnicodeDecodeError:
        with open(filename, "r", encoding="cp1251") as f:
            return f.read()

KEYWORDS = {
    "#include": "Директива подключения заголовочного файла",
    "using": "Подключение пространства имён",
    "namespace": "Объявление пространства имён",
    "std": "Стандартное пространство имён C++",
    "int": "Целочисленный тип данных",
    "bool": "Логический тип данных",
    "return": "Возврат значения из функции",
    "if": "Условный оператор",
    "else": "Альтернативная ветвь условного оператора",
    "for": "Оператор цикла с параметром",
    "while": "Оператор цикла с предусловием",
    "cout": "Стандартный поток вывода",
    "endl": "Перевод строки в потоке вывода"
}

# Идентификаторы, которые встречаются в test.cpp
IDENTIFIERS = {
    "iostream": "Имя подключаемого заголовочного файла",
    "multiply": "Имя функции умножения",
    "main": "Главная функция программы",
    "x": "Первый параметр функции multiply",
    "y": "Второй параметр функции multiply",
    "a": "Первая целочисленная переменная",
    "b": "Вторая целочисленная переменная",
    "sum": "Переменная для хранения суммы",
    "diff": "Переменная для хранения разности",
    "product": "Переменная для хранения произведения",
    "flag": "Логическая переменная-флаг",
    "i": "Счётчик цикла for",
    "counter": "Счётчик цикла while"
}

# Булевы константы
BOOL_CONSTANTS = {
    "false": "Логическая ложь"
}

# Операторы, которые встречаются в test.cpp
OPERATORS = {
    "<<": "Оператор вывода в поток",
    "&&": "Логический оператор И",
    "!=": "Оператор проверки неравенства",
    "++": "Оператор инкремента",
    "=": "Оператор присваивания",
    "+": "Оператор сложения",
    "-": "Оператор вычитания",
    "*": "Оператор умножения",
    ">": "Оператор сравнения больше",
    "<": "Оператор сравнения меньше"
}

# Разделители, которые встречаются в test.cpp
DELIMITERS = {
    "(": "Открывающая круглая скобка",
    ")": "Закрывающая круглая скобка",
    "{": "Открывающая фигурная скобка",
    "}": "Закрывающая фигурная скобка",
    ",": "Разделитель параметров или аргументов",
    ";": "Конец оператора",
    "<": "Начало имени заголовочного файла в директиве include",
    ">": "Конец имени заголовочного файла в директиве include"
}

TOKEN_TABLE_NAMES = {
    "KEYWORD": "Ключевые слова",
    "IDENTIFIER": "Идентификаторы",
    "CONSTANT_INT": "Целочисленные константы",
    "CONSTANT_STRING": "Строковые константы",
    "CONSTANT_BOOL": "Булевы константы",
    "OPERATOR": "Операторы",
    "DELIMITER": "Разделители"
}


# Функция для вывода ошибки
def lexical_error(message, lexeme=""):
    print("Лексическая ошибка:", message)
    if lexeme:
        print("Проблемная лексема:", lexeme)
    raise SystemExit(1)


# Получение описания лексемы
def get_lexeme_description(token_type, lexeme):
    if token_type == "KEYWORD":
        return KEYWORDS.get(lexeme, "Ключевое слово")
    if token_type == "IDENTIFIER":
        return IDENTIFIERS.get(lexeme, "Пользовательский идентификатор")
    if token_type == "CONSTANT_INT":
        return "Целочисленная константа"
    if token_type == "CONSTANT_STRING":
        return "Строковая константа"
    if token_type == "CONSTANT_BOOL":
        return BOOL_CONSTANTS.get(lexeme, "Булева константа")
    if token_type == "OPERATOR":
        return OPERATORS.get(lexeme, "Оператор")
    if token_type == "DELIMITER":
        return DELIMITERS.get(lexeme, "Разделитель")
    return "Лексема"


# Определение типа уже выделенной лексемы
def get_token_type(lexeme):
    if lexeme in KEYWORDS:
        return "KEYWORD"
    if lexeme in BOOL_CONSTANTS:
        return "CONSTANT_BOOL"
    if lexeme in OPERATORS:
        return "OPERATOR"
    if lexeme in DELIMITERS:
        return "DELIMITER"
    if re.fullmatch(r'\d+', lexeme):
        return "CONSTANT_INT"
    if re.fullmatch(r'"([^"\\\n]|\\.)*"', lexeme):
        return "CONSTANT_STRING"
    if lexeme in IDENTIFIERS:
        return "IDENTIFIER"
    lexical_error("неизвестная лексема", lexeme)


def validate(tokens):
    for i in range(len(tokens)):
        token_type, lexeme = tokens[i]

        if token_type not in {"IDENTIFIER", "CONSTANT_INT", "CONSTANT_STRING", "CONSTANT_BOOL"}:
            continue

        prev_token = tokens[i - 1][0] if i > 0 else None
        prev_lexeme = tokens[i - 1][1] if i > 0 else None
        next_token = tokens[i + 1][0] if i + 1 < len(tokens) else None
        next_lexeme = tokens[i + 1][1] if i + 1 < len(tokens) else None

        if prev_token in {"IDENTIFIER", "CONSTANT_INT", "CONSTANT_STRING", "CONSTANT_BOOL"}:
            lexical_error("две лексемы подряд без оператора или разделителя", lexeme)

        if prev_lexeme in {":", "{", "}", ";"} and (
            next_lexeme in {"return", "for", "while", "if", "else", ";", "}", "{"}
            or next_token in {"KEYWORD", "DELIMITER"}
        ):
            if not (token_type == "IDENTIFIER" and next_lexeme == "("):
                lexical_error("лишняя лексема", lexeme)


# Лексический анализ
def lexical_analyze(text):
    tokens = []
    i = 0
    n = len(text)

    while i < n:
        ch = text[i]

        # Пропускаем пробельные символы
        if ch.isspace():
            i += 1
            continue

        # Пропускаем однострочные комментарии
        if text.startswith("//", i):
            i += 2
            while i < n and text[i] != "\n":
                i += 1
            continue

        # Пропускаем многострочные комментарии
        if text.startswith("/*", i):
            i += 2
            while i + 1 < n and text[i:i + 2] != "*/":
                i += 1
            if i + 1 >= n:
                lexical_error("незакрытый многострочный комментарий", "/*")
            i += 2
            continue

        # Обработка #include
        if text.startswith("#include", i):
            tokens.append(("KEYWORD", "#include"))
            i += len("#include")

            # Пропускаем пробелы после #include
            while i < n and text[i].isspace():
                i += 1

            # Ожидаем <
            if i >= n or text[i] != '<':
                lexical_error("после #include ожидается символ <", "#include")

            tokens.append(("DELIMITER", "<"))
            i += 1

            # Читаем имя заголовка до >
            start = i
            while i < n and text[i] != '>':
                if text[i].isspace():
                    lexical_error("в имени заголовочного файла не должно быть пробелов", text[start:i])
                i += 1

            if i >= n:
                lexical_error("после #include не найден закрывающий символ >", text[start:])

            header_name = text[start:i]
            if header_name == "":
                lexical_error("пустое имя заголовочного файла", "<>")

            tokens.append(("IDENTIFIER", header_name))
            tokens.append(("DELIMITER", ">"))
            i += 1
            continue

        # Строковые константы
        if ch == '"':
            start = i
            i += 1
            escaped = False

            while i < n:
                if text[i] == '\n' and not escaped:
                    lexical_error("незакрытый строковый литерал", text[start:i])

                if text[i] == '"' and not escaped:
                    i += 1
                    lexeme = text[start:i]
                    tokens.append(("CONSTANT_STRING", lexeme))
                    break

                if text[i] == "\\" and not escaped:
                    escaped = True
                else:
                    escaped = False

                i += 1
            else:
                lexical_error("незакрытый строковый литерал", text[start:])

            continue

        # Двухсимвольные операторы
        if i + 1 < n:
            two = text[i:i + 2]
            if two in OPERATORS:
                tokens.append(("OPERATOR", two))
                i += 2
                continue

        # Разделители
        if ch in DELIMITERS and ch not in OPERATORS:
            tokens.append(("DELIMITER", ch))
            i += 1
            continue

        # Односимвольные операторы
        if ch in OPERATORS:
            tokens.append(("OPERATOR", ch))
            i += 1
            continue

        # Числа
        if ch.isdigit():
            start = i
            while i < n and (text[i].isdigit() or text[i] == '.' or text[i].isalpha() or text[i] == '_'):
                i += 1

            lexeme = text[start:i]

            # Ошибка: две точки и более
            if lexeme.count('.') > 1:
                lexical_error("некорректно оформленное число: больше одной точки", lexeme)

            # Ошибка: число заканчивается точкой
            if lexeme.endswith('.'):
                lexical_error("некорректно оформленное число: отсутствует дробная часть", lexeme)

            # Ошибка: буквы в числе или идентификатор начинается с цифры
            if re.search(r'[A-Za-zА-Яа-я_]', lexeme):
                lexical_error("идентификатор начинается с цифры или число содержит буквы", lexeme)

            token_type = get_token_type(lexeme)
            tokens.append((token_type, lexeme))
            continue

        # Идентификаторы и ключевые слова
        if ch.isalpha() or ch == '_':
            start = i
            while i < n and (text[i].isalnum() or text[i] == '_'):
                i += 1

            lexeme = text[start:i]
            token_type = get_token_type(lexeme)
            tokens.append((token_type, lexeme))
            continue

        # Если символ похож на оператор, но его нет в таблице
        if ch in "!|&=+-*/%<>":
            lexical_error("неизвестный оператор", ch)

        lexical_error("недопустимый символ", ch)

    return tokens


# Формирование таблиц лексем с описаниями
def build_lexeme_tables(tokens):
    tables = {token_type: [] for token_type in TOKEN_TABLE_NAMES}

    for token_type, lexeme in tokens:
        if not any(row[0] == lexeme for row in tables[token_type]):
            description = get_lexeme_description(token_type, lexeme)
            tables[token_type].append((lexeme, description))

    return tables


# Табличный вывод всех найденных лексем с описаниями
def print_lexeme_tables(tokens):
    tables = build_lexeme_tables(tokens)

    print("ТАБЛИЦЫ ЛЕКСЕМ")
    for token_type, title in TOKEN_TABLE_NAMES.items():
        print()
        print(title)
        print("id".ljust(5) + "| Лексема".ljust(22) + "| Описание")
        print("-" * 5 + "+" + "-" * 22 + "+" + "-" * 55)

        if not tables[token_type]:
            print("-".ljust(5) + "| " + "-".ljust(20) + "| В test.cpp не используется")
            continue

        for number, (lexeme, description) in enumerate(tables[token_type], 1):
            print(str(number).ljust(5) + "| " + lexeme.ljust(20) + "| " + description)


# Запуск программы
filename = "lab3/clean_test.cpp"
content = read_source_file(filename)

if content.strip() == "":
    print("Ошибка: входной файл пуст.")
    raise SystemExit(1)

tokens = lexical_analyze(content)
validate(tokens)

print_lexeme_tables(tokens)

# Табличный вывод последовательности токенов
print()
print("ПОСЛЕДОВАТЕЛЬНОСТЬ ТОКЕНОВ")
print("Лексема".ljust(21) + "| Тип")
print("-" * 21 + "+" + "-" * 22)

for token_type, lexeme in tokens:
    print(lexeme.ljust(21) + "| " + token_type)

print()
print([(token_type, lexeme) for token_type, lexeme in tokens])
print()
print(f"Лексический анализ завершён успешно. Обнаружено {len(tokens)} токенов. Ошибок не найдено.")
