# JSON-контракт

Усе, що описано тут, — стабільний інтерфейс для інтеграцій (IDE, debugger, web playground,
conformance suite). Поточна версія: `schema_version` = **1**. Нові поля можуть додаватися без зміни
версії; вилучення чи зміна змісту наявного поля означає нову версію.

## Конверт

Кожна команда з `--json` друкує один об'єкт:

```json
{
  "schema_version": 1,
  "command": "run",
  "ok": true,
  "diagnostics": [],
  "...": "поля команди"
}
```

| Команда | Додаткові поля |
| --- | --- |
| `check` | — |
| `parse` | `ast` (лише якщо `ok`) |
| `run` | `status`, `steps`, `initial_state`, `final_state` |
| `trace` | те саме, що `run`, і `events` |
| `tree --format json` | `kind`, `tree` |

У разі синтаксичної помилки будь-яка команда повертає лише конверт з `ok: false` і діагностикою.

## Позиція: `span`

```json
{"start": {"line": 3, "column": 9, "offset": 26}, "end": {"line": 3, "column": 14, "offset": 31}}
```

`line` і `column` рахуються з 1, `offset` — з 0 у символах Unicode; кінець не включається.

## Діагностика

```json
{
  "code": "E002",
  "kind": "syntax",
  "severity": "error",
  "message": "Неочікувана лексема 'end'; очікувалось: ...",
  "hint": "';' розділяє оператори, а не завершує їх: приберіть ';' перед 'end'",
  "span": {"start": {"...": 0}, "end": {"...": 0}}
}
```

| Код | `kind` | Зміст |
| --- | --- | --- |
| E001 | `syntax` | неочікуваний символ |
| E002 | `syntax` | неочікувана лексема |
| E003 | `syntax` | неочікуваний кінець програми |
| E101 | `runtime` | змінна не має значення в поточному стані |
| E102 | `step_limit` | перевищено ліміт кроків |

Текст `message` і `hint` призначений для людини й може змінюватись; програми мають спиратися на `code`,
`kind` і `span`. `hint` може бути `null`.

## AST

Кожен вузол — об'єкт із полем `type`, своїми полями та `span`.

| `type` | Поля |
| --- | --- |
| `Program` | `body`: оператор |
| `Assign` | `target`: `Var`, `value`: вираз |
| `Seq` | `first`, `second`: оператори |
| `If` | `cond`: умова, `then_branch`, `else_branch`: оператори |
| `While` | `cond`: умова, `body`: оператор |
| `Block` | `body`: оператор |
| `Skip` | — |
| `Num` | `value`: ціле |
| `Var` | `name`: рядок |
| `BinOp` | `op`: `"+"`, `"-"` або `"*"`; `left`, `right`: вирази |
| `Compare` | `op`: `"="` або `">"`; `left`, `right`: вирази |
| `Or` | `left`, `right`: умови |
| `Not` | `operand`: умова |

`Seq` вкладається праворуч: `A; B; C` — це `Seq(A, Seq(B, C))`. Дужки окремих вузлів не утворюють.

## Виконання

| Поле | Зміст |
| --- | --- |
| `status` | `ok`, `runtime_error` або `step_limit` |
| `steps` | кількість виконаних кроків |
| `initial_state` | початковий стан: об'єкт «змінна → ціле» |
| `final_state` | стан після завершення або на момент зупинки |

## Події (`trace`)

`events` — масив у порядку виникнення. Остання подія завжди `finished`, і вона одна.

| `event` | Поля | Коли виникає |
| --- | --- | --- |
| `before_statement` | `step`, `statement`, `span` | перед оператором |
| `variable_changed` | `step`, `name`, `old`, `new`, `span` | після присвоювання; `old` = `null`, якщо значення не було |
| `condition_evaluated` | `step`, `statement`, `value`, `span` | після перевірки умови `If` або `While` |
| `after_statement` | `step`, `statement`, `span`, `state` | після оператора; `state` — знімок стану |
| `finished` | `status`, `steps`, `state`, `diagnostic` | наприкінці; `diagnostic` = `null` за успіху |

`statement` — тип вузла AST: `Assign`, `If`, `While`, `Block` або `Skip`. Для `Seq` подій немає:
композиція лише задає порядок. `before_statement` і `after_statement` завжди парні та правильно
вкладені, якщо виконання завершилось успішно.

## Дерево (`tree --format json`)

`kind` — `parse` або `ast`. `tree` — кореневий вузол:

| Поле | Зміст |
| --- | --- |
| `id` | унікальний ідентифікатор у межах дерева (`p0`, `p1`, … або `a0`, `a1`, …) |
| `label` | короткий підпис |
| `title` | повний підпис: `<оператор>`, `R`, `BinOp *` |
| `category` | `rule` (метазмінна `<оператор>` тощо), `token` (термінал) — дерево виводу; `stmt`, `expr`, `cond` — AST |
| `span` | позиція у вихідному тексті |
| `source` | відповідний фрагмент вихідного тексту |
| `children` | дочірні вузли зліва направо |
