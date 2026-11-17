# SIPL Language Toolkit

[![CI](https://github.com/ddashukko/sipl-toolkit/actions/workflows/ci.yml/badge.svg)](https://github.com/ddashukko/sipl-toolkit/actions/workflows/ci.yml)

Інструменти для навчальної мови SIPL (SImple Programming Language) з курсу «Теорія програмування»:
формальна граматика, парсер із типізованим AST, інтерпретатор із подієвою моделлю, CLI з JSON-режимом,
conformance suite та візуалізація дерева виводу й AST.

```
begin
  R := 1;
  while Y > 0 do
  begin
    R := R * X;
    Y := Y - 1
  end
end
```

```
$ sipl run examples/valid/power.sipl -s X=2,Y=10
Кінцевий стан: {R = 1024, X = 2, Y = 0}
Кроків: 32
```

## Обрані завдання

| ID      | Завдання                                       | Бали | Де реалізовано                                                    |
| ------- | ---------------------------------------------- | ---- | ----------------------------------------------------------------- |
| CORE-01 | Формальна специфікація SIPL                    | 0.5  | `src/sipl/grammar/sipl.lark`, `docs/grammar.md`, `examples/`      |
| CORE-02 | Парсер і типізоване AST зі SourceSpan          | 1.5  | `src/sipl/parser.py`, `ast.py`, `parse_tree.py`, `diagnostics.py` |
| CORE-03 | Інтерпретатор                                  | 2.0  | `src/sipl/interpreter/machine.py`                                 |
| CORE-04 | Подієва модель виконання і trace               | 1.0  | `src/sipl/interpreter/events.py`                                  |
| CORE-05 | CLI з JSON-режимом                             | 1.0  | `src/sipl/cli.py`, `docs/cli.md`, `docs/json-schema.md`           |
| CORE-06 | Conformance suite                              | 1.0  | `conformance/`                                                    |
| VIS-01  | Візуалізація дерева виводу                     | 1.5  | `src/sipl/visualization/`                                         |
| VIS-02  | Візуалізація AST і порівняння Parse Tree ↔ AST | 1.0  | `src/sipl/visualization/compare.py`                               |
| REL-01  | CI                                             | 0.5  | `.github/workflows/ci.yml`                                        |
| REL-02  | GitHub Releases, SemVer, CHANGELOG             | 0.5  | `.github/workflows/release.yml`, `CHANGELOG.md`                   |

Заявлено 10.5 бала; підсумкова оцінка обмежена 10.

## Встановлення

Потрібен Python 3.10 або новіший.

```
git clone https://github.com/ddashukko/sipl-toolkit.git
cd sipl-toolkit
python -m venv .venv
```

Активувати середовище: `.venv\Scripts\activate` у Windows або `source .venv/bin/activate` у Linux/macOS. Далі:

```
pip install -e ".[dev]"
sipl --version
```

Без інструментів розробки достатньо `pip install .`. Готовий пакет також можна взяти
з артефактів релізу: `pip install sipl_toolkit-0.4.0-py3-none-any.whl`.

## Швидкий старт

```
sipl check   examples/valid/power.sipl                 # синтаксична перевірка
sipl parse   examples/valid/power.sipl                 # AST
sipl run     examples/valid/power.sipl -s X=2 -s Y=10  # кінцевий стан
sipl trace   examples/valid/power.sipl -s X=2,Y=2      # події виконання
sipl tree    examples/valid/power.sipl                 # дерево виводу текстом
sipl tree    examples/valid/power.sipl --format svg -o tree.svg
sipl tree    examples/valid/power.sipl --kind ast --format dot -o ast.dot
sipl compare examples/valid/power.sipl -o compare.html # Parse Tree ↔ AST у браузері
```

Кожна з команд `parse`, `check`, `run`, `trace` має прапорець `--json`. Замість файлу можна
передати `-` і подати програму через stdin.

Помилки прив'язані до місця в коді й пояснюють, що не так:

```
$ sipl check examples/invalid/trailing_semicolon.sipl
examples/invalid/trailing_semicolon.sipl:3:1: error[E002]: Неочікувана лексема 'end'; очікувалось: 'begin', 'if', 'skip', 'while', змінна
   3 | end
     | ^^^
  підказка: ';' розділяє оператори, а не завершує їх: приберіть ';' перед 'end'
```

| Код завершення | Значення                                  |
| -------------- | ----------------------------------------- |
| 0              | успіх                                     |
| 1              | синтаксична помилка                       |
| 2              | неправильний виклик або файл не читається |
| 3              | помилка виконання (змінна без значення)   |
| 4              | перевищено ліміт кроків                   |

Повний опис команд — у [docs/cli.md](docs/cli.md), формат JSON — у [docs/json-schema.md](docs/json-schema.md).

## Використання як бібліотеки

```python
from sipl import parse, run, trace

program = parse("begin F := 1; while N > 1 do begin F := F * N; N := N - 1 end end")
result = run(program, {"N": 5})
print(result.status, result.state)  # ok {'N': 1, 'F': 120}

for event in trace(program, {"N": 2}):  # події для debugger / visualizer
    print(event.to_dict())
```

## Мова

Граматика відповідає БНФ практикуму: `begin … end`, присвоювання `:=`, композиція `;`,
`if … then … else …`, `while … do …`, `skip`; вирази з `+`, `-`, `*`; умови з `=`, `>`, `∨`, `¬`.
Операції `∨` та `¬` можна писати як `or` та `not`. Усі деталі, пріоритети та відмінності від
БНФ описано в [docs/grammar.md](docs/grammar.md).

## Структура

```
src/sipl/
├── grammar/sipl.lark    формальна граматика (єдине джерело синтаксису)
├── parser.py            текст -> дерево виводу -> AST, діагностика
├── parse_tree.py        модель дерева виводу
├── ast.py               вузли AST і SourceSpan
├── diagnostics.py       повідомлення про помилки
├── interpreter/         виконання, стан, події, trace
├── visualization/       text / JSON / DOT / SVG / HTML
└── cli.py               командний рядок
examples/valid/          16 коректних програм
examples/invalid/        18 некоректних програм
conformance/             незалежний від реалізації набір тестів
tests/                   pytest
docs/                    граматика, CLI, JSON-контракт, архітектура
```

Як дані проходять між шарами — у [docs/architecture.md](docs/architecture.md).

## Тести

```
pytest --cov                   # модульні та інтеграційні тести з покриттям
python conformance/run.py -v   # conformance suite
ruff check . && ruff format --check . && mypy
```

Покриття ядра тестами — близько 97 %; CI вимагає не менше 80 %.

## Обмеження

- Парсер повідомляє про першу синтаксичну помилку й зупиняється; відновлення після помилок немає.
- Числа — цілі довільної величини; ділення, `<`, `∧` та інших операцій поза БНФ немає.
- Нескінченні цикли не розпізнаються: виконання просто зупиняється після ліміту кроків
  (типово 10 000, параметр `--max-steps`).
- Дерева обходяться рекурсивно; CLI піднімає ліміт рекурсії Python, тому практична межа —
  тисячі рівнів вкладеності.
- SVG-розкладка проста: для програм на сотні рядків малюнок виходить дуже широким.
- Перевірено на Windows 11 та Linux, Python 3.10–3.13

## Ліцензія

MIT, див. [LICENSE](LICENSE).
