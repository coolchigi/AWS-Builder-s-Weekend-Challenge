"""Bedrock reasoning via the Converse API, so any model swaps in cleanly.

We ask the model to reply as strict JSON so the handler can act on structured
output instead of parsing prose.
"""

import json
import re

import boto3

_bedrock = boto3.client("bedrock-runtime")


def analyze(model_id: str, system_prompt: str, user_prompt: str) -> dict:
    response = _bedrock.converse(
        modelId=model_id,
        system=[{"text": system_prompt}],
        messages=[{"role": "user", "content": [{"text": user_prompt}]}],
        inferenceConfig={"maxTokens": 900, "temperature": 0.8},
    )
    text = response["output"]["message"]["content"][0]["text"]
    return _parse_json(text)


def _parse_json(text: str) -> dict:
    """Models sometimes wrap JSON in prose or a code fence. Pull the object out."""
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        match = re.search(r"\{.*\}", text, re.DOTALL)
        if match:
            return json.loads(match.group(0))
    raise ValueError(f"Model did not return valid JSON:\n{text[:500]}")
