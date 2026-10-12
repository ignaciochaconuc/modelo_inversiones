# ADR-029: Cache-write accounting and offline smoke preparation

## Status

Accepted for the explicitly requested Phase 4C.2 preparation/correction.
No live inference is authorized by this preparation. Phase 4C.2 remains
`implemented_pending_external_review`; Phase 4C.3 remains `not_started`.
ADR-028 and all prior evidence are preserved as history.

## Reason

The original three-price calculation treats all non-read input as ordinary
input. For GPT-5.6 Luna this undercounts cache writes: their rate is 1.25 times
ordinary input. Its reservation also omits the more expensive write lane.
Responses additionally expects nested `reasoning.effort`, not the flat
Chat Completions-style `reasoning_effort` parameter.

## Decision and compatibility

Opt-in `news-inference-settings-v2`, `openai-responses-settings-v2`,
`news-token-prices-v2` and `news-inference-attempt-v2` bind the new behavior.
Original v1 settings serialization, three-price PricingRegistry API, LLMResponse,
4C.1 contracts, recorded responses and replay remain unchanged. Readers accept
both attempt versions; v2 stores cache-write counts in the outer attempt record,
not in the frozen inner replay contract. Versions cannot be mixed silently.
The single-article real smoke CLI requires v2 and one attempt; v1 remains readable
for offline reconstruction, not accepted as a real-smoke pricing profile.

For total input I, cached reads R, cache writes W and output O:

`cost = ((I-R-W)*input_price + R*read_price + W*write_price + O*output_price)/1e6`.

Counts must be nonnegative integers and `R+W <= I`. Missing write telemetry is
unknown, never zero. Unknown cost retains the full durable reservation.
Malformed/overlapping reported counts and usage outside the verified price band
halt without retry and are not priced using an inapplicable tariff.
The reservation uses the highest of ordinary/read/write input rates plus capped
output. Larger-than-short-context inputs are blocked before attempting inference;
long-context surcharges are not guessed or silently omitted. Standard service
tier is explicit, with no tools, background processing or stored responses.

`--validate-only` shares pure transport/reservation preparation with execution.
It checks configuration, prices/validity, PIT eligibility, capabilities, context,
one-attempt policy and budgets without creating persistence or calling a provider.
It reports only identifiers, parameters and bounds, never source text or secrets.
The flag is mutually exclusive with real confirmation. Account access/API-key
validity cannot be established offline.

## Official sources (checked 2026-10-12)

- [GPT-5.6 Luna](https://developers.openai.com/api/docs/models/gpt-5.6-luna):
  `none`, structured outputs, Responses, 1,050,000 context, maximum input 922,000,
  output 128,000; short-context rates 0.20/0.02/0.25/1.20 USD per million.
- [Prompt caching](https://developers.openai.com/api/docs/guides/prompt-caching):
  disjoint reads/writes, `usage.input_tokens_details.cache_write_tokens`,
  implicit/explicit caching and minimum TTL `30m` for GPT-5.6. This is not a
  guaranteed maximum remote retention or a deletion mechanism.
- [Responses](https://developers.openai.com/api/reference/resources/responses/methods/create):
  reasoning object, strict text format, output cap and standard service tier.
- [Structured Outputs](https://developers.openai.com/api/docs/guides/structured-outputs):
  required properties, closed objects, refusal/incomplete handling; structural
  validity does not establish factual correctness.
- [Data controls](https://developers.openai.com/api/docs/guides/your-data):
  `store:false` does not establish Zero Data Retention; default abuse monitoring
  can retain content for up to 30 days, subject to documented exceptions.

See [smoke preparation and cleanup](../phase4c2-smoke-preparation.md).
