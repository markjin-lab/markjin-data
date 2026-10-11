# X query rule (applies to future days only)

Past raw/<date>/x-queries.md files are immutable archives and are NOT edited. From 2026-10-11 onward, runs follow the spec below (canonical working copy: /workspace/markjin/x-queries.md); each day's raw/<date>/x-queries.md snapshot should record the actual computed start_time values.

# markjin X query set (rolling window; effective 2026-10-11 onward)

Common params (from 2026-10-11): x.search_posts_all with `post.fields=created_at,author_id,public_metrics,entities`, `expansions=author_id,attachments.media_keys`, `user.fields=username`. `entities.urls[]` gives `expanded_url` / `unwound_url` for each t.co link; leads.json primary-source matching must use `expanded_url` (prefer `unwound_url` if present), never the t.co `url`.

**Rolling start_time rule:** `start_time = now − 48h` (UTC ISO 8601, e.g. `2026-10-08T23:11:00Z`); queries 04 and 12 use `now − 96h`. The start_time column below is historical (2026-10-10 run) and is superseded by this rule.

## Capture schedule & round2 window (effective 2026-10-12)

Capture rounds run at **05:00 SGT (round1)** and **06:00 SGT (round2)**; the daily report is published at 07:00 SGT. (Through 2026-10-11 the rounds were 07:00 and 08:15 SGT.)

- **round1:** rolling window unchanged — `start_time = now − 48h`; queries 04 and 12 use `now − 96h`.
- **round2:** `start_time = 05:00 SGT the same day` (= `21:00Z` previous UTC day, e.g. for 2026-10-12 use `2026-10-11T21:00:00Z`), i.e. only posts since round1 started. Dedup against round1 ids as before.

Sort: recency for from: lists, relevancy for topic queries.

| # | slug | query | start_time | max | returned |
|---|---|---|---|---|---|
| 01 | ai-labs | `((from:OpenAI OR from:AnthropicAI OR from:GoogleDeepMind OR from:xai OR from:MetaAI OR from:MistralAI) -is:retweet -is:reply)` | 2026-10-08 (hist; now−48h) | 25 | 4 |
| 02 | openai-google | `((from:OpenAI OR from:OpenAIDevs OR from:GoogleDeepMind OR from:GoogleAI OR from:sama OR from:demishassabis) -is:retweet -is:reply)` | 2026-10-08 (hist; now−48h) | 25 | 6 |
| 03 | science-journals | `((from:Nature OR from:ScienceMagazine OR from:NatureNews OR from:CellPressNews OR from:physorg_com OR from:QuantaMagazine) -is:retweet -is:reply)` | 2026-10-08 (hist; now−48h) | 25 | 25 |
| 04 | official-econ | `((from:federalreserve OR from:BLS_gov OR from:stlouisfed OR from:NewYorkFed OR from:BEA_News OR from:USTreasury) -is:retweet -is:reply)` | 2026-10-06 (hist; now−96h) | 25 | 25 |
| 05 | arxiv-llm | `((url:arxiv.org) (LLM OR "language model" OR reasoning OR agents OR RL) lang:en -is:retweet -is:reply -giveaway -airdrop -bonus -homework -essay)` | 2026-10-08 (hist; now−48h) | 25 | 25 |
| 06 | ai-math-proofs | `(("Navier-Stokes" OR "Navier–Stokes" OR "700 papers" OR "AI-generated proofs") (OpenAI OR Lean) lang:en -is:retweet -is:reply -giveaway -airdrop -bonus)` | 2026-10-08 (hist; now−48h) | 10 | 10 |
| 07 | ai-researchers | `((from:karpathy OR from:ylecun OR from:JeffDean OR from:_akhaliq OR from:omarsar0 OR from:DrJimFan OR from:jaschasd) -is:retweet -is:reply)` | 2026-10-08 (hist; now−48h) | 10 | 10 |
| 08 | macro-economists | `((from:NickTimiraos OR from:elerianm OR from:jasonfurman OR from:LizAnnSonders OR from:M_McDonough OR from:biancoresearch) -is:retweet -is:reply)` | 2026-10-08 (hist; now−48h) | 10 | 10 |
| 09 | bond-yields | `(("10-year yield" OR "bond vigilantes" OR "term premium" OR "yield curve") lang:en -is:retweet -is:reply -giveaway -airdrop -bonus -BingX -XAU -signals)` | 2026-10-08 (hist; now−48h) | 10 | 10 |
| 10 | physics-space | `((from:NaturePhysics OR from:NatureComms OR from:PhysRevLett OR from:APSphysics OR from:CERN OR from:NASA) -is:retweet -is:reply)` | 2026-10-08 (hist; now−48h) | 10 | 10 |
| 11 | zh-ai-research | `((大模型 OR 论文 OR arXiv) (发布 OR 开源 OR 研究) lang:zh -is:retweet -is:reply -空投 -抽奖 -福利)` | 2026-10-08 (hist; now−48h) | 10 | 10 |
| 12 | ai-evals-policy | `((from:AISecurityInst OR from:METR_Evals OR from:EpochAIResearch OR from:StanfordHAI OR from:apolloaievals) -is:retweet -is:reply)` | 2026-10-06 (hist; now−96h) | 10 | 10 |

Re-run 2026-10-10 16:37-16:43 SGT with identical query strings/start_time/max_results; added only output fields (post.fields=created_at,author_id,public_metrics; expansions=author_id; user.fields=username). Raw files x/NN-<slug>.json are full tool returns, transcribed (no spill file appeared in /workspace/agent-tools/); see x/PROVENANCE.md.

## Derived filter (x/filtered-ids.json)

Raw x/NN-*.json stay complete. Derived x/filtered-ids.json keeps a post (deduped by id) if ANY of:
- public_metrics.like_count >= 20
- public_metrics.retweet_count >= 5
- author username (from includes.users) is on the authority whitelist below

### Authority whitelist
Defined as every `from:` account in the curated queries above (46 accounts):
_akhaliq, AISecurityInst, AnthropicAI, apolloaievals, APSphysics, BEA_News, biancoresearch, BLS_gov, CellPressNews, CERN, demishassabis, DrJimFan, elerianm, EpochAIResearch, federalreserve, GoogleAI, GoogleDeepMind, jaschasd, jasonfurman, JeffDean, karpathy, LizAnnSonders, M_McDonough, MetaAI, METR_Evals, MistralAI, NASA, Nature, NatureComms, NatureNews, NaturePhysics, NewYorkFed, NickTimiraos, omarsar0, OpenAI, OpenAIDevs, physorg_com, PhysRevLett, QuantaMagazine, sama, ScienceMagazine, StanfordHAI, stlouisfed, USTreasury, xai, ylecun
