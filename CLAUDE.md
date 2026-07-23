# sanctionsai.dev — граблі та правила

## Деплой
- Fly.io, app = `agentmail-api`: `flyctl deploy` (без нових secrets)
- **fly.toml: autostop=suspend — критичний фікс, який РЕВЕРТИТЬСЯ, якщо деплоїти зі старим fly.toml.** Перед деплоєм перевір, що suspend на місці

## Критичні граблі
- api.py = 836KB, всі manifests віддаються inline з нього — НІЯКОЇ хірургії api.py; статичний контент (glossary /learn/) — окремими файлами під served-префіксом
- Compliance-контент: тільки VETTED verbatim визначення + disclaimers; verbatim gate обовʼязковий, нічого не вигадувати
- Dashboard фільтрує verify_* пінги; реальних відвідувачів історично ~0 — не інтерпретуй пінги як трафік
- Owner-задача (не робити самому): ротація ключів sanctionsai
- api.py.bak файли в репо — бекапи, не видаляти
