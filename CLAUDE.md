# sanctionsai.dev — граблі та правила

## Деплой
- Fly.io, app = `agentmail-api`: `flyctl deploy` (без нових secrets)
- **fly.toml: autostop=suspend — критичний фікс, який РЕВЕРТНЕТЬСЯ, якщо деплоїти зі старим fly.toml.** Перед деплоєм перевір, що suspend на місці

## Критичні граблі
- api.py = 836KB, всі manifests віддаються inline з нього — НІЯКОЇ хірургії api.py; статичний контент (glossary /learn/) — окремими файлами під served-префіксом
- Compliance-контент: тільки VETTED verbatim визначення + disclaimers; verbatim gate обовʼязковий, нічого не вигадувати
- Dashboard фільтрує verify_* пінги; реальних відвідувачів історично ~0 — не інтерпретуй пінги як трафік
- Owner-задача (не робити самому): ротація ключів sanctionsai
- api.py.bak файли в репо — бекапи, не видаляти

## Нові роути (DotCom Secrets audit 2026-07-26)
- `/playbook.pdf` — лід-магніт (PDF, генерується `scripts/build_playbook.py`). `/start` обіцяв його з launch; welcome-лист тепер його доставляє.
- `/checkout/dev/bump` — order-bump interstitial (Ch14). **МАЄ матчиситись ДО префікс-роуту `/checkout/`**, інакше префікс зловить `dev/bump` як план і 500не на відсутньому STRIPE ключі.
- `/upgrade` — upsell Dev→Pro (Ch15), лінкається з post-purchase листа.
- Tripwire `/tripwire` — CTA тепер env-driven: `STRIPE_PAYMENT_LINK_TRIPWIRE` → реальна Stripe кнопка, інакше робочий fallback (playbook + ручний invoice).
- `/subscribe` більше не бреше `email_sent:true` — повертає реальний результат + `email_configured`.
- Owner-only (див. `OWNER_ACTIONS_DOTCOM_2026-07-26.md`): `RESEND_API_KEY`, `STRIPE_PAYMENT_LINK_TRIPWIRE`, `STRIPE_PRICE_BUMP_AUDIT`.

