# There is no database of cell towers

*Everyone assumes one exists. It doesn't, and that gap breaks billing audits, coverage analysis, and roaming reconciliation in quiet ways. We just published the research workflow we use to build tower masters from scratch, as an open Claude Code skill.*

---

Ask a normal question: where are the cell towers for this carrier, and what cell IDs do they broadcast? You would think somebody maintains that table. Nobody does.

What exists instead is four partial views that disagree with each other:

The regulators know where licensed transmitters physically are. In the US, FCC ULS has exact coordinates for every licensed transmitter site, and FCC ASR has owner-attested coordinates for registered structures. What the regulators do not know is anything about the network side. There is no LAC, no cell ID, no eNodeB in a license record. A license tells you a tower exists; it cannot tell you which tower your phone was talking to.

The crowdsourced platforms know the opposite half. OpenCelliD and CellMapper have millions of observations pairing a cell identity with a location, collected from volunteers' phones. But an OpenCelliD coordinate is a weighted centroid of wherever people happened to stand when their phones saw that cell. With one sample it can be off by kilometers. The data that knows the cell IDs has soft coordinates; the data with hard coordinates knows no cell IDs.

The carriers themselves file site commitments in regulatory dockets, in prose, in PDFs. The Alaska Plan and RDOF filings name every site a funded carrier promised to build. Extracting a table from them is an afternoon of work per filing.

And then there are the aggregator websites, which look authoritative and are mostly stale re-packagings of the FCC data with the provenance stripped off.

If you work with CDR or TAP billing data, you eventually need the join none of these provide alone: `(mcc, mnc, lac, ci)` from a call record, resolved to a real tower at a defensible coordinate. We do this work, and it is harder than it has any right to be. So we taught the whole pipeline to Claude Code and published it.

```
/plugin marketplace add fuzemobi/claude-plugins
/plugin install carrier-tower-research@fuzemobi-plugins
```

## Why this is genuinely hard

A few of the traps, from our own scar tissue.

**The regulator doesn't know your carrier's name.** ULS and ASR index the registered legal entity, not the brand. Search for the name on the storefront and you get nothing; search for the full cooperative or LLC name on the license and you get every record. Rural carriers are the worst case: the brand, the holding company, and the licensing entity can be three different names. The skill ships a checklist of entity-name variants to try, and the advice to fall back to the FCC Registration Number, which never varies.

**The coordinates come in the wrong format.** ULS stores degrees-minutes-seconds in separate fields with a hemisphere flag. Every merge starts with DMS-to-decimal conversion, and a sign error puts a tower in the wrong hemisphere. Ofcom's UK register, by contrast, is already decimal degrees in a quarterly CSV. Every country's regulator made its own choices; the skill's references cover the US sources in depth and fifteen-plus other countries in tiers by data quality.

**The obvious join key is wrong.** LTE cell identities pack an eNodeB ID and a sector: `enb_id = ci >> 8`, `sector = ci & 0xFF`. It is tempting to join tower data on the eNodeB ID. Don't. One eNB value can map to dozens of physical sites, so an eNB join silently assigns arbitrary coordinates that look plausible on a map. The skill mandates matching on the full cell identity and verifying against real call-record location data before trusting any operator export.

**An LLM will happily guess.** Ask a model where "Nome Site 2" is and it will produce confident coordinates. That is how a site in Nome, Alaska ends up plotted in Pike Road, Alabama. The skill's hardest rule is that coordinates are never generated: a row either carries a coordinate from a named source, or it carries a town-centroid placeholder explicitly tagged as such and flagged for follow-up.

**Crowdsourced data lies at low sample counts.** The skill requires at least five observations before an OpenCelliD centroid counts, prefers CellMapper's triangulated positions where they exist, and refuses "predicted" tower locations outright. Mozilla Location Service, which used to be the third source here, was discontinued; old dumps still circulate and are only good for history.

## What the skill actually does

Give it a carrier, as an MCC/MNC pair like 310-410, a TADIG code, or just a name, and it runs a research pipeline:

1. **Resolve identity.** MCC/MNC, TADIG, and FCC legal entity name, cross-checked, because every downstream query depends on getting the entity name right.
2. **Pull the authoritative layer.** FCC ULS bulk dumps (queried locally with grep and awk, because the files are enormous and re-downloading them per question is silly), ASR, FAA obstruction filings for sites too new to be registered, coverage data for validation, and the docket filings where carriers name their committed sites. Outside the US, the national regulator registries.
3. **Layer the observations.** OpenCelliD and CellMapper supply the cell identities, collapsed from sector-level rows to tower-level rows, then matched to regulator coordinates within a distance threshold.
4. **Merge in trust order.** An eleven-level hierarchy from operator export down to manual centroid seed. The rule that matters: a higher-trust coordinate is never overwritten by a lower-trust one, and every row carries a `source` tag and a source URL.
5. **Validate and emit.** Join-key completeness, no silent coordinate nulls, and a sanity check against the carrier's publicly stated footprint, because an eight-village co-op returning four hundred towers means something upstream went wrong. The output is a 29-column CSV plus a methodology document listing every query used, so the next person can reproduce the pull instead of trusting it.

Four Python scripts ship with it, covering the ULS bulk join, the ASR entity search, the OpenCelliD fetch, and the trust-order merge. Everything it queries is public data: government licensing records, public filings, and openly licensed crowdsourced observations.

## The part we care about most

The trust order sounds like bureaucracy until the first time two sources disagree about where a tower is. Then it is the whole product. A tower master where every row can answer "who says so?" is a different artifact from a map of dots, even when the dots land in the same places. Billing disputes, coverage claims, and audits all eventually reach the question of provenance, and a CSV with a `source` column and a methodology doc answers it. One without them is just an opinion with coordinates.

The skill is MIT licensed, part of the same marketplace as our team-mode multi-agent workflow and doc-extract plugins. The README covers the full method, the trust hierarchy, and the failure modes in more detail: [github.com/fuzemobi/claude-plugins](https://github.com/fuzemobi/claude-plugins).

If you have fought this same fight for a carrier we have never heard of, in a country whose regulator we rated wrong, open an issue. The tier list improves one annoyed contributor at a time.
