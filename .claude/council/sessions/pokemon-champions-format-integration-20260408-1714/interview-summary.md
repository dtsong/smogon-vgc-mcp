# Interview Summary: Pokemon Champions Format Integration

## Core Intent
Pivot the MCP server from Gen 9-only to supporting Pokemon Champions (new generation, new dex, separate Pokemon pool). Reg I is a quick config-only add for the next couple months of Gen 9, then Champions becomes the top priority. Need to research emerging data sources since there's no official API.

## Key Decisions Made
- Reg I is config-only — just a new FormatConfig entry, no code changes
- Champions is a completely new gen with separate Pokemon, moves, abilities, dex
- Focus on Champions going forward, not multi-gen parity
- Build a Python damage calculator first for day-1 Champions support, swap to @smogon/calc when it adds the new gen
- No official in-game API for ladder stats — need third-party sources
- All decisions captured as GitHub issues

## Open Questions for Deliberation
- What third-party data sources exist or are emerging for Champions?
- What's Smogon's timeline for adding Champions format data?
- How should the format system evolve to handle a completely different generation?
- What static data (base stats, types, moves) needs to be sourced for Champions?
- Should the damage calc be a full rewrite or adapted from the existing @smogon/calc patterns?
- How to handle the transition period where Champions data is sparse?

## Perspective Relevance Scores
| Perspective | Score (0-5) | Rationale |
|-------------|-------------|-----------|
| Architect | 5 | Multi-gen architecture, format abstraction, damage calc design |
| Scout | 5 | Research Champions data sources, Smogon timeline, third-party tools |
| Strategist | 4 | Phasing Reg I vs Champions, MVP scoping |
| Oracle | 3 | MCP tool surface for new gen, prompt/tool design |
| Skeptic | 3 | Data availability risks, API stability concerns |
| Alchemist | 3 | Data pipeline for new sources (overlaps Architect) |
| Craftsman | 2 | Testing strategy, secondary for planning session |
| Advocate | 1 | No direct UX/UI work |
| Operator | 1 | No deployment concerns |
