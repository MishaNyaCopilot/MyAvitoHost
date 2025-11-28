"""
Guest Chat Interface Module

This module provides an interactive chat interface for apartment rental guests
powered by Ollama LLM with RAG (Retrieval-Augmented Generation) capabilities.
It loads apartment information and prompts from files, processes guest inquiries,
and can trigger notifications to landlords via the MCP server when check-in
times are mentioned.
"""

import asyncio
import json
import os
import re

import httpx
import ollama
from fastmcp import Client

from src.chat.rag_loader import load_apartment_info, load_json_from_file, load_text_from_file
from src.constants import (
    DEFAULT_APARTMENT_INFO_DIR,
    DEFAULT_MCP_SERVER_URL,
    DEFAULT_PROMPTS_DIR,
)

# --- Константы ---
HARDCODED_APARTMENT_ADDRESS = "Ленинском проспекте, 123"
MCP_SERVER_URL = os.getenv("MCP_SERVER_URL", DEFAULT_MCP_SERVER_URL)
APARTMENT_INFO_DIR = os.getenv("APARTMENT_INFO_DIR", DEFAULT_APARTMENT_INFO_DIR)
PROMPTS_DIR = os.getenv("PROMPTS_DIR", DEFAULT_PROMPTS_DIR)


# --- Асинхронная функция для выбора модели Ollama ---
async def get_ollama_model():
    """
    Fetches available Ollama models and prompts user to select one.

    Returns:
        Selected model name string, or None if no models available or
        connection fails

    Note:
        Displays numbered list of available models and accepts either
        the number or full model name as input
    """
    try:
        models_info = ollama.list()
        available_models = [m["model"] for m in models_info["models"]]

        if not available_models:
            print(
                "ERROR: No Ollama models found. Please pull models (e.g., 'ollama pull llama2') and ensure Ollama is running."
            )
            return None

        print("\nAvailable Ollama Models:")
        for i, model_name in enumerate(available_models):
            print(f"{i + 1}. {model_name}")

        while True:
            try:
                choice = input(f"Select a model (1-{len(available_models)}) or type full name: ")
                if choice.isdigit():
                    idx = int(choice) - 1
                    if 0 <= idx < len(available_models):
                        return available_models[idx]
                elif choice in available_models:
                    return choice
                print("Invalid choice. Please try again.")
            except ValueError:
                print("Invalid input. Please enter a number or a model name.")

    except httpx.ConnectError:
        print("ERROR: Could not connect to Ollama server. Please ensure Ollama is running.")
        return None
    except Exception as e:
        print(f"An unexpected error occurred while listing models: {e}")
        return None


