# src/run_interview.py
"""
Основной файл для запуска системы интервью.
Поддерживает интерактивный режим и режим сценариев.
"""

import asyncio
import sys
import os
from pathlib import Path
from datetime import datetime

# Добавляем корневую директорию в путь для импортов
sys.path.append(str(Path(__file__).parent.parent))

from dotenv import load_dotenv
from src.core.coordinator import InterviewCoordinator
from src.utils.logger import setup_logging

# Загрузка переменных окружения
load_dotenv()


async def run_interactive_mode():
    """Запуск интерактивного режима интервью."""
    
    print("=" * 70)
    print("МУЛЬТИАГЕНТНАЯ СИСТЕМА ИНТЕРВЬЮ")
    print("Версия 1.0 | Система с двумя агентами (Interviewer + Observer)")
    print("=" * 70)
    
    # Настройка логгирования
    setup_logging()
    
    # Создаем координатора
    # coordinator = InterviewCoordinator(
    #     team_name="AI Interview Team",
    #     enable_logging=True
    # )
    
    # Ввод контекста интервью
    print("\n📋 ВВЕДИТЕ ДАННЫЕ ДЛЯ ИНТЕРВЬЮ:")
    print("-" * 40)
    
    participant_name = input("Имя кандидата: ").strip() or "Кандидат"
    position = input("Должность (например, Python Backend Developer): ").strip() or "Python Developer"
    grade = input("Уровень (Junior/Middle/Senior): ").strip() or "Middle"
    experience = input("Опыт работы: ").strip() or "1-2 года"
    tech_input = input("Технологии (через запятую): ").strip() or "Python, Django, SQL"
    
    technologies = [t.strip() for t in tech_input.split(",")]
    
    context = {
        "name": participant_name,
        "position": position,
        "grade": grade,
        "experience": experience,
        "technologies": technologies,
        "interview_date": datetime.now().strftime("%Y-%m-%d")
    }
    
    print(f"\n✅ Контекст установлен: {position} ({grade})")
    print(f"   Кандидат: {participant_name}")
    print(f"   Технологии: {', '.join(technologies)}")

    # Создаем координатора с именем кандидата
    coordinator = InterviewCoordinator(
        participant_name=participant_name,  # Передаем имя
        enable_logging=True
    )
    
    # Начинаем интервью
    print("\n" + "=" * 70)
    print("🎤 НАЧАЛО ИНТЕРВЬЮ")
    print("=" * 70)
    print("(Для завершения введите 'стоп интервью' или 'фидбэк')")
    print("-" * 70)
    
    greeting = await coordinator.start_interview(context)
    print(f"\n🤖 {greeting}")
    
    # Основной цикл диалога
    while coordinator.is_interview_active:
        try:
            # Ввод пользователя
            user_input = input("\n👤 Вы: ").strip()
            
            if not user_input:
                print("⚠️  Пожалуйста, введите ответ.")
                continue
            
            # Обработка ответа (без показа статуса)
            response = await coordinator.process_user_response(user_input)
            
            # Очищаем ответ для отображения
            response = coordinator._clean_response_for_display(response) if hasattr(coordinator, '_clean_response_for_display') else response
            
            print(f"🤖 {response}")
            
        except KeyboardInterrupt:
            print("\n\n⚠️  Интервью прервано пользователем.")
            break
        except Exception as e:
            print(f"\n❌ Произошла ошибка. Давайте продолжим.")
            # logger.error(f"Ошибка в основном цикле: {e}")
            # Пропускаем ошибку и продолжаем интервью
            continue
    
    # Если интервью завершено, показываем фидбэк
    if not coordinator.is_interview_active:
        print("\n" + "=" * 70)
        print("📊 ФИНАЛЬНЫЙ ФИДБЭК")
        print("=" * 70)
        
        # Получаем фидбэк
        feedback = coordinator.json_logger.log_data.get("final_feedback", {}) if coordinator.json_logger else {}
        
        if feedback:
            _display_feedback(feedback)
        else:
            # Генерируем фидбэк если его нет
            feedback = await coordinator.end_interview()
            _display_feedback(feedback)
        
        # Сохраняем сессию, но НЕ показываем кандидату
        try:
            log_file = coordinator.save_session()
            # print(f"\n📝 Интервью завершено. Результаты сохранены.")
        except Exception as e:
            logger.error(f"Ошибка сохранения сессии: {e}")
        
    
    print("\n✅ Спасибо за участие в интервью!")


# def _display_feedback(feedback: dict):
#     """Отображение фидбэка в читаемом формате."""
    
