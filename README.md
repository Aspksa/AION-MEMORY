# AION MEMORY v0.1.0

Локальный архив переписок ИИ и визуальный граф знаний.

## Реализовано
- FastAPI + SQLite WAL: чаты, сообщения, поиск, удаление, статистика
- React + TypeScript + Vite: обзор, чат, поиск, память, граф React Flow, ECharts
- Факты со ссылками на сообщения, статус candidate
- Подключение совместимого с OpenAI HTTPS API через локальный .env
- Windows Start.bat, npm.cmd, без Docker

## Запуск
Установить Python 3.11+ и Node.js 20+. Скопировать .env.example в .env. Запустить Start.bat. Интерфейс: http://127.0.0.1:5173; документация API: http://127.0.0.1:8000/docs.

## Ещё не реализовано
MemOS, Mem0, Graphiti, Qdrant, автоматическое извлечение фактов, агенты, резервное копирование, полноценная конфигурация моделей и 3D-граф. Разделы меню для будущих модулей являются заглушками. Хранилище сейчас SQLite, не PostgreSQL.

## Безопасность
Не добавлять .env, API-ключи, историю чатов и базу в публичный GitHub. Сервер рассчитан только на локальное использование и привязан к 127.0.0.1. Для сетевого доступа необходимы авторизация, TLS и ограничения запросов.

## Проверки
`python -m pytest backend/tests`; `cd frontend && npm.cmd run build`. Проверки ещё не запускались в CI.

## Automatic knowledge extraction (experimental)
Set `AION_AUTO_EXTRACT=1` in .env and start the separate worker with `python -m backend.worker`. New user messages are queued in SQLite and processed by the configured HTTPS model. Extracted facts remain **candidate** until manually confirmed through PATCH /api/memories/{id}. Queue status: GET /api/jobs; retry failed jobs: POST /api/jobs/{id}/retry. This worker is single-process and currently has no crash-recovery lease for interrupted running jobs.

## CI
GitHub Actions checks backend pytest and frontend TypeScript/Vite build. Do not assume green until workflows complete.