# --- Основная асинхронная функция чата ---
async def main():
    """
    Main entry point for the guest chat interface.

    Initializes the chat system by:
    1. Selecting an Ollama model
    2. Loading apartment information and prompts
    3. Setting up the MCP client for notifications
    4. Running the interactive chat loop

    The chat uses RAG to provide context-aware responses about the apartment
    and can trigger landlord notifications when guests mention check-in times.
    """
    print("Welcome to the Mini Apartment Rental Chat!")
    print(f"Apartment address is hardcoded to: {HARDCODED_APARTMENT_ADDRESS}")
    print(
        "You can chat freely, and the system will trigger a notification when a check-in time is mentioned."
    )
    print("Type 'exit' to quit.")

    # Создаем директории, если их нет
    os.makedirs(APARTMENT_INFO_DIR, exist_ok=True)
    os.makedirs(PROMPTS_DIR, exist_ok=True)

    selected_model = await get_ollama_model()
    if not selected_model:
        print("Exiting due to no Ollama model selected or available.")
        return

    print(f"\nUsing Ollama model: {selected_model}")

    # Инициализация FastMCP клиента
    mcp_client = Client(MCP_SERVER_URL)

    # Загружаем системный промпт и few-shot примеры
    system_prompt_content = load_text_from_file(
        os.path.join(PROMPTS_DIR, "system_prompt_employee.txt")
    )
    few_shot_examples = load_json_from_file(os.path.join(PROMPTS_DIR, "few_shot_examples.json"))

    if not system_prompt_content:
        print(f"Error: system_prompt_employee.txt not loaded. Check '{PROMPTS_DIR}' directory.")
        return  # Выход, так как без системного промпта LLM будет непредсказуемой

    # Загружаем информацию о квартире
    apartment_full_info = load_apartment_info(APARTMENT_INFO_DIR)
    if apartment_full_info:
        print(
            f"Loaded apartment info from '{APARTMENT_INFO_DIR}'. Size: {len(apartment_full_info)} characters."
        )
        # Добавляем RAG-информацию к системному промпту
        final_system_prompt = system_prompt_content + (
            f"\n\nВот дополнительная информация о квартире, которую вы должны использовать для ответов:\n\n{apartment_full_info}"
        )
    else:
        print("No apartment info loaded. LLM will rely only on its internal knowledge.")
        final_system_prompt = system_prompt_content

    # Инициализация истории сообщений для LLM.
    messages = [{"role": "system", "content": final_system_prompt}]
    # Добавляем few-shot примеры, если они были загружены
    if few_shot_examples:
        messages.extend(few_shot_examples)
        print(f"Loaded {len(few_shot_examples)} few-shot examples.")
    else:
        print(
            "Warning: few_shot_examples.json not loaded or is empty. LLM might be less predictable."
        )

    while True:
        user_input = input("\nYour request: ")
        if user_input.lower() == "exit":
            break

        # --- Добавляем текущее сообщение пользователя в постоянную историю ---
        messages.append({"role": "user", "content": user_input})

        # --- Первый вызов Ollama: Генерация общего разговорного ответа ---
        try:
            print("Generating conversational response...")
            # Передаем всю историю сообщений для поддержания контекста и роли
            conversation_response = ollama.chat(model=selected_model, messages=messages)
            assistant_reply = conversation_response["message"]["content"]
            print(f"Ollama: {assistant_reply}")

            # Добавляем ответ ассистента в постоянную историю
            messages.append({"role": "assistant", "content": assistant_reply})

        except ollama.ResponseError as e:
            print(
                f"Ollama API Error (Conversation): {e}. Please check if the model is correctly pulled and the Ollama server is functional."
            )
            messages.pop()  # Удаляем user_input, если LLM не смогла ответить
            continue
        except httpx.ConnectError:
            print("Connection to Ollama server lost. Please ensure Ollama is still running.")
            messages.pop()  # Удаляем user_input, если LLM не смогла ответить
            continue
        except Exception as e:
            print(f"An unexpected error occurred with Ollama (Conversation): {e}")
            messages.pop()  # Удаляем user_input, если LLM не смогла ответить
            continue

        # --- Второй вызов Ollama: Извлечение информации для MCP-сервера ---
        # Здесь мы по-прежнему используем только последнее сообщение пользователя для извлечения,
        # чтобы промпт для извлечения был максимально чистым и сфокусированным.
        extraction_prompt = (
            "You are an information extraction assistant. "
            "Your task is to extract the 'check_in_time' from the LAST user message. "
            "The 'check_in_time' should be a string in 'HH:MM' format. "
            "If the time is not explicitly provided, use 'Unknown Time'. "
            "Also, determine if the user expresses an 'intent_to_check_in' (boolean: true/false) "
            "based on keywords like 'заселиться', 'заехать', 'приехать', 'хочу'. "
            "Respond ONLY with a JSON object containing these two keys, for example: "
            '{"check_in_time": "15:30", "intent_to_check_in": true}'
        )

        extraction_messages = [
            {"role": "system", "content": extraction_prompt},
            {"role": "user", "content": user_input},
        ]

        extracted_time = "Unknown Time"
        intent_to_check_in = False

        try:
            print("Sending request to Ollama for extraction and intent detection...")
            extraction_response = ollama.chat(model=selected_model, messages=extraction_messages)
            llm_extraction_content = extraction_response["message"]["content"]
            print(f"Ollama Raw Extraction Response: {llm_extraction_content}")

            # Попытка извлечь JSON из markdown-блока (```json\n...\n```)
            json_match = re.search(r"```json\n(.*)\n```", llm_extraction_content, re.DOTALL)
            if json_match:
                json_string = json_match.group(1)
            else:
                json_string = (
                    llm_extraction_content  # Предполагаем, что это прямой JSON, если нет markdown
                )

            try:
                parsed_extraction = json.loads(json_string)
                if "check_in_time" in parsed_extraction:
                    extracted_time = parsed_extraction["check_in_time"]
                if "intent_to_check_in" in parsed_extraction:
                    intent_to_check_in = parsed_extraction["intent_to_check_in"]
            except json.JSONDecodeError:
                print(
                    "Warning: Ollama did not return valid JSON. Attempting fallback extraction for time and intent."
                )
                # Fallback для извлечения времени (поиск "HH:MM")
                time_match = re.search(
                    r"\b([01]?[0-9]|2[0-3]):([0-5][0-9])\b", llm_extraction_content
                )
                if time_match:
                    extracted_time = time_match.group(0)  # Получаем полное совпадение "HH:MM"

                # Fallback для определения намерения (простая проверка ключевых слов)
                if any(
                    keyword in user_input.lower()
                    for keyword in ["заселиться", "заехать", "приехать", "хочу"]
                ):
                    intent_to_check_in = True

        except ollama.ResponseError as e:
            print(f"Ollama API Error (Extraction): {e}")
            continue
        except httpx.ConnectError:
            print("Connection to Ollama server lost.")
            continue
        except Exception as e:
            print(f"An unexpected error occurred with Ollama (Extraction): {e}")
            continue

        print(f"LLM extracted: Time='{extracted_time}', Intent='{intent_to_check_in}'")

        # --- Условный вызов MCP Tool ---
        if extracted_time != "Unknown Time" and intent_to_check_in:
            print("Detected check-in time and intent. Triggering MCP notification...")
            try:
                async with mcp_client:
                    result = await mcp_client.call_tool(
                        "notify_rental_request",
                        {
                            "apartment_address": HARDCODED_APARTMENT_ADDRESS,
                            "check_in_time": extracted_time,
                        },
                    )
                    print(f"MCP Server Response: {result}")
                    # Добавляем подтверждение для пользователя
                    messages.append(
                        {
                            "role": "assistant",
                            "content": f"Понял, ваше время заселения на {extracted_time} передано владельцу. Дополнительного подтверждения не требуется.",
                        }
                    )
            except Exception as e:
                print(f"An unexpected error occurred during MCP call: {e}")
                print("Please ensure the FastMCP server (mcp_server.py) is running.")
                messages.append(
                    {
                        "role": "assistant",
                        "content": "Извините, произошла ошибка при попытке передать информацию владельцу. Пожалуйста, попробуйте позже или свяжитесь с нами по телефону.",
                    }
                )
        else:
            print("No check-in time or explicit intent detected. Continuing conversation.")