#     # Вердикт
#     verdict = feedback.get("verdict", {})
#     print("\n" + "=" * 70)
#     print("🎯 ВЕРДИКТ")
#     print("=" * 70)
#     print(f"  Уровень кандидата: {verdict.get('grade', 'Не определен')}")
#     print(f"  Рекомендация по найму: {verdict.get('hiring_recommendation', 'Не определена')}")
#     print(f"  Уверенность системы: {verdict.get('confidence_score', '0%')}")
#     print(f"  Краткое резюме: {verdict.get('summary', '')}")
    
#     # Hard Skills
#     technical = feedback.get("technical_review", {})
#     print("\n" + "=" * 70)
#     print("💻 HARD SKILLS - ТЕХНИЧЕСКИЙ АНАЛИЗ")
#     print("=" * 70)
    
#     confirmed = technical.get("confirmed_skills", [])
#     if confirmed:
#         print("\n✅ ПОДТВЕРЖДЕННЫЕ НАВЫКИ:")
#         print("-" * 40)
#         for skill in confirmed:
#             print(f"  Тема: {skill.get('topic')}")
#             print(f"    Точность: {skill.get('accuracy')}")
#             print(f"    Вопросов: {skill.get('correct_answers')}/{skill.get('total_questions')}")
#             if skill.get('example_question'):
#                 print(f"    Пример вопроса: {skill.get('example_question')[:80]}...")
#             print()
    
#     gaps = technical.get("knowledge_gaps", [])
#     if gaps:
#         print("\n❌ ПРОБЕЛЫ В ЗНАНИЯХ:")
#         print("-" * 40)
#         for gap in gaps:
#             print(f"  Тема: {gap.get('topic')}")
#             print(f"    Вопрос: {gap.get('question')[:100]}...")
#             print(f"    Ответ кандидата: {gap.get('candidate_answer')[:80]}...")
#             print(f"    Оценка: {gap.get('quality_score')}")
#             print(f"    ПРАВИЛЬНЫЙ ОТВЕТ: {gap.get('correct_answer')[:150]}...")
#             print(f"    Ресурсы для изучения:")
#             for resource in gap.get('suggested_resources', [])[:3]:
#                 print(f"      • {resource}")
#             print()
    
#     topics_covered = technical.get("topics_covered", [])
#     if topics_covered:
#         print(f"\n📊 Всего затронуто тем: {len(topics_covered)}")
#         print(f"   Проанализировано тем: {technical.get('total_topics_asked', 0)}")
    
#     # Soft Skills
#     soft = feedback.get("soft_skills", {})
#     print("\n" + "=" * 70)
#     print("🤝 SOFT SKILLS - НАВЫКИ КОММУНИКАЦИИ")
#     print("=" * 70)
#     for skill, value in soft.items():
#         print(f"  {skill}: {value}")
    
#     # Roadmap
#     roadmap = feedback.get("personal_roadmap", [])
#     if roadmap:
#         print("\n" + "=" * 70)
#         print("🗺️  ПЕРСОНАЛЬНЫЙ ROADMAP - СЛЕДУЮЩИЕ ШАГИ")
#         print("=" * 70)
#         for item in roadmap:
#             print(f"  Приоритет: {item.get('priority', 'medium').upper()}")
#             print(f"  Навык: {item.get('skill')}")
#             print(f"  Действие: {item.get('action')}")
#             print(f"  Время на изучение: {item.get('estimated_time')}")
#             print(f"  Конкретная задача: {item.get('specific_task', 'Практиковаться в теме')}")
#             print(f"  Ресурсы:")
#             for resource in item.get('resources', [])[:3]:
#                 print(f"    • {resource}")
#             print()
    
#     # Статистика
#     stats = feedback.get("interview_statistics", {})
#     print("\n" + "=" * 70)
#     print("📈 СТАТИСТИКА ИНТЕРВЬЮ")
#     print("=" * 70)
#     for key, value in stats.items():
#         if key not in ["summary"]:
#             print(f"  {key}: {value}")

