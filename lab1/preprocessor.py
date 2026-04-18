import re

tabs_spaces_pattern = r"^[ \t]+|[ \t]+$"
one_line_comments_pattern = r"//[^\n]*"
many_lines_comments_pattern = r"/\*.*?\*/"
extra_spaces_pattern = r"[ \t]{2,}"
invalid_chars_pattern = r"[^\t\n\r -~А-Яа-яЁё]"

with open("lab1/test.cpp", "r", encoding="utf-8") as f:
    content = f.read()

balance = 0
last_open = None

for match in re.finditer(r"/\*|\*/", content):
    if match.group() == "/*":
        if balance == 0:
            last_open = match.start()
        balance += 1
    else:
        balance -= 1
        if balance < 0:
            print(f"Ошибка: лишнее закрытие */ в индексе {match.start()}")
            raise SystemExit(1)

if balance > 0:
    print(f"Ошибка: незакрытый /* начиная с индекса {last_open}")
    raise SystemExit(1)

invalid_char = re.search(invalid_chars_pattern, content)
if invalid_char:
    print(
        f"Ошибка: найден недопустимый символ в индексе {invalid_char.start()}: {repr(invalid_char.group())}"
    )
    raise SystemExit(1)

content = re.sub(many_lines_comments_pattern, "", content, flags=re.DOTALL)
content = re.sub(one_line_comments_pattern, "", content)
content = re.sub(tabs_spaces_pattern, "", content, flags=re.MULTILINE)
content = re.sub(extra_spaces_pattern, " ", content)
content = re.sub(r"^\n+|\n+\Z", "", content, flags=re.MULTILINE)

if not content:
    print("Ошибка: файл пуст.")
    raise SystemExit(1)

print(content)
print("\nКод успешно очищен, ошибок не найдено.")

with open("lab1/clean_test.cpp", "w", encoding="utf-8") as f:
    f.write(content)
    print("Очищенный код сохранён в файл clean_test.cpp")
