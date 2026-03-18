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
week2/tests/test_extract.py:22 - 116 
```

### Exercise 3: Refactor Existing Code for Clarity
Prompt: 
```
TODO
``` 

Generated/Modified Code Snippets:
```
TODO: List all modified code files with the relevant line numbers. (We anticipate there may be multiple scattered changes here – just produce as comprehensive of a list as you can.)
```


### Exercise 4: Use Agentic Mode to Automate a Small Task
Prompt: 
```
TODO
``` 

Generated Code Snippets:
```
TODO: List all modified code files with the relevant line numbers.
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