def _display_feedback(feedback: dict):
    """Отображение фидбэка в читаемом формате для КАНДИДАТА."""
    
    # Вердикт - показываем кандидату
    verdict = feedback.get("verdict", {})
    print("\n" + "=" * 70)
    print("🎯 ФИНАЛЬНЫЙ ВЕРДИКТ")
    print("=" * 70)
    print(f"Уровень: {verdict.get('grade', 'Не определен')}")
    print(f"Рекомендация: {verdict.get('hiring_recommendation', 'Не определена')}")
    print(f"\nОбщее резюме: {verdict.get('summary', '')}")
    
    # Hard Skills - показываем кандидату
    technical = feedback.get("technical_review", {})
    print("\n" + "=" * 70)
    print("💻 ТЕХНИЧЕСКИЕ НАВЫКИ")
    print("=" * 70)
    
    confirmed = technical.get("confirmed_skills", [])
    if confirmed:
        print("\n✅ ТЕМЫ, КОТОРЫЕ КАНДИДАТ ЗНАЕТ ХОРОШО:")
        for skill in confirmed:
            print(f"\n• {skill.get('topic')}")
            print(f"  Правильных ответов: {skill.get('correct_answers')}/{skill.get('total_questions')}")
            print(f"  Точность: {skill.get('accuracy')}")
            if skill.get('example_question'):
                print(f"  Пример вопроса: {skill.get('example_question')}")
    
    gaps = technical.get("knowledge_gaps", [])
    if gaps:
        print("\n❌ ТЕМЫ, КОТОРЫЕ НУЖНО ПОДТЯНУТЬ:")
        for gap in gaps:
            print(f"\n• {gap.get('topic')}")
            print(f"  Вопрос: {gap.get('question')}")
            print(f"  Ответ кандидата: {gap.get('candidate_answer')}")
            print(f"  ПРАВИЛЬНЫЙ ОТВЕТ: {gap.get('correct_answer')}")
    
    # Soft Skills - показываем кандидату
    soft = feedback.get("soft_skills", {})
    print("\n" + "=" * 70)
    print("🤝 НАВЫКИ КОММУНИКАЦИИ")
    print("=" * 70)
    
    # Преобразуем в читаемый формат
    clarity_map = {"Высокая": "Отлично", "Средняя": "Хорошо", "Низкая": "Можно улучшить"}
    honesty_map = {"Высокая": "Отличная", "Средняя": "Хорошая", "Низкая": "Нужно поработать"}
    engagement_map = {"Высокая": "Высокая", "Средняя": "Средняя", "Низкая": "Низкая"}
    
    print(f"Ясность изложения: {clarity_map.get(soft.get('clarity', 'Средняя'), soft.get('clarity'))}")
    print(f"Честность ответов: {honesty_map.get(soft.get('honesty', 'Средняя'), soft.get('honesty'))}")
    print(f"Вовлеченность в диалог: {engagement_map.get(soft.get('engagement', 'Средняя'), soft.get('engagement'))}")
    
    # Roadmap - показываем кандидату (ОБЯЗАТЕЛЬНО!)
    roadmap = feedback.get("personal_roadmap", [])
    if roadmap:
        print("\n" + "=" * 70)
        print("🗺️  ПЕРСОНАЛЬНЫЙ ПЛАН РАЗВИТИЯ")
        print("=" * 70)
        print("Вот что вам нужно изучить для улучшения ваших навыков:")
        
        for i, item in enumerate(roadmap, 1):
            print(f"\n{i}. {item.get('skill')}")
            print(f"   Действие: {item.get('action')}")
            print(f"   Время: {item.get('estimated_time')}")
            print(f"   Конкретная задача: {item.get('specific_task')}")
            if item.get('resources'):
                print(f"   Ресурсы для изучения:")
                for resource in item.get('resources', []):
                    print(f"     - {resource}")
    else:
        # Если roadmap пустой, создаем базовые рекомендации
        print("\n" + "=" * 70)
        print("🗺️  ПЕРСОНАЛЬНЫЙ ПЛАН РАЗВИТИЯ")
        print("=" * 70)
        print("Рекомендуем обратить внимание на следующие темы:")
        
        # Базовые рекомендации на основе контекста
        technologies = ["Python", "алгоритмы", "базы данных", "ООП"]
        for i, tech in enumerate(technologies, 1):
            print(f"\n{i}. {tech}")
            print(f"   Время: 2-4 недели")
            print(f"   Ресурсы: онлайн-курсы, документация, практические задачи")


# def _display_feedback(feedback: dict):
#     """Отображение фидбэка в читаемом формате."""
    
#     # Вердикт
#     verdict = feedback.get("verdict", {})
#     print("\n🎯 ВЕРДИКТ:")
#     print(f"  Уровень кандидата: {verdict.get('grade', 'Не определен')}")
#     print(f"  Рекомендация по найму: {verdict.get('hiring_recommendation', 'Не определена')}")
#     print(f"  Уверенность системы: {verdict.get('confidence_score', '0%')}")
#     print(f"  Краткое резюме: {verdict.get('summary', '')}")
    
#     # Hard Skills
#     technical = feedback.get("technical_review", {})
#     print("\n💻 HARD SKILLS:")
    
#     confirmed = technical.get("confirmed_skills", [])
#     if confirmed:
#         print("  ✅ Подтвержденные навыки:")
#         for skill in confirmed[:5]:  # Показываем до 5 навыков
#             print(f"    • {skill.get('topic')} ({skill.get('accuracy')})")
    
