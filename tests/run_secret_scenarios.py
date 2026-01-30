# tests/run_secret_scenarios.py
"""
Скрипт для прогона секретных сценариев.
Создает JSON-логи для каждого сценария как требуется в задании.
"""

import asyncio
import json
import os
import sys
from datetime import datetime
from pathlib import Path

# Добавляем корневую директорию в путь
sys.path.append(str(Path(__file__).parent.parent))

from src.core.coordinator import InterviewCoordinator
from src.utils.logger import setup_logging


# Секретные сценарии из задания
SECRET_SCENARIOS = [
    {
        "name": "Сценарий 1: Junior Backend Developer",
        "context": {
            "name": "Алекс",
            "position": "Backend Developer",
            "grade": "Junior",
            "experience": "Пет-проекты на Django, немного SQL",
            "technologies": ["Python", "Django", "SQL", "Git"]
        },
        "dialogue": [
            "Привет. Я Алекс, претендую на позицию Junior Backend Developer. Знаю Python, SQL и Git.",
            "Django - это фреймворк для веб-разработки на Python. Он использует паттерн MVT (Model-View-Template) и включает ORM для работы с базами данных.",
            "Честно говоря, я читал на Хабре, что в Python 4.0 циклы for уберут и заменят на нейронные связи, поэтому я их не учу.",
            "Слушайте, а какие задачи вообще будут на испытательном сроке? Вы используете микросервисы?",
            "Стоп интервью. Давай фидбэк."
        ],
        "description": "Тестирование базовых знаний Junior разработчика, обработка галлюцинаций и встречных вопросов."
    },
    {
        "name": "Сценарий 2: Middle Python Developer",
        "context": {
            "name": "Михаил",
            "position": "Python Developer",
            "grade": "Middle",
            "experience": "3 года коммерческого опыта, FastAPI, PostgreSQL",
            "technologies": ["Python", "FastAPI", "PostgreSQL", "Docker", "Redis"]
        },
        "dialogue": [
            "Здравствуйте! У меня 3 года опыта в коммерческой разработке на Python.",
            "Я использовал асинхронность в FastAPI для обработки большого количества одновременных запросов.",
            "Мне нравится погода сегодня, не правда ли? Кстати, когда перерыв?",
            "Я сам написал свой ORM который быстрее SQLAlchemy в 100 раз, используя нейросетевую оптимизацию.",
            "Какие у вас Code Review практики?",
            "Стоп интервью, покажи фидбэк."
        ],
        "description": "Тестирование Middle уровня, обработка оффтопика и галлюцинаций, встречные вопросы."
    }
]


