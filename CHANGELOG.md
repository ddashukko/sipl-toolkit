# Changelog

Формат — [Keep a Changelog](https://keepachangelog.com/uk/1.1.0/), версії — [SemVer](https://semver.org/lang/uk/).
Номер 0.4 відповідає етапу «Візуалізація» рекомендованого циклу версій спільного проєкту SIPL.

## [0.5.0] - 2026-11-19

### Змінено

- Дерево виводу (`sipl tree`, `sipl compare`) тепер у нотації практикуму: метазмінні `<програма>`,
  `<оператор>`, `<вираз>`, `<умова>`, `<змінна>`, `<число>`, листки — термінали; у SVG і DOT вузли
  без рамок, ребра — стрілки.
- Композиція `;` вкладається праворуч: `S1 ; S2 ; S3` = `S1 ; (S2 ; S3)`, як у практикумі.
  У JSON-поданні AST `Seq` відповідно змінив форму (несумісна зміна для `schema_version` 1).
- `docs/grammar.md`: таблиця БНФ практикуму з назвами правил NP1, NS1–NS6, NA1–NA6, NB1–NB5.

## [0.4.0] - 2026-11-16

Перший публічний реліз.

### Додано

- Граматика SIPL у форматі Lark та опис лексики (`docs/grammar.md`); 16 коректних і 18 некоректних прикладів.
- Парсер: дерево виводу `ParseNode` і типізоване AST зі `SourceSpan` у кожному вузлі.
- Діагностика синтаксичних помилок із кодом, позицією, списком очікуваних лексем і підказкою.
- Інтерпретатор: присвоювання, композиція, `if`, `while`, `begin/end`, `skip`; ліміт кроків;
  діагностика читання змінної без значення.
- Подієва модель виконання: `before_statement`, `after_statement`, `variable_changed`,
  `condition_evaluated`, `finished`.
- CLI: `check`, `parse`, `run`, `trace`, `tree`, `compare`; JSON-режим зі `schema_version` 1; стабільні коди завершення.
- Візуалізація дерева виводу та AST: text, JSON, DOT, SVG; інтерактивна HTML-сторінка порівняння.
- Conformance suite: 44 тести й runner, незалежний від реалізації.
- CI: ruff, mypy, pytest із порогом покриття 80 %, conformance suite, збірка пакета.

[0.5.0]: https://github.com/ddashukko/sipl-toolkit/releases/tag/v0.5.0
[0.4.0]: https://github.com/ddashukko/sipl-toolkit/releases/tag/v0.4.0
