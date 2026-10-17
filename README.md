# it-salary-ru

Предсказание зарплаты IT-специалиста по тексту вакансии с hh.ru.

## Что внутри
- **Парсер** вакансий hh.ru (Python)
- **Модель** предсказания зарплаты (CatBoost) с объяснением через SHAP
- **API** на FastAPI и **шлюз** на Go
- **Веб-интерфейс** на Vue: «Сколько ты стоишь?»

## Статус
🚧 В разработке

## Запуск
```bash
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
```
