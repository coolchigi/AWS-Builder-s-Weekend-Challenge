"""Bedrock reasoning via the Converse API, so any model swaps in cleanly.

App-agnostic: the caller passes the prompt and the keys the reply must contain.
Production concerns handled here:
  - adaptive retries on throttling (botocore Config)
  - strict JSON parsing, tolerant of prose/code-fence wrapping
  - output validation with a bounded regenerate loop, so a malformed reply
    never reaches an app.
"""

import json
import logging
import re

import boto3
from botocore.config import Config

logger = logging.getLogger(__name__)

_bedrock = boto3.client(
    "bedrock-runtime",
    config=Config(retries={"max_attempts": 4, "mode": "adaptive"}),
)


def generate(
    model_id: str,
    system_prompt: str,
    user_prompt: str,
    required_keys,
    attempts: int = 2,
    max_tokens: int = 900,
    temperature: float = 0.7,
) -> dict:
    """Generate a validated JSON packet, regenerating up to `attempts` times."""
    last_error = None
    for attempt in range(1, attempts + 1):
        text = _invoke(model_id, system_prompt, user_prompt, max_tokens, temperature)
        try:
            packet = _parse_json(text)
            _validate(packet, required_keys)
            return packet
        except ValueError as err:
            last_error = err
            logger.warning("model output invalid (attempt %d/%d): %s", attempt, attempts, err)
    raise ValueError(f"model output invalid after {attempts} attempts: {last_error}")


def _invoke(model_id, system_prompt, user_prompt, max_tokens, temperature) -> str:
    response = _bedrock.converse(
        modelId=model_id,
        system=[{"text": system_prompt}],
        messages=[{"role": "user", "content": [{"text": user_prompt}]}],
        inferenceConfig={"maxTokens": max_tokens, "temperature": temperature},
    )
    return response["output"]["message"]["content"][0]["text"]


def _parse_json(text: str) -> dict:
    """Models sometimes wrap JSON in prose or a code fence. Pull the object out."""
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        match = re.search(r"\{.*\}", text, re.DOTALL)
        if match:
            try:
                return json.loads(match.group(0))
            except json.JSONDecodeError:
                pass
    raise ValueError(f"no valid JSON object in reply: {text[:200]}")


def _validate(packet: dict, required_keys) -> None:
    missing = [k for k in required_keys if not str(packet.get(k, "")).strip()]
    if missing:
        raise ValueError(f"missing/empty keys: {', '.join(missing)}")
