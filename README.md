# Daily Lexicon

An always-on creative agent for the AWS Builder Center **"Set your creative app
free"** weekend challenge (Level 200).

Every day, EventBridge wakes a Lambda that reasons with Amazon Bedrock (Nova) to
conjure one uncommon, beautiful word, themed to the date and weather, with a
definition, etymology, an example, and a tiny original poem. It remembers past
words in DynamoDB so it never repeats and evolves over time, publishes a web
page to S3, and emails you the word. You never open an app, the word is just
waiting for you.

## Architecture

```
EventBridge (daily) --> Lambda --> Bedrock (Nova)   conjure the word + verse
                          |  \---> DynamoDB          memory: never repeat, evolve
                          |------> S3 static site    the page waiting for you
                          \------> SNS               emails you the word
```

## Prerequisites

- AWS account with **Bedrock model access enabled** for Amazon Nova in
  `us-east-1` (Bedrock console -> Model access -> enable Nova Lite).
- AWS SAM CLI + configured credentials.

## Deploy

```bash
sam build
sam deploy --parameter-overrides NotifyEmail=you@example.com
```

Confirm the SNS subscription email once. `WeatherLatLon` defaults to Ottawa;
override it for another city.

## Create today's word right now (don't wait for the schedule)

```bash
FN=$(aws cloudformation describe-stacks --stack-name weekend-agent \
  --query "Stacks[0].Outputs[?OutputKey=='FunctionName'].OutputValue" --output text)
aws lambda invoke --function-name "$FN" /dev/stdout
```

Then open the site URL:

```bash
aws cloudformation describe-stacks --stack-name weekend-agent \
  --query "Stacks[0].Outputs[?OutputKey=='SiteURL'].OutputValue" --output text
```

Invoke it a few times to seed the archive before you screenshot it.

## Submission checklist (challenge closes Aug 24, 2026 1:00 PM PT)

- [ ] Public GitHub repo with this code
- [ ] `sam deploy` succeeds, SNS subscription confirmed, live site loads
- [ ] Invoked a few times so the archive has several words
- [ ] Screenshots of the page + the email (proof it works)
- [ ] Article published from `docs/ARTICLE_TEMPLATE.md`, 500+ words
- [ ] Title contains exactly: `Weekend Creative Agent Challenge: Daily Lexicon`
- [ ] Tag `#agents` added
- [ ] Submitted early (first 101 qualifying entries win)

## Re-skin note

The creative concept lives entirely in `src/task.py`. Everything else is
reusable infrastructure for any future weekend challenge.

## If the public S3 site is blocked

Some accounts turn on **account-level** S3 Block Public Access, which overrides
the bucket. If the site URL 403s, either disable account-level BPA (S3 console
-> Block Public Access settings for this account) or just use screenshots/video
of the page rendered locally, the challenge accepts screenshots or video as
proof of functionality.
