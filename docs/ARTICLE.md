<!--
FINAL ARTICLE - copy the content below into the AWS Builder Center editor.
The live URL and repo link are already filled in. Before you publish:
  1. Upload docs/architecture.png where the diagram is referenced.
  2. Add a screenshot of your real page + email (swap the Petrichor sample for
     your own first word if you like).
Title and tag are exact per the challenge terms.
-->

**Title:** Weekend Creative Agent Challenge: Daily Lexicon

**Tag:** #agents

## Vision and what it does

I read a lot, so I run into great words all the time, and then I forget them. I
don't really need a dictionary for that. I need something that just hands me a new
word each day so I don't have to remember to go looking.

So I built Daily Lexicon. It teaches me one word a day and I never have to open
anything.

Every morning it wakes up on its own, picks an uncommon word, and ties it loosely
to the date and the weather here in Ottawa. I get the word, how to say it, what it
means, where it came from, a sentence, and a little poem that actually uses it. By
the time I've got coffee, it's already sitting on a page and in my inbox. That's
the whole idea. The best tool is the one you never have to open.

Here's a real one it made:

> **Petrichor** /ˈpɛtrɪkɔːr/ · noun
> The earthy scent produced when rain falls on dry soil.
> *Origin:* Greek *petra* (stone) and *ichor*, the fluid said to run in the veins
> of the gods.
> *In a sentence:* "The first storm of August broke, and petrichor rose from the
> warm pavement like a memory."
>
> *Warm stone remembers every drought,*
> *then breathes its petrichor aloud,*
> *a summer psalm the clouds let out.*
>
> — for a warm, rainy summer Saturday

## How I built it

The thing that makes this an agent and not just a cron job is that it remembers.

A word-a-day script with no memory repeats itself fast, and it never gets more
interesting. So before it picks anything, the Lambda pulls every word it has
already used out of DynamoDB and tells the model: don't reuse these, go somewhere
new. That one step is the difference between a random generator and something that
feels like it is keeping track.

I also wanted it to notice what day it is. Each run grabs the date, the season,
and Ottawa's current weather, so a rainy Saturday gets a different word and mood
than a cold Monday. The weather actually shows up in the poem, not just as a label.

I kept the Lambda dependency-free on purpose. Just boto3, which is already in the
runtime, and the standard library. So `sam build` never has to touch pip and it
builds the same every time.

The part that took the most fiddling was getting output clean enough to render. A
page and an email need real structure, not a paragraph of prose. So I ask Bedrock
for JSON and then don't trust it. The code copes with the model wrapping JSON in a
code block or a sentence, checks that every field is actually there, and asks again
if something is missing. Nothing broken makes it to the page. Add retries for
throttling and a check so a re-run never emails me twice, and it is something I am
happy to leave running for months.

## AWS services used and architecture overview

![Daily Lexicon architecture: EventBridge wakes a Lambda that reads and writes DynamoDB for memory, calls Amazon Bedrock Nova to create the word and verse, then publishes a page to S3 and emails it via SNS.](architecture.png)

| Service | Role |
|---|---|
| Amazon EventBridge | Daily schedule that wakes the agent, nothing idles |
| AWS Lambda (Python 3.12) | The orchestrator: remember, sense, create, publish |
| Amazon Bedrock (Nova Lite) | Picks the word and writes the verse |
| Amazon DynamoDB | The agent's memory, so it never repeats |
| Amazon S3 | Hosts the page waiting for me each morning |
| Amazon SNS | Emails me the word |
| AWS SAM | Infrastructure as code for the whole thing |

It is one Lambda doing everything: read the memory, check the day, one Bedrock
call, then write a page and send an email. I kept it a single function instead of
a Step Functions workflow because the steps run start to finish in a straight
line. A state machine would have been ceremony, not reliability.

## What I learned

This changed how I think about the word "agent." I assumed the model call would be
the interesting part. It wasn't. Bedrock's Converse API made that bit almost
boring, which I mean as a compliment. The part that mattered was the memory. An
agent that looks at what it did yesterday before it acts is just a different thing
than one that doesn't, even if it is only a few lines of code and one table.

The other lesson: don't trust model output by default, especially for something
that publishes on its own while you are asleep. Parse it, check it, regenerate if
it is off. That is what makes "unattended" actually safe.

And I am sold on keeping small agents dependency-free when I can. Using urllib
instead of a nicer HTTP library cost me a little polish, but the build is dead
simple and reproducible. For something meant to run untouched, I will take that
trade.

## Link to app or repo

- **Live page:** http://weekend-agent-sitebucket-okt65m9uniqf.s3-website-us-east-1.amazonaws.com
- **Code:** https://github.com/coolchigi/AWS-Builder-s-Weekend-Challenge

The repo has the full SAM template, the source, tests, CI, and setup notes.
