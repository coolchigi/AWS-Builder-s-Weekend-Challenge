<!--
SHOWCASE ARTICLE - copy the content below into the AWS Builder Center editor.
Status: Daily Lexicon (roost-word) is deployed and live. Flight Watch pending deploy.
Before you publish:
  1. Deploy the flight stacks, then paste the Flight Watch SiteURL below.
  2. Upload docs/architecture.png where the diagram is referenced.
  3. Add a screenshot of a real page + a real email for each app.
  4. Fill in the builder you're tagging at the end.
Title and tag are exact per the challenge terms. No city/country named, by design.
-->

**Title:** Weekend Showcase Challenge: Roost

**Tag:** #application

## Vision and what it does

Last month I built Daily Lexicon, a little agent that teaches me one uncommon word
every morning before I've even had coffee. It picks a word, ties it to the date and
the weather in my city, writes a tiny poem, and drops it on a web page and in my
inbox. I never open anything. It just shows up.

Building it, I noticed something. Almost none of the code was about words.

The word part was one small file. Everything else was plumbing that any always-on
agent needs: wake up on a schedule, look at what you did before, do one useful
thing, save the result, put it somewhere I can see it, and email me when it matters.
That plumbing is the actual product. The word was just the first thing I plugged
into it.

So for the finale I pulled that plumbing out into a platform and called it Roost.
Roost runs always-on agents. An app on Roost wakes on a schedule, checks what it saw
last time, does its one job, writes a page, and emails me only if something changed.
That part is written once. To build a new app I write one adapter file and deploy it
as its own stack.

Then I proved it by building a completely different second app in an afternoon.

**Flight Watch.** I'm booking flights for a trip later this year, and I was tired of
manually checking fares. Flight Watch watches a route, remembers every price it has
ever seen, and emails me only when it's a genuine new low or a real drop. Not a price
every six hours. Just the ones worth acting on. It runs two routes right now, each as
its own stack.

Two apps. One teaches a word, one watches a fare. The only thing they share is Roost.

## How I built it

The core is six methods. Every app fills them in: `collect` (sense something),
`reason` (make one record from it), `is_duplicate` (skip repeats), `is_noteworthy`
(is this worth an email), `email`, and `pages` (how the site reads). The Lambda
handler knows only those six methods. It has no idea whether it's running words or
flights. Daily Lexicon became one adapter behind that interface, and Flight Watch
became another. The handler didn't change at all between them.

Here's the whole contract, `src/roost/tracker.py`:

```python
class Tracker(ABC):
    slug: str  # picks the adapter and names the app

    @abstractmethod
    def collect(self) -> dict: ...                  # sense the world (weather, a price)
    @abstractmethod
    def reason(self, ctx, history) -> dict: ...      # turn context + memory into one record
    @abstractmethod
    def is_duplicate(self, record, history) -> bool: ...  # already stored? skip the save
    @abstractmethod
    def is_noteworthy(self, record, history) -> bool: ... # worth an email?
    @abstractmethod
    def email(self, record, url) -> tuple[str, str]: ...  # (subject, body)
    @abstractmethod
    def pages(self, record, history) -> dict: ...    # {path: html} for the S3 site
```

And here's the entire orchestrator, `src/app.py`. Notice it never mentions words or
fares. It just runs the loop against whichever adapter the `ADAPTER` env var selects:

```python
def handler(event, context):
    adapter = load(os.environ["ADAPTER"])        # word? flight? chosen at deploy
    past = store.history(table)                  # 1. remember
    ctx = adapter.collect()                      # 2. sense
    record = adapter.reason(ctx, past)           # 3. reason
    fresh = event.get("force") or not adapter.is_duplicate(record, past)
    if fresh:
        store.save(table, record)                # 4. keep
    url = store.publish(bucket, adapter.pages(record, [record, *past]))  # 5. publish
    if fresh and adapter.is_noteworthy(record, past):
        notify.send_alert(topic, *adapter.email(record, url))           # 6. alert
```

That is the platform. Everything else is an adapter or a template parameter.

