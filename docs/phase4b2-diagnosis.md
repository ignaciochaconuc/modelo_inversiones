# Phase 4B.2: initial diagnosis (before algorithm changes)

Case `3108bd96b8c21e06f7e4dec192021bce4a3a5aaf418580690696665d3eb66921`
is present in the original 500-article source snapshot
`85072aca40381289e0109b6e28769bc31886b2fc54442dbcc0511569360118d2`.
The original technical review records `stored_pipeline_pair`, confirmed by
one matching entry in snapshot pair_evidence. It was not an audit-only score.

Reexecuting the frozen v1 classifier yields `different`, global cosine
0.550364706926844, headline cosine 0.5789473684210527, publication gap
10.644166666666667 hours, and `insufficient_event_or_editorial_evidence`.
Both sides resolve corporate entity `apple` and security `apple-common`;
their provider ticker and corporate alias evidence agree. Both articles and
entity links are eligible at the original strict decision time.

Full-text anchors: left event vocabulary empty, right `product`; both numeric
sets contain only `18`, and both action sets are empty. Thus the factual
conflict guard does not reject this pair. Shared-event evidence fails because
there is no common event kind and headline similarity is below 0.65.

The editorial branch requires identical headline cores AND global cosine
at least 0.90 AND headline cosine at least 0.65. All three fail. Tokenization
treats `iphone18` as one word but `iphone 18` as two; `soft` and `sluggish`
differ, and terminal `- Nikkei` adds an attribution token. Punctuation alone
is already handled. Summaries have 115 versus 243 characters and different
editorial wording: fixing the headline alone cannot guarantee global cosine
0.90. This is a classification failure, not candidate generation, entity
resolution or temporal exclusion. No blocking or event-clustering redesign
is justified by this case.

Authorized targeted design: preserve v1 dispatch; introduce v1.1 with three
explicit headline normalizations (iPhone-number spacing, soft/sluggish demand,
terminal dash-Nikkei attribution) and an additional editorial route requiring
exact normalized substantive headline equality, resolved common entity,
unchanged time/minimum-text guards and compatible factual anchors. Global
cosine remains reported, not lowered. Normalized differences must never be
called exact duplicates. Summary factual updates remain guarded. Shared-event
logic, complete-link, candidate blocks and budgets remain unchanged.

All original 36 pairs now have development/diagnostic status via a new
sidecar, not mutation of original evidence. Their AI-assisted adjudication is
not independent human ground truth. The original evaluation is locally
present but blind human fields remain blank: retain that provenance and do
not fill them from classifier output.

Reproduction: `python scripts/run_phase4b2_offline.py --diagnose-only`.
The script checks original scores, stored membership, entities, anchors and
single-rule ablations entirely offline. Provider text remains local/ignored.
