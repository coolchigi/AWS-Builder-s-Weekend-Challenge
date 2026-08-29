# Roost

[![CI](https://github.com/coolchigi/AWS-Builder-s-Weekend-Challenge/actions/workflows/ci.yml/badge.svg)](https://github.com/coolchigi/AWS-Builder-s-Weekend-Challenge/actions/workflows/ci.yml)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)

A small platform for **always-on agents** on AWS. Every app wakes on a schedule,
senses the world, reasons over what it remembers, publishes a page, and emails
you when something changed. That lifecycle is written once. An app is one adapter
file plus a config, deployed as its own isolated stack.

Two apps ship on it today:

- **Daily Lexicon** — one uncommon, beautiful word a day, themed to the weather.
- **Flight Watch** — tracks one route's fare and emails you only on a real drop.

They are genuinely different jobs. They share everything except the amber cells:
the adapter, the data source, the schedule, and the rule for when an email is
worth sending.

## Architecture

```
                    PLATFORM CORE  (src/roost/, written once)
        wake -> sense -> reason -> remember -> publish -> alert
        agent.py (Bedrock)  store.py (DynamoDB + S3)  notify.py (SNS)
                                  |
              the Tracker port    |    template.yaml (one parameterized stack)
                                  |
        +-------------------------+--------------------------+
        |                                                    |
   adapters/word.py                                   adapters/flight.py
   ADAPTER=word                                       ADAPTER=flight
        |                                                    |
   stack: roost-word                                 stack: roost-flight
   EventBridge (daily)                               EventBridge (rate 6h)
   Lambda -> Bedrock Nova                            Lambda -> Amadeus + Bedrock
          -> DynamoDB (memory)                              -> DynamoDB (memory)
          -> S3 site                                        -> S3 site
          -> SNS email (every word)                         -> SNS email (on a drop)
```

Each app is its own CloudFormation stack: its own Lambda, table, and public S3
site. One app can't break another.

## What's platform vs what's an app

| Layer | Files | You write it |
|---|---|---|
| **Platform** | `src/roost/` + `template.yaml` | once |
| **An app** | one file in `src/adapters/` + a config-env | per app |

An adapter implements six methods (`src/roost/tracker.py`): `collect`, `reason`,
`is_duplicate`, `is_noteworthy`, `email`, `pages`.

## Prerequisites

- AWS account with **Bedrock model access enabled** for Amazon Nova in
  `us-east-1` (Bedrock console -> Model access -> enable Nova Lite).
- AWS SAM CLI + configured credentials.
- (Flight Watch, optional) a free **Amadeus Self-Service** key/secret. Without
  it the app runs on a mock fare feed, so it is still fully demoable.

## Deploy an app

```bash
sam build

# Daily Lexicon
sam deploy --config-env word --parameter-overrides NotifyEmail=you@example.com

# Flight Watch (mock fares)
sam deploy --config-env flight --parameter-overrides NotifyEmail=you@example.com

# Flight Watch (live fares)
sam deploy --config-env flight --parameter-overrides \
  "NotifyEmail=you@example.com AmadeusClientId=xxx AmadeusClientSecret=yyy"
```

Confirm the SNS subscription email once per stack. Flight Watch defaults to
YOW -> LOS in December; override `Route`, `DepartDate`, `ReturnDate`, `Currency`.

## Run it right now (don't wait for the schedule)

```bash
STACK=roost-flight   # or roost-word
FN=$(aws cloudformation describe-stacks --stack-name "$STACK" \
  --query "Stacks[0].Outputs[?OutputKey=='FunctionName'].OutputValue" --output text)
aws lambda invoke --function-name "$FN" --payload '{"force":true}' --cli-binary-format raw-in-base64-out /dev/stdout
```

Then open the site:

```bash
aws cloudformation describe-stacks --stack-name "$STACK" \
  --query "Stacks[0].Outputs[?OutputKey=='SiteURL'].OutputValue" --output text
```

Invoke a few times to seed the archive / price history before you screenshot it.

## Add a third app

1. Write `src/adapters/<name>.py` implementing `Tracker`.
2. Add its class to `_CLASSES` in `src/adapters/__init__.py`.
3. Add an `AllowedValues` entry for `Adapter` and a config-env in
   `samconfig.toml`, then `sam deploy --config-env <name>`.

No new infrastructure. The other apps never know it happened.

## Development

```bash
pip install -r requirements-dev.txt
pytest -q                 # prompts, parsing, validation, price logic, rendering
sam validate --lint       # validate the template
```

CI runs both on every push (see `.github/workflows/ci.yml`).

## Production notes

- **Idempotent:** Daily Lexicon makes one word per day; a retry re-publishes the
  page instead of emailing you twice. Flight Watch skips a redundant save when
  the price is unchanged.
- **Resilient:** Bedrock calls use adaptive retries; malformed model output is
  validated and regenerated before anything publishes. Flight Watch's verdict is
  best-effort and falls back to a computed message if Bedrock is unavailable.
- **Least privilege:** the Bedrock permission is scoped to foundation models.
- **Free-Tier aware:** Flight Watch at every 6h is ~120 Amadeus calls/month,
  well inside the free 2,000. Secrets are template parameters for the weekend;
  move them to Secrets Manager for anything longer-lived.
- **Observable:** structured JSON logs to CloudWatch on every run.
