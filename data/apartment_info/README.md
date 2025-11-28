# Apartment Information Files

This directory contains example apartment information files used by the RAG (Retrieval-Augmented Generation) system to answer guest questions.

## File Formats

### info.csv
A CSV file containing structured apartment information in Russian. Format:
- **Column 1 (Категория)**: Category (О квартире, О доме, Правила, Расположение, Описание, Дополнительно)
- **Column 2 (Название характеристики)**: Characteristic name
- **Column 3 (Значение)**: Value

### Text Files (*.txt)
Plain text files containing apartment details in Russian:

- **допы.txt**: Additional information about daily cleaning, linens, and utilities
- **о доме.txt**: Building information (floors, elevator, parking)
- **о квартире.txt**: Apartment details (rooms, beds, area, floor, amenities)
- **описание.txt**: Full description including amenities, nearby locations, pricing, rules
- **правила.txt**: House rules (check-in/out times, guest limits, pets, smoking, etc.)
- **расположение.txt**: Location/address information

## Usage

These files are loaded by the RAG system (`src/chat/rag_loader.py`) and embedded into a vector database (ChromaDB) to provide context for the AI assistant when answering guest questions.

## Customization

To use this system for your own apartment:

1. Replace placeholder values `[CITY]`, `[STREET]`, `[BUILDING_NUMBER]` with actual information
2. Update apartment characteristics to match your property
3. Modify rules and amenities as needed
4. Ensure all sensitive personal information is removed before committing to version control

## Note on Sensitive Data

The example files contain placeholder values for addresses and other potentially sensitive information. Always sanitize data before sharing or committing to public repositories.
