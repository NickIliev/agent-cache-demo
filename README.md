# Agent Cache Demo — Bug Report Analyzer

This project demonstrates [Fiddler Everywhere's Agent Cache](../inspect-traffic/agent-cache.md) feature using a minimal Python agent.

The agent sends a fixed bug report to the Claude API and returns a structured analysis (severity, category, summary, and a suggested next step). Because the input is identical on every run, it is a perfect match for Agent Cache: after the first real call, Fiddler Everywhere can serve every subsequent run from cache—consuming zero additional tokens on the provider side.

---

## Prerequisites

| Requirement | Details |
|:------------|:--------|
| **Python** | 3.10 or later |
| **Fiddler Everywhere** | Trial, Pro, or Enterprise (Lite is not supported for Agent Cache) |
| **Anthropic API key** | [console.anthropic.com](https://console.anthropic.com) |

---

## Setup

```bash
# 1. Create and activate a virtual environment
python -m venv .venv
source .venv/bin/activate        # macOS / Linux
.venv\Scripts\activate           # Windows

# 2. Install dependencies
pip install -r requirements.txt

# 3. Set your API key
export ANTHROPIC_API_KEY=sk-ant-...   # macOS / Linux
set ANTHROPIC_API_KEY=sk-ant-...      # Windows
```

---

## Running the Demo

### Step 1 — Baseline run (tokens consumed)

Start Fiddler Everywhere and make sure traffic capture is active. Then run:

```bash
python agent.py
```

Expected output:

```
Bug Report Analyzer — Agent Cache Demo
============================================================

Bug report submitted:
...

[proxy]  Routing HTTPS calls through Fiddler at http://127.0.0.1:8866
...
[tokens] Input: 312  |  Output: 68  |  Total: 380

── Bug Report Analysis ─────────────────────────────────────
  Severity  : HIGH
  Category  : crash
  Summary   : App crashes with a NullPointerException when attempting to
              log in under no network connectivity.
  Next step : Add a null or connectivity check in
              NetworkManager.checkConnectivity() before network calls.
─────────────────────────────────────────────────────────────
```

Switch to Fiddler Everywhere and open the **Traffic > Agent Calls** tab.
You will see the captured call to `api.anthropic.com`. Note the token count printed in the terminal — this represents the cost of the live call.

### Step 2 — Enable Agent Cache

In the **Agent Calls** tab, find the captured session and enable its **Cache** switch.

### Step 3 — Cached run (zero token cost)

Run the agent again without changing anything:

```bash
python agent.py
```

Fiddler Everywhere intercepts the outbound call and immediately returns the cached response. The terminal output is identical, but the provider never received the request — so no tokens were charged.

---

## Environment Variables

| Variable | Default | Description |
|:---------|:--------|:------------|
| `ANTHROPIC_API_KEY` | — | **Required.** Your Anthropic API key. |
| `ANTHROPIC_MODEL` | `claude-sonnet-4-20250514` | Model to use. |
| `FIDDLER_PROXY` | `http://127.0.0.1:8866` | Fiddler Everywhere proxy address. |
| `USE_PROXY` | `true` | Set to `false` to bypass Fiddler and connect directly. |

---

## How It Works

```
┌─────────────┐   HTTPS (proxied)   ┌──────────────────────┐   HTTPS   ┌──────────────────┐
│  agent.py   │ ──────────────────► │  Fiddler Everywhere  │ ────────► │  api.anthropic.com│
│             │                     │  (Agent Calls tab)   │           └──────────────────┘
│             │ ◄────────────────── │                      │ ◄──────── response
└─────────────┘   response          └──────────────────────┘
                                            │
                                     Cache switch ON?
                                            │
                                    ┌───────▼────────┐
                                    │ Return cached  │
                                    │ response.      │
                                    │ No new call to │
                                    │ the provider.  │
                                    └────────────────┘
```

1. `agent.py` routes all HTTPS traffic through Fiddler via `httpx` proxy settings.
2. Fiddler captures the call and displays it in **Agent Calls**.
3. When the **Cache** switch is enabled, Fiddler replays the stored response for any matching subsequent call.
4. The provider endpoint never receives the duplicate request — no tokens are charged.

---

## SSL / TLS Note

The demo disables SSL verification (`verify=False`) so `httpx` accepts Fiddler's intercepting certificate without extra configuration. This is fine for local development.

For any non-demo use, [install the Fiddler root CA certificate](https://docs.telerik.com/fiddler-everywhere/installation-and-setup/trust-fiddler-ca) and remove the `verify=False` parameter.