#     gaps = technical.get("knowledge_gaps", [])
#     if gaps:
#         print("  ❌ Пробелы в знаниях:")
#         for gap in gaps[:3]:  # Показываем до 3 пробелов
#             print(f"    • {gap.get('topic')}: {gap.get('question')[:50]}...")
    
#     # Soft Skills
#     soft = feedback.get("soft_skills", {})
#     print("\n🤝 SOFT SKILLS:")
#     for skill, value in soft.items():
#         print(f"  {skill}: {value}")
    
#     # Roadmap
#     roadmap = feedback.get("personal_roadmap", [])
#     if roadmap:
#         print("\n🗺️  ПЕРСОНАЛЬНЫЙ ROADMAP:")
#         for item in roadmap[:3]:  # Показываем до 3 пунктов
#             print(f"  • {item.get('action')} ({item.get('estimated_time')})")
    
#     # Статистика
#     stats = feedback.get("interview_statistics", {})
#     print("\n📈 СТАТИСТИКА ИНТЕРВЬЮ:")
#     for key, value in stats.items():
#         if key not in ["summary"]:
#             print(f"  {key}: {value}")


async def run_scenario_mode(scenario_file: str = None):
    """Запуск режима сценария."""
    
    if not scenario_file:
        # Пример сценария из задания
        scenario = {
            "name": "Секретный сценарий 1",
            "context": {
                "position": "Backend Developer",
                "grade": "Junior",
                "experience": "Пет-проекты на Django, немного SQL",
                "technologies": ["Python", "Django", "SQL", "Git"]
            },
            "dialogue": [
                "Привет. Я Алекс, претендую на позицию Junior Backend Developer. Знаю Python, SQL и Git.",
                "Django - это фреймворк для веб-разработки на Python. Он использует паттерн MVT (Model-View-Template).",
                "Честно говоря, я читал на Хабре, что в Python 4.0 циклы for уберут и заменят на нейронные связи, поэтому я их не учу.",
                "Слушайте, а какие задачи вообще будут на испытательном сроке? Вы используете микросервисы?",
                "Стоп интервью. Давай фидбэк."
            ]
        }
    else:
        # Загрузка сценария из файла
        import json
        with open(scenario_file, 'r', encoding='utf-8') as f:
            scenario = json.load(f)
    
    print(f"\n🔧 Запуск сценария: {scenario.get('name', 'Без названия')}")
    
    # Создаем координатора
    coordinator = InterviewCoordinator(
        team_name="Scenario Test Team",
        enable_logging=True
    )
    
    # Начинаем интервью
    greeting = await coordinator.start_interview(scenario["context"])
    print(f"\n🤖 {greeting}")
    
    # Проходим по диалогу сценария
    for i, user_message in enumerate(scenario["dialogue"], 1):
        print(f"\n👤 [Ход {i}]: {user_message}")
        
        response = await coordinator.process_user_response(user_message)
        print(f"🤖 {response}")
        
        # Пауза между ходами для имитации реального диалога
        if i < len(scenario["dialogue"]):
            await asyncio.sleep(1)
    
    # Завершаем интервью
    feedback = await coordinator.end_interview()
    
    # Сохраняем сессию
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    log_file = coordinator.save_session(f"logs/scenario_{timestamp}.json")
    
    print(f"\n💾 Лог сохранен в: {log_file}")
    
    return {
        "scenario": scenario["name"],
        "log_file": log_file,
        "feedback": feedback,
        "stats": coordinator.get_status()["stats"]
    }


def main():
    """Главная функция."""
    
    # Проверяем API ключ
    if not os.getenv("MISTRAL_API_KEY"):
        print("❌ ОШИБКА: Не найден MISTRAL_API_KEY в переменных окружения.")
        print("   Создайте файл .env и добавьте: MISTRAL_API_KEY=ваш_ключ")
        return
    
    print("Выберите режим:")
    print("1. Интерактивное интервью")
    print("2. Запуск тестового сценария")
    print("3. Запуск секретного сценария из файла")
    
    choice = input("\nВаш выбор (1-3): ").strip()
    
    if choice == "1":
        asyncio.run(run_interactive_mode())
    elif choice == "2":
        asyncio.run(run_scenario_mode())
    elif choice == "3":
        filepath = input("Путь к файлу сценария: ").strip()
        if os.path.exists(filepath):
            asyncio.run(run_scenario_mode(filepath))
        else:
            print(f"❌ Файл не найден: {filepath}")
    else:
        print("❌ Неверный выбор. Завершение.")


if __name__ == "__main__":
    main()
