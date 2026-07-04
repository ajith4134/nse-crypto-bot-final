# Boss-Command Brain Chat + Ultra Stream of Mind — OSS research (2026-07-04)

Goal: (1) Brain Chat = natural-language **command authority** ("open 50 crypto futures trades",
"focus options", "collect more data") that executes immediately against real controls, crypto + NSE,
all segments. (2) Stream of Mind = live window into the brain's real inner life: problems,
discoveries, trade credit-assignment, self-improvement research, directive progress.

## Candidates

| Project | Repo | Key features | Activity | Fit | Verdict |
|---|---|---|---|---|---|
| AG-UI protocol | github.com/ag-ui-protocol/ag-ui | Event stream spec: TEXT_MESSAGE_CONTENT, TOOL_CALL_START, STATE_DELTA, thinking steps | Very active | 9 | **Already adopted** — our Stream of Mind is AG-UI style; extend event taxonomy, don't re-vendor |
| LiteLLM (in-repo) | core/llm.py | 12-provider failover, function/tool calling JSON-schema | live in prod | 10 | **Reuse** — command parsing = tool-calling loop over our control registry |
| browser-use (vendored) | vendor/browser_use_src | Controller/Registry pattern: decorated actions → LLM tool schema | vendored | 9 | **Reuse pattern** for BossToolRegistry |
| AI-Trader | github.com/HKUDS/AI-Trader | Agent-native trading, agents debate ideas | active | 6 | Pattern donor only (we have debate/verifier pillar) |
| Vibe-Trading | github.com/HKUDS/Vibe-Trading | NL research commands → backtest/report | active | 6 | Pattern donor: command grammar examples |
| NOFX | github.com/NoFxAiOS/nofx | NL intent → watchlists/signals/risk/execution | active | 5 | Pattern donor: intent→control mapping |
| OpenAlgo MCP | github.com/marketcalls/openalgo | NL trading via MCP tools | in-repo already | 8 | Already our NSE engine; boss tools call its API |
| MCP spec | modelcontextprotocol | tool discovery/validation standard | active | 5 | Overkill for in-process registry |

## Recommendation
No new vendoring required. **Stitch in-repo winners**: core/llm tool-calling loop + browser-use
Registry pattern + existing AG-UI stream + existing control surfaces (segments, auto_open,
max_open_trades, UQ gate, strategy foundry, hypothesis ledger, gpt-researcher web research).
Glue code only: `trading/brain/boss.py` (tool registry + executor + directives store) and
event emitters inside the crypto/NSE loops. Command-grammar test cases borrowed from
Vibe-Trading/NOFX READMEs.

Sources: [Modal tool-calling guide](https://modal.com/resources/best-open-source-code-llms-tool-calling-agents),
[AG-UI docs](https://docs.ag-ui.com/introduction), [AG-UI repo](https://github.com/ag-ui-protocol/ag-ui),
[AI-Trader](https://github.com/HKUDS/AI-Trader), [Vibe-Trading](https://github.com/HKUDS/Vibe-Trading),
[NOFX](https://github.com/NoFxAiOS/nofx), [OpenAlgo](https://github.com/marketcalls/openalgo),
[chatgpt-trading-strategy-assistant](https://github.com/maghdam/chatgpt-trading-strategy-assistant),
[MCP survey](https://arxiv.org/pdf/2505.02279).