The biggest decision was how far to share. I could have run every app in one big
stack with a shared table and one function routing between them. I didn't. Each app
is its own CloudFormation stack with its own Lambda, its own table, and its own
site. The core library is shared as code, not as a running server. That means a bad
deploy to Flight Watch can't touch Daily Lexicon, and I never migrate one app's data
to add another. Adding a third app is a new file and a `sam deploy --config-env`, and
the others never know it happened.

Flight Watch was the real test of the design, because it isn't creative like the
word app. It doesn't always talk to a model, it fetches a number, compares it to
memory, and mostly stays quiet. Getting "quiet by default" right was the interesting
part. The whole alert policy is one function:

```python
def is_noteworthy(self, record, history):
    prices = _past_prices(history)
    if not prices:
        return True                      # first reading: send a baseline
    price, prev_min, recent = record["price"], min(prices), prices[0]
    drop = (recent - price) / recent * 100 if recent else 0
    return price < prev_min or drop >= self.drop_pct  # new low, or a real drop
```

Everything that doesn't clear that bar is just recorded and shown on the page,
never emailed.

Then the data source died under me. I first built Flight Watch on the Amadeus flight
API, and partway through the build Amadeus closed its free developer tier. That would
have sunk the app if the fare source had been wired straight into the logic. It
wasn't. `collect` just asks for a price, and the source sits behind a swap point,
tried in order:

```python
def collect(self):
    return (_serpapi_cheapest(...)     # Google Flights: price + Google's own read
            or _duffel_cheapest(...)   # fallback provider
            or _mock_fare(...))        # always demoable, no keys
```

So losing Amadeus cost me that one function, not the app. It runs on Google Flights
now (through a search API), with Duffel and a mock feed behind it. If any of them
dies, the next is one more single file.

Google Flights turned out to be more than a replacement. It returns Google's own read
on the fare, a `price_level` of low, typical, or high, and a typical price range. So
instead of only knowing "cheaper than *I've* seen," the agent can say "this is a low
fare, below the typical range" on its very first run, and that read is what it hands
to the model for the Buy/Wait call. Judgment from day one, not after weeks of data.

I kept the same habits from last month. The big one: ask Bedrock for JSON, then don't
trust it. Parse it (tolerating a model that wraps JSON in prose or a code fence),
check every field is there, and regenerate if it isn't. Nothing malformed reaches a
page or an inbox:

```python
for attempt in range(1, attempts + 1):
    text = _invoke(model_id, system_prompt, user_prompt)
    try:
        packet = _parse_json(text)          # pull the JSON object out of the reply
        _validate(packet, required_keys)    # every required key present and non-empty?
        return packet
    except ValueError:
        continue                            # malformed, try once more
raise ValueError("model output invalid after retries")
```

The rest of the habits: keep the Lambda dependency-free, just boto3 and the standard
library, so `sam build` never touches pip. And least privilege on the IAM, scoped to
foundation models, not a wildcard.

## Why I didn't use an agent framework

I got asked this a lot, so it's worth being clear, because "agent" gets used for two
pretty different things:

- **The tool-calling kind.** The model plans, calls a tool, reads the result, calls
  another, and loops until it's done. This is what Strands and Amazon Bedrock Agents
  are built for, and they're great at it.
- **The autonomous kind.** It wakes on its own, reads what it remembers, does one
  useful thing, and goes back to sleep.

Roost is the second kind. Each wake is a single Bedrock call, no tool loop, no
planning. So a framework would be weight I never use. The Lambda stays boto3 plus the
standard library, and `sam build` never has to touch pip.

I'd reach for Strands the moment an app actually needs to chain tools, say, search
fares, then check a visa rule, then hold a booking. Flight Watch doesn't. It fetches
a number, compares it to memory, and decides. Use the tool the job needs. This job
didn't need a framework.

## AWS services used and architecture overview

![Roost architecture: one shared core and template produce isolated per-app stacks. Daily Lexicon and Flight Watch share the same lifecycle (EventBridge, Lambda, Bedrock, DynamoDB, S3, SNS) and differ only in their adapter, data source, schedule, and alert rule.](architecture.png)

