"""
RAG (Retrieval-Augmented Generation) Loader Module

This module provides functions for loading apartment information and prompts
from the file system to be used in the guest chat system.
"""

import json
import os


def load_text_from_file(filepath: str) -> str:
    """
    Loads text content from a specified file.

    Args:
        filepath: Path to the text file

    Returns:
        File content as string, or empty string if file not found or error occurs
    """
    try:
        with open(filepath, "r", encoding="utf-8") as f:
            return f.read()
    except FileNotFoundError:
        print(f"Error: File not found at {filepath}")
        return ""
    except Exception as e:
        print(f"Error loading {filepath}: {e}")
        return ""


def load_json_from_file(filepath: str) -> list:
    """
    Loads JSON data from a specified file.

    Args:
        filepath: Path to the JSON file

    Returns:
        Parsed JSON data as list, or empty list if file not found or error occurs
    """
    try:
        with open(filepath, "r", encoding="utf-8") as f:
            return json.load(f)
    except FileNotFoundError:
        print(f"Error: JSON file not found at {filepath}")
        return []
    except json.JSONDecodeError as e:
        print(f"Error decoding JSON from {filepath}: {e}")
        return []
    except Exception as e:
        print(f"Error loading {filepath}: {e}")
        return []


def load_apartment_info(directory: str) -> str:
    """
    Loads all text from .txt files in the specified directory and combines them.

    Args:
        directory: Path to directory containing apartment info text files

    Returns:
        Combined text from all .txt files, separated by double newlines
    """
    full_info = []
    if not os.path.exists(directory):
        print(
            f"Warning: Apartment info directory '{directory}' not found. Please create it and add .txt files."
        )
        return ""

    sorted_files = sorted(os.listdir(directory))

    for filename in sorted_files:
        filepath = os.path.join(directory, filename)
        if os.path.isfile(filepath) and filepath.endswith(".txt"):
            try:
                full_info.append(load_text_from_file(filepath))
            except Exception as e:
                print(f"Error loading {filepath} for apartment info: {e}")

    return "\n\n".join(full_info)


def load_prompts(
    prompts_dir: str,
    system_prompt_filename: str = "system_prompt_employee.txt",
    few_shot_filename: str = "few_shot_examples.json",
) -> tuple[str, list]:
    """
    Loads system prompt and few-shot examples from the prompts directory.

    Args:
        prompts_dir: Path to directory containing prompt files
        system_prompt_filename: Name of the system prompt file
        few_shot_filename: Name of the few-shot examples JSON file

    Returns:
        Tuple of (system_prompt_content, few_shot_examples)
    """
    system_prompt_path = os.path.join(prompts_dir, system_prompt_filename)
    few_shot_path = os.path.join(prompts_dir, few_shot_filename)

    system_prompt_content = load_text_from_file(system_prompt_path)
    few_shot_examples = load_json_from_file(few_shot_path)

    return system_prompt_content, few_shot_examples
