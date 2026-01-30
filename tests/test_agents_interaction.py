# tests/test_agents_interaction.py
"""
Тестирование взаимодействия между Interviewer и Observer.
"""

import asyncio
import sys
import os

# Добавляем путь к src
sys.path.append(os.path.join(os.path.dirname(__file__), '..'))

from src.agents.interviewer import InterviewerAgent
from src.agents.observer import ObserverAgent


async def test_agents_interaction():
    """Тест взаимодействия агентов."""
    
    print("=" * 60)
    print("ТЕСТ ВЗАИМОДЕЙСТВИЯ АГЕНТОВ")
    print("=" * 60)
    
    # Создаем агентов
    interviewer = InterviewerAgent(name="ТехническийИнтервьюер")
    observer = ObserverAgent(name="ТехническийЭксперт")
    
    # Контекст интервью
    context = {
        "position": "Python Backend Developer",
        "grade": "Middle",
        "experience": "3 года коммерческого опыта",
        "technologies": ["Python", "Django", "PostgreSQL", "Docker", "REST API"],
        "current_topic": "Python",
        "current_difficulty": "middle"
    }
    
    interviewer.set_interview_context(context)
    observer.set_interview_context(context)
    
    # История диалога
    conversation_history = []
    
    # Начинаем интервью
    print("\n[НАЧАЛО ИНТЕРВЬЮ]")
    greeting = await interviewer.start_interview(context)
    print(f"Interviewer: {greeting}")
    conversation_history.append({"role": "assistant", "content": greeting})
    
    # Тестовые ответы кандидата
    test_responses = [
        "У меня 3 года опыта работы с Python и Django. Разрабатывал REST API для e-commerce платформы.",
        "В Python есть списки (list), кортежи (tuple), словари (dict) и множества (set). Списки изменяемые, кортежи - нет.",
        "Честно говоря, я читал на Хабре, что в Python 4.0 циклы for уберут и заменят на нейронные связи, поэтому я их не учу.",
        "Слушайте, а какие задачи вообще будут на испытательном сроке? Вы используете микросервисы?",
        "Стоп интервью. Давай фидбэк."
    ]
    
    # Проходим по тестовым ответам
    for i, user_response in enumerate(test_responses, 1):
        print(f"\n{'='*50}")
        print(f"ХОД {i}:")
        print(f"Кандидат: {user_response}")
        
        # Добавляем ответ в историю
        conversation_history.append({"role": "user", "content": user_response})
        
        # Observer анализирует ответ
        if i > 1:  # Пропускаем первый ответ (на приветствие)
            print("\n[OBSERVER АНАЛИЗИРУЕТ ОТВЕТ]")
            
            # Получаем последний вопрос
            last_question = ""
            for msg in reversed(conversation_history):
                if msg["role"] == "assistant":
                    last_question = msg["content"]
                    break
            
            # Observer анализирует
            observer_analysis = await observer.analyze_and_recommend(
                question=last_question,
                answer=user_response,
                context=context
            )
            
            print(f"Анализ Observer: {observer_analysis['analysis'][:200]}...")
            print(f"Рекомендация: {observer_analysis['recommendation']}")
            
            # Отправляем рекомендацию Interviewer (симуляция)
            interviewer.send_message(
                to_agent=observer,
                message=f"Рекомендация для ответа {i}: {observer_analysis['recommendation']}",
                metadata={"response_number": i, "has_hallucinations": observer_analysis['has_hallucinations']}
            )
        
        # Interviewer генерирует следующий вопрос
        if "стоп" not in user_response.lower():
            print("\n[INTERVIEWER ГЕНЕРИРУЕТ СЛЕДУЮЩИЙ ВОПРОС]")
            
            # Внутренние мысли Interviewer
            interviewer_thoughts = await interviewer.think(user_response, context, conversation_history)
            print(f"Мысли Interviewer: {interviewer_thoughts['thoughts'][:150]}...")
            
            # Ответ Interviewer
            interviewer_response = await interviewer.respond(user_response, context, conversation_history)
            print(f"Interviewer: {interviewer_response}")
            
            # Добавляем в историю
            conversation_history.append({"role": "assistant", "content": interviewer_response})
    
    # Выводим итоги
    print(f"\n{'='*60}")
    print("ИТОГИ ТЕСТА:")
    print("=" * 60)
    
    # Статус Interviewer
    print("\nINTERVIEWER СТАТУС:")
    for key, value in interviewer.get_status().items():
        print(f"  {key}: {value}")
    
    print("\nИнтервью сводка:")
    interview_summary = interviewer.get_interview_summary()
    print(f"  Всего вопросов: {interview_summary['total_questions']}")
    print(f"  Темы: {', '.join(interview_summary['topics_covered'][:5])}")
    print(f"  Финальная сложность: {interview_summary['difficulty_progression']}")
    
    # Статус Observer
    print("\nOBSERVER СТАТУС:")
    for key, value in observer.get_status().items():
        print(f"  {key}: {value}")
    
    print("\nОценки Observer:")
    eval_summary = observer.get_evaluation_summary()
    print(f"  Всего оценок: {eval_summary['total_evaluations']}")
    print(f"  Средняя уверенность: {eval_summary['average_confidence']}")
    print(f"  Найдено галлюцинаций: {eval_summary['hallucination_count']}")
    
    # Внутренние мысли агентов
    print(f"\n{'='*60}")
    print("ВНУТРЕННИЕ МЫСЛИ INTERVIEWER:")
    print("=" * 60)
    print(interviewer.get_internal_thoughts())
    
    print(f"\n{'='*60}")
    print("ВНУТРЕННИЕ МЫСЛИ OBSERVER:")
    print("=" * 60)
    print(observer.get_internal_thoughts())


if __name__ == "__main__":
    # Запуск теста
    asyncio.run(test_agents_interaction())
