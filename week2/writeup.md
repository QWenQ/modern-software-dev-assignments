# Week 2 Write-up
Tip: To preview this markdown file
- On Mac, press `Command (⌘) + Shift + V`
- On Windows/Linux, press `Ctrl + Shift + V`

## INSTRUCTIONS

Fill out all of the `TODO`s in this file.

## SUBMISSION DETAILS

Name: **TODO** \
SUNet ID: **TODO** \
Citations: **TODO**

This assignment took me about **TODO** hours to do. 


## YOUR RESPONSES
For each exercise, please include what prompts you used to generate the answer, in addition to the location of the generated response. Make sure to clearly add comments in your code documenting which parts are generated.

### Exercise 1: Scaffold a New Feature
Prompt: 
```
You are a helpful coding assistant.
First, you should analyze the existing `extract_action_items()` function in `app/services/extract.py`
and then implement an LLM-powered alternative, `extract_action_items_llm()`,
that utilizes Ollama to perform action item extraction via a large language model `mistral-nemo:12b`.
You should set the temperature of the model to 0 for more deterministic output.
The model should return as JSON.
``` 

Generated Code Snippets:
```
week2/app/services/extract.py:92 - 167
```

### Exercise 2: Add Unit Tests
Prompt: 
```
You're a helpful coding assistant.
Now, you should write unit tests for `extract_action_items_llm()` function in './tests/test_extract.py'.
The unit tests should cover multiple inputs: bullet lists, keyword-prefixed lines, empty input.
Before you run the tests, you should call `conda activate cs146s` to initialize environment.
Now you can run the tests and reimplement `extract_action_items_llm()` until it passes all unit tests.
``` 

Generated Code Snippets:
```
week2/tests/test_extract.py:
 - Line 22 - 116: 7 comprehensive test functions for LLM extraction

Test functions generated:
1. test_extract_bullet_lists(Line 25 - 39)
    - Test extraction from bullet list format.
2. test_extract_keyword_prefixed_lines(Line 41 - 55)
    - Test extraction from lines with action keywords.
3. test_extract_with_checkboxes(Line 57 - 71)
    - Test extraction from checkbox format.
4. test_empty_input(Line 73 - 78)
    - Test with empty input.
5. test_no_action_items(Line 80 - 84)
    - Test with text that contains no action items.
6. test_deduplication(Line 86 - 98)
    - Test that duplicate items are removed.
7. test_mixed_format_input(Line 100 - 115)
    - Test with mixed format input.
```

### Exercise 3: Refactor Existing Code for Clarity
Prompt: 
```
Perform a refactor of the code in the backend, focusing in particular on well-defined API contracts/schemas, database layer cleanup, app lifecycle/configuration, error handling.
``` 

Generated/Modified Code Snippets:
```
TODO: List all modified code files with the relevant line numbers. (We anticipate there may be multiple scattered changes here – just produce as comprehensive of a list as you can.)
New Files
1. app/config.py: Centralized app settings. Defines the Settings dataclass, loads env vars, and resolves frontend/data/db paths plus Ollama configuration.
2. app/dependencies.py: FastAPI dependency helpers. Pulls settings, database, and the action-item extractor from app.state.
3. app/errors.py: Shared API error contract. Defines app-specific exceptions, error response models, and global exception handlers for validation, not-found, service, and unexpected errors.
4. app/schemas.py: Typed request/response models. Replaces raw dict payload handling with explicit Pydantic schemas for notes and action items.
5. tests/test_api.py: New API-level tests. Covers note creation/listing, extraction flow, validation errors, missing resources, and extractor failure behavior.

Refactored Files
1. app/main.py: Refactored into an app factory with FastAPI lifespan startup. Initializes DB and extractor in app.state, registers exception handlers, and serves the frontend without import-time side effects.
2. app/db.py: Cleaned up into a repository-style database layer. Adds typed NoteRecord/ActionItemRecord models, transaction-safe connection management, atomic note+items creation, and keeps thin compatibility wrappers for old helper functions.
3. app/routers/notes.py: Switched from loose JSON handling to typed schemas and dependency injection. Also adds GET /notes and consistent 404 behavior.
4. app/routers/action_items.py: Refactored to typed request/response models, shared errors, dependency-injected extractor/DB access, and transactional persistence when saving a note with extracted items.
5. app/services/extract.py: Reworked LLM extraction flow. Separates Ollama call failures from parsing, normalizes/deduplicates outputs more defensively, and supports heuristic fallback through a dedicated extractor class.
```


### Exercise 4: Use Agentic Mode to Automate a Small Task
Prompt: 
```
Your are a helpful coding assistant. And your work is two parts:
1. Integrate the LLM-powered extraction as a new endpoint. Update the frontend to include an "Extract LLM" button that, when clicked, triggers the extraction process via the new endpoint.

2. Expose one final endpoint to retrieve all notes. Update the frontend to include a "List Notes" button that, when clicked, fetches and displays them.
``` 

Generated Code Snippets:
```
TODO: List all modified code files with the relevant line numbers.
app/routers/action_items.py:
 - Line 36 - 56
 - Line 76 - 92
```


### Exercise 5: Generate a README from the Codebase
Prompt: 
```
TODO
``` 

Generated Code Snippets:
```
TODO: List all modified code files with the relevant line numbers.
```


## SUBMISSION INSTRUCTIONS
1. Hit a `Command (⌘) + F` (or `Ctrl + F`) to find any remaining `TODO`s in this file. If no results are found, congratulations – you've completed all required fields. 
2. Make sure you have all changes pushed to your remote repository for grading.
3. Submit via Gradescope. 