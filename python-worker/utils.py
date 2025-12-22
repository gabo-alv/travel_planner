import json
import re


def extract_json(text: str):
    """
    Extract and parse JSON from LLM output that may include markdown fences like:
        ```json
        { ... }
        ```
        or
        ``` 
        { ... }
        ```
    Returns a Python object.

    Raises RuntimeError if valid JSON cannot be parsed.
    """

    if not isinstance(text, str):
        raise RuntimeError(f"Expected string LLM output, got: {type(text)}")

    cleaned = text.strip()

    # 1) Remove common ```json ... ``` blocks
    fence_pattern = re.compile(r"```(?:json)?\s*(.*?)```", re.DOTALL)
    matches = fence_pattern.findall(cleaned)

    if matches:
        # Use the first fenced block, most models put JSON there
        cleaned = matches[0].strip()

    # 2) Remove stray backticks (rare cases)
    cleaned = cleaned.replace("```", "").strip()

    # 3) Attempt to parse JSON
    try:
        return json.loads(cleaned)
    except Exception as e:
        raise RuntimeError(
            f"Failed to parse JSON.\nRaw cleaned text:\n{cleaned}\nError: {e}"
        ) from e