| Service | Role |
|---|---|
| Amazon EventBridge | Wakes each app on its own schedule. Word daily, flight every 6 hours. |
| AWS Lambda (Python 3.12) | Runs the shared Roost lifecycle. The adapter is the only per-app code. |
| Amazon Bedrock (Nova Lite) | Writes the word and verse; writes Flight Watch's one-line verdict. |
| Amazon DynamoDB | Each app's memory. No repeats for words, full price history for fares. |
| Amazon S3 | The public page each app publishes. |
| Amazon SNS | Emails me, on every new word and only on a real fare drop. |
| AWS SAM | One parameterized template. `--config-env` picks the app and its stack. |

The shape is identical for both apps. The only things that differ are the adapter
file, the external data source, the schedule, and the rule for when an email is
worth sending. That short list is everything you write to add a new app.

## Add your own app in one file

This is the part I'd want a new builder to take and run with. An app on Roost is one
adapter that fills in six methods (from `src/roost/tracker.py`): `collect`, `reason`,
`is_duplicate`, `is_noteworthy`, `email`, and `pages`. Say you want to watch a GitHub
repo's star count:

```python
# src/adapters/stars.py
from roost.tracker import Tracker

class StarTracker(Tracker):
    slug = "stars"
    title = "Star Watch"

    def collect(self):
        # ask the GitHub API for the current count
        return {"stars": current_stars(self.repo)}

    def reason(self, ctx, history):
        # one record; it needs a sortable id and a date
        return {"id": now_iso(), "date": today(), "stars": ctx["stars"]}

    def is_noteworthy(self, record, history):
        # stay quiet unless it just crossed a 1,000-star milestone
        return crossed_thousand(record, history)

    # is_duplicate, email, pages fill in the rest
```

Then three lines of wiring:

- add `StarTracker` to `_CLASSES` in `src/adapters/__init__.py`
- add `stars` to the `Adapter` values and a config-env in `samconfig.toml`
- `sam deploy --config-env stars`

That's a brand new always-on agent: its own stack, its own memory, its own page, and
every bit of the reliability I already wrote (JSON validation, retries, idempotent
sends, least-privilege IAM). No new infrastructure. The other apps never know it
showed up. When Amadeus died, this is the seam that saved me: the fare source is just
one more swappable piece behind `collect`.

## What I learned across the summer

The summer went idea, then creative app, then agent, and it quietly taught me the
same lesson three times before I actually heard it.

The first time, building Daily Lexicon, I assumed the model call would be the
interesting part. It wasn't. The memory was. An agent that reads what it did
yesterday before it acts is just a different thing than one that doesn't, even if
it's a few lines and one table.

The second time was this weekend, pulling Roost out of that app. The thing I was
proud of in Daily Lexicon, the reliability, the retries, the "never publish junk,"
the "never email me twice," was never really about words. It was infrastructure I
had accidentally written for one app. Once I saw that, building the second app took
an afternoon instead of a weekend.

The third lesson is the one I'll keep: I've been building apps when I should have
been building the thing underneath the app. Flight Watch isn't impressive because
it checks a flight price. It's impressive because it cost me almost no new code. The
platform is the part worth keeping. The apps just prove it works.

The last thing: staying quiet is a feature. An agent that emails you on every run
gets muted within a week. One that only speaks when it has something real is one you
leave running for months. Daily Lexicon earns a message every day. Flight Watch has
to earn each one.

## Link to app or repo

- **Daily Lexicon (live):** http://roost-word-sitebucket-pmgueatufzxf.s3-website-us-east-1.amazonaws.com
- **Flight Watch (live):** http://roost-flight-sitebucket-xuummxvihdrq.s3-website-us-east-1.amazonaws.com
- **Code:** https://github.com/coolchigi/AWS-Builder-s-Weekend-Challenge

The repo has the Roost core, both adapters, the single SAM template, tests, and CI.

## A builder who inspired me

_<Tag a builder here. e.g. @lewissawe, whose "The Museum That Grows" was the
top-voted agent last week and made me want mine to feel less like a cron job.>_
