# Prompt Files

This directory contains prompt templates and examples used by the AI chat system.

## File Formats

### system_prompt_employee.txt
A plain text file containing the system prompt that defines the AI assistant's role and behavior. This prompt:
- Defines the assistant as a polite and helpful rental employee
- Sets guidelines for conversation style (natural, not overly formal)
- Instructs when to use specific tools (e.g., `notify_rental_request_tool`)
- Provides context on how to handle guest questions

**Format**: Plain text, UTF-8 encoded, in Russian

### few_shot_examples.json
A JSON file containing example conversations to guide the AI's responses. This uses few-shot learning to demonstrate desired conversation patterns.

**Format**: JSON array of message objects
```json
[
  {
    "role": "user" | "assistant",
    "content": "message text"
  }
]
```

Each object represents one message in the conversation:
- **role**: Either "user" (guest message) or "assistant" (AI response)
- **content**: The message text in Russian

## Usage

These files are loaded by the chat system (`src/chat/guest_chat.py`) to configure the AI assistant's behavior and provide examples of good responses.

## Customization

To customize the AI assistant for your use case:

1. **system_prompt_employee.txt**: Modify the instructions to match your business needs, tone, and available tools
2. **few_shot_examples.json**: Add or modify example conversations that demonstrate the desired interaction style

## Best Practices

- Keep the system prompt clear and concise
- Include 5-10 few-shot examples covering common scenarios
- Ensure examples demonstrate the desired tone and level of detail
- Update examples when you identify common guest questions or issues
- Test changes thoroughly to ensure the AI behaves as expected

## Note on Sensitive Data

The example files contain placeholder values for addresses. Always sanitize data before sharing or committing to public repositories.
