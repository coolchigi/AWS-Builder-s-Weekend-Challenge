# Builder Center article draft — Daily Lexicon

A near-complete draft. Fill the [bracketed] bits in your own voice, especially
"What I learned" and the one real challenge, reviewers can tell genuine
reflection from filler, and it's a required section. Keep it over 500 words
(this draft already is).

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

Every morning, before I'm awake, the agent conjures a single uncommon, beautiful
English word, themed to the date and Ottawa's weather that day, and presents it
with its pronunciation, definition, etymology, an example sentence, and a tiny
original poem that uses the word. By the time I pour my coffee, the word is
already waiting, on a web page and in my inbox. The best tool is the one you
never have to open.

Here's a real morning's output:

> **Petrichor** /ˈpɛtrɪkɔːr/ · noun
> The earthy scent produced when rain falls on dry soil.
> *Origin:* Greek *petra* (stone) + *ichor*, the fluid in the veins of the gods.
> *In a sentence:* "The first storm of August broke, and petrichor rose from the
> warm pavement like a memory."
>
> *Warm stone remembers every drought,*
> *then breathes its petrichor aloud,*
> *a summer psalm the clouds let out.*
>
> — for a warm, rainy summer Saturday

[Replace with a screenshot of your own deployed page and the email, that's your
proof of functionality.]

## How I Built It

The design decision that makes this an *agent* rather than a cron job that calls
an LLM once is memory. A daily word generator with no memory repeats itself and
never grows. So before it generates anything, the Lambda reads every word it has
already taught out of DynamoDB and hands the model that list with a single
instruction: never reuse these, and drift into new territory over time. That one
feedback loop is what turns a random word picker into something that behaves
like it's paying attention across days.

The second decision was to make it *feel* like it knows what day it is. Each run
pulls the date, season, and Ottawa's current weather from a free API, so a warm
rainy Saturday yields a different word and mood than a cold clear Monday. The
weather is woven into the poem, not just stamped on top.

I also kept the Lambda dependency-free, only `boto3` (already in the runtime)
and the standard library, so `sam build` never touches `pip` and the whole thing
is trivially reproducible.

The main challenge was [describe one real thing you hit, e.g. enabling Bedrock
Nova model access, getting the model to return clean JSON I could render, the
DynamoDB dedup-key design, or S3 public-website access, and how you solved it].

## AWS Services Used / Architecture Overview

| Service | Role |
|---|---|
| Amazon EventBridge | Daily schedule that wakes the agent, no human input |
| AWS Lambda (Python 3.12) | Orchestrator: remember, sense, create, publish |
| Amazon Bedrock (Nova Lite) | Chooses the word and writes the verse |
| Amazon DynamoDB | The agent's memory, for non-repetition and evolution |
| Amazon S3 | Hosts the static page waiting for me each morning |
| Amazon SNS | Emails me the word wherever I am |
| AWS SAM | Infrastructure as code for the whole stack |

```
EventBridge (daily) --> Lambda --> Bedrock (Nova)
                          |  \---> DynamoDB  (memory)
                          |------> S3        (the page)
                          \------> SNS       (the email)
```

One Lambda is the whole orchestration layer: it reads its memory, senses the
day, makes one Bedrock call, and produces two outputs, a web page and an email.
Keeping it a single function instead of a Step Functions workflow was a
deliberate weekend-scope call, the sequence is linear enough that a state
machine would add ceremony without adding reliability.

## What I Learned

[Two or three honest sentences. Ideas to draw from: giving an agent even a tiny
memory changes it from a toy into something that evolves; the Bedrock Converse
API made model choice almost boring, in a good way; how cheap Nova Lite is on
Free Tier for a daily job; the first AWS service that was new to you here.]

## Link to App or Repo

- **Live page:** [your S3 website URL]
- **Code:** https://github.com/coolchigi/AWS-Builder-s-Weekend-Challenge

[Verify the repo is public in an incognito window before submitting.]