async def run_scenario(scenario: dict) -> dict:
    """
    Запуск одного сценария.
    
    Returns:
        Результаты выполнения
    """
    print(f"\n{'='*70}")
    print(f"🔧 ЗАПУСК СЦЕНАРИЯ: {scenario['name']}")
    print(f"{'='*70}")
    print(f"Описание: {scenario['description']}")

    # Получаем имя кандидата из контекста
    participant_name = scenario['context'].get('name', 'Кандидат')
    
    # Создаем координатора с именем кандидата
    coordinator = InterviewCoordinator(
        participant_name=participant_name,
        enable_logging=True
    )
    
    # Создаем уникальное имя файла для лога
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    scenario_slug = scenario['name'].lower().replace(' ', '_').replace(':', '')[:30]
    log_filename = f"logs/scenario_{scenario_slug}_{timestamp}.json"
    
    # Начинаем интервью
    greeting = await coordinator.start_interview(scenario["context"])
    print(f"\n🤖 {greeting}")
    
    results = {
        "scenario_name": scenario["name"],
        "context": scenario["context"],
        "turns": [],
        "start_time": datetime.now().isoformat()
    }
    
    # Проходим по диалогу
    for turn_num, user_message in enumerate(scenario["dialogue"], 1):
        print(f"\n👤 [Ход {turn_num}]: {user_message}")
        
        # Обработка ответа
        response = await coordinator.process_user_response(user_message)
        print(f"🤖 {response}")
        
        # Сохраняем ход
        results["turns"].append({
            "turn_number": turn_num,
            "user_message": user_message,
            "agent_response": response,
            "timestamp": datetime.now().isoformat()
        })
        
        # Небольшая пауза между ходами
        if turn_num < len(scenario["dialogue"]):
            await asyncio.sleep(0.5)
    
    # Завершаем интервью
    feedback = await coordinator.end_interview()
    results["end_time"] = datetime.now().isoformat()
    results["feedback"] = feedback
    
    # Сохраняем лог
    log_file = coordinator.save_session(log_filename)
    
    # Также сохраняем результаты в отдельный файл
    results_file = log_filename.replace(".json", "_results.json")
    with open(results_file, 'w', encoding='utf-8') as f:
        json.dump(results, f, ensure_ascii=False, indent=2)
    
    print(f"\n💾 Лог сохранен в: {log_file}")
    print(f"💾 Результаты сохранены в: {results_file}")
    
    return {
        "scenario": scenario["name"],
        "log_file": log_file,
        "results_file": results_file,
        "feedback_summary": {
            "grade": feedback.get("verdict", {}).get("grade", "N/A"),
            "recommendation": feedback.get("verdict", {}).get("hiring_recommendation", "N/A"),
            "confidence": feedback.get("verdict", {}).get("confidence_score", "0%")
        },
        "stats": coordinator.get_status()["stats"]
    }


async def main():
    """Основная функция для запуска всех сценариев."""
    
    # Проверка API ключа
    if not os.getenv("MISTRAL_API_KEY"):
        print("❌ ОШИБКА: Не найден MISTRAL_API_KEY")
        print("   Установите переменную окружения или создайте .env файл")
        return
    
    # Настройка логгирования
    setup_logging()
    
    print("=" * 70)
    print("🚀 ЗАПУСК СЕКРЕТНЫХ СЦЕНАРИЕВ")
    print("=" * 70)
    print(f"Всего сценариев: {len(SECRET_SCENARIOS)}")
    print("Создаются JSON-логи в формате для сдачи задания.")
    print("=" * 70)
    
    # Создаем директорию для логов
    Path("logs").mkdir(exist_ok=True)
    
    all_results = []
    
    # Запускаем все сценарии
    for i, scenario in enumerate(SECRET_SCENARIOS, 1):
        print(f"\n📋 Сценарий {i}/{len(SECRET_SCENARIOS)}")
        
        try:
            result = await run_scenario(scenario)
            all_results.append(result)
            
            print(f"✅ Сценарий завершен: {result['feedback_summary']}")
            
        except Exception as e:
            print(f"❌ Ошибка при выполнении сценария: {e}")
            import traceback
            traceback.print_exc()
    
    # Выводим сводку
    print("\n" + "=" * 70)
    print("📊 СВОДКА ПО ВСЕМ СЦЕНАРИЯМ")
    print("=" * 70)
    
    for result in all_results:
        summary = result.get("feedback_summary", {})
        print(f"\nСценарий: {result['scenario']}")
        print(f"  Уровень: {summary.get('grade', 'N/A')}")
        print(f"  Рекомендация: {summary.get('recommendation', 'N/A')}")
        print(f"  Уверенность: {summary.get('confidence', '0%')}")
        print(f"  Лог-файл: {Path(result['log_file']).name}")
    
    # Сохраняем общую сводку
    summary_file = f"logs/scenarios_summary_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
    with open(summary_file, 'w', encoding='utf-8') as f:
        json.dump({
            "run_timestamp": datetime.now().isoformat(),
            "total_scenarios": len(SECRET_SCENARIOS),
            "completed_scenarios": len(all_results),
            "results": all_results
        }, f, ensure_ascii=False, indent=2)
    
    print(f"\n💾 Общая сводка сохранена в: {summary_file}")
    print("\n✅ Все сценарии выполнены. Готово к сдаче!")


if __name__ == "__main__":
    asyncio.run(main())
