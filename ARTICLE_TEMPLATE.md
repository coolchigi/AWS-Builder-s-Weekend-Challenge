# Builder Center article draft — Daily Lexicon

A near-complete draft. Fill the [bracketed] bits with your own voice, especially
"What I learned", reviewers can tell genuine reflection from filler, and it's
one of the required sections. Keep it over 500 words (this draft already is).

> Before publishing, confirm against the challenge terms:
> - Title contains: `Weekend Creative Agent Challenge: Daily Lexicon`
> - Tag added: `#agents`
> - A working public link to your app or repo

---

**Title:** Weekend Creative Agent Challenge: Daily Lexicon

**Tag:** #agents

## Vision & What It Does

I read a lot, and I kept meeting words I loved and then forgot by the next
chapter. So I built **Daily Lexicon**, an always-on agent that teaches me one
new word every day without my ever opening an app.

Each morning, before I'm awake, the agent conjures a single uncommon, beautiful
English word, themed to the date and the day's weather. It presents the word
with its pronunciation, definition, etymology, an example sentence, and a tiny
original poem that uses the word and echoes the mood of the day. By the time I
pour my coffee, the word is already waiting, on a web page and in my inbox. The
best tool really is the one you never have to open.

Crucially, it has a memory. It knows every word it has already taught me, so it
never repeats itself, and over time it drifts into new territory. It is less a
dictionary and more a patient tutor with a sense of atmosphere.

## How I Built It

I started from a reusable "always-on agent" pattern: a scheduled trigger, a
Lambda brain, a reasoning model, and somewhere to put the output. The whole
creative concept lives in one file, so the architecture is reusable for other
ideas.

The interesting decisions were about making it feel alive rather than random:

- **Memory before generation.** The Lambda first reads the words it has already
  used from DynamoDB and passes them to the model as a "do not repeat" list.
  That single step is what turns a random word generator into an agent that
  evolves.
- **Sensing the day.** It pulls the date, season, and current weather (via a
  free weather API) so the word and its poem quietly match the moment, a warm
  rainy Saturday reads differently from a cold clear Monday.
- **Structured output.** I ask Bedrock to reply as strict JSON so I can render
  it reliably into both a web page and an email.

The main challenge was [describe one real thing you hit, e.g. getting Bedrock
model access enabled, IAM permissions for S3 + DynamoDB, or making the JSON
parse robust, and how you solved it].

## AWS Services Used / Architecture Overview

- **Amazon EventBridge** — a daily schedule that wakes the agent, no human input.
- **AWS Lambda (Python 3.12)** — the orchestrator: remember, sense, create, publish.
- **Amazon Bedrock (Amazon Nova Lite)** — reasons over the day and the memory to
  choose the word and write the verse.
- **Amazon DynamoDB** — the agent's memory of every word taught, for
  non-repetition and evolution.
- **Amazon S3** — hosts the static page that's waiting for me each morning.
- **Amazon SNS** — emails me the word so it reaches me wherever I am.

```
EventBridge (daily) --> Lambda --> Bedrock (Nova)
                          |  \---> DynamoDB  (memory)
                          |------> S3        (the page)
                          \------> SNS       (the email)
```

## What I Learned

[Two or three honest sentences. Ideas to draw from: giving an agent even a tiny
memory changes it from a toy into something that evolves; the Bedrock Converse
API made swapping models trivial; how cheap Nova Lite is on Free Tier for a
daily job; the first AWS service that was new to you here.]

## Link to App or Repo

- **Live page:** [your S3 website URL]
- **Code:** [your public GitHub repo URL]

[Add 1-2 screenshots of the page and the email as proof it works. Verify the
repo is public in an incognito window before submitting.]
