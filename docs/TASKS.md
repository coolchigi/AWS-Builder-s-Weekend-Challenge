# Daily Lexicon — prod-level finish tracker

Challenge deadline: **Aug 24, 2026, 1:00 PM PT.** First 101 qualifying entries win.

## To ship a production-quality entry

- [x] 1. Architecture diagram (SVG + PNG) in `docs/`
- [x] 2. Structured logging + robust error handling in the Lambda
- [x] 3. Bedrock call retries with backoff (throttling-safe)
- [x] 4. Idempotency: exactly one word per day, safe to re-run
- [x] 5. Validate the model's output (required keys, retry on malformed)
- [x] 6. Least-privilege IAM (scope Bedrock to foundation models)
- [x] 7. Unit tests (pytest) for the pure logic — 16 tests
- [x] 8. GitHub Actions CI (tests + cfn-lint)
- [x] 9. LICENSE + README polish (badges, embed diagram)
- [x] 10. Commit + push everything

## Still on you (needs your AWS account)

- [ ] Enable Bedrock Nova access in us-east-1
- [ ] `sam build && sam deploy --parameter-overrides NotifyEmail=coolchigi0031@gmail.com`
- [ ] Confirm SNS email, invoke a few times to seed the archive
- [ ] Screenshot the page + email
- [ ] Publish the article, submit early