if __name__ == "__main__":
    # Убедитесь, что директории существуют
    os.makedirs(APARTMENT_INFO_DIR, exist_ok=True)
    os.makedirs(PROMPTS_DIR, exist_ok=True)

    # Создайте файлы с промптами, если их нет, чтобы избежать ошибок при первом запуске
    # и дать пример структуры
    system_prompt_file = os.path.join(PROMPTS_DIR, "system_prompt_employee.txt")
    if not os.path.exists(system_prompt_file):
        with open(system_prompt_file, "w", encoding="utf-8") as f:
            f.write(
                "Вы - вежливый и услужливый сотрудник по аренде квартир. Ваша задача - отвечать на вопросы гостей, помогать им с заселением, предоставлять информацию о квартире и передавать детали заселения владельцу. Будьте доброжелательны, терпеливы и информативны. Всегда старайтесь помочь гостю и сделать его пребывание максимально комфортным. Используйте предоставленную вам информацию о квартире для ответов на вопросы. НЕ НАЧИНАЙТЕ КАЖДОЕ СООБЩЕНИЕ С ПРИВЕТСТВИЯ. Продолжайте диалог естественно, как обычный собеседник. Приветствуйте только в начале нового диалога или после явной паузы со стороны гостя. При подтверждении времени заселения, если оно отличается от стандартного, просто подтвердите его и сообщите о передаче информации владельцу. НЕ УКАЗЫВАЙТЕ, что требуется дополнительное подтверждение от владельца, или что гостю нужно чего-то ждать."
            )
        print(f"Created default '{system_prompt_file}'. Please review and customize.")

    few_shot_file = os.path.join(PROMPTS_DIR, "few_shot_examples.json")
    if not os.path.exists(few_shot_file):
        with open(few_shot_file, "w", encoding="utf-8") as f:
            json.dump(
                [
                    {"role": "user", "content": "Привет"},
                    {
                        "role": "assistant",
                        "content": "Здравствуйте! Рад вас видеть. Чем могу помочь?",
                    },
                    {"role": "user", "content": "Можно заселиться сегодня в 16:00?"},
                    {
                        "role": "assistant",
                        "content": "Да, конечно, вы сможете заселиться в 16:00. Я передам информацию владельцу о вашем прибытии.",
                    },
                    {
                        "role": "user",
                        "content": "Я забронировал, но смогу приехать только в 18:00, это нормально?",
                    },
                    {
                        "role": "assistant",
                        "content": "Да, 18:00 — это отличное время для вашего заезда. Информация о вашем прибытии в 18:00 передана владельцу.",
                    },
                    {"role": "user", "content": "А что насчет чистоты?"},
                    {
                        "role": "assistant",
                        "content": "В квартире абсолютно чисто! Каждый день проводится уборка, и вы можете быть уверены в свежести и уюте. Постельное белье всегда новое.",
                    },
                    {"role": "user", "content": "Как пользоваться горячей водой?"},
                    {
                        "role": "assistant",
                        "content": "У нас установлена газовая колонка, ее трогать не нужно. Вода из-под крана и душа всегда будет теплой.",
                    },
                    {"role": "user", "content": "Сколько стоит?"},
                    {
                        "role": "assistant",
                        "content": "Стоимость указана за 2х человек и 1 комплект постельного белья. Цена в праздничные дни может меняться. Также возможна почасовая аренда.",
                    },
                    {"role": "user", "content": "Сколько человек поместится?"},
                    {
                        "role": "assistant",
                        "content": "Максимальная вместимость квартиры - 3 человека. Комфортно размещаются до 2х человек.",
                    },
                    {"role": "user", "content": "Где находится квартира?"},
                    {
                        "role": "assistant",
                        "content": "Квартира расположена по адресу: Республика Марий Эл, Йошкар-Ола, Первомайская ул., 150. Это центр города.",
                    },
                ],
                f,
                ensure_ascii=False,
                indent=2,
            )
        print(f"Created default '{few_shot_file}'. Please review and customize.")

    asyncio.run(main())
