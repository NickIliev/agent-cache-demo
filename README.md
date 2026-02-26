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

Start Fiddler Everywhere. How traffic reaches Fiddler depends on the `USE_PROXY` environment variable:

**`USE_PROXY=true` (default)**
`agent.py` explicitly routes every HTTPS call through the address set in `FIDDLER_PROXY` (`http://127.0.0.1:8866` by default). Because the proxy is set in code, **no Fiddler capturing mode needs to be enabled** — Fiddler simply has to be running. The call will appear in the **Traffic > Agent Calls** tab automatically.

**`USE_PROXY=false`**
The agent connects directly to the provider; Fiddler's proxy is bypassed entirely. You can still capture the traffic, however, by launching the agent from **Fiddler's built-in terminal** (Traffic pane → **Terminal** button). That terminal is pre-configured with the Fiddler proxy address and a trusted CA certificate, so all child processes — including `agent.py` — are captured without any code change. See the [Terminal Capturing Mode](https://www.telerik.com/fiddler/fiddler-everywhere/documentation/capture-traffic/capturing-traffic-from-terminal) and [Setting Fiddler alongside Python applications](https://www.telerik.com/fiddler/fiddler-everywhere/documentation/capture-traffic/advanced-capturing-options/capturing-python-traffic) docs for details.

Then run:

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

The demo disables SSL verification (`verify=False`) so `httpx` accepts Fiddler's intercepting certificate without extra configuration. This is fine for local development, but should never be used in production.

There are two recommended approaches for removing `verify=False` in non-demo use.

### Option A — Use Fiddler's built-in terminal

Fiddler Everywhere ships a dedicated terminal that automatically configures the proxy and trusts the Fiddler CA — no manual certificate work required.

1. In Fiddler Everywhere, click **Open Terminal**.
2. Run `python agent.py` inside that terminal.
3. Remove the `verify=False` argument from the `httpx.Client` call.

### Option B — Export the CA and set environment variables

1. In Fiddler Everywhere, go to **Settings > HTTPS > Advanced > Export Root Certificate (PEM/ASCII)** and save the file (e.g. `Fiddler_Root_Certificate_Authority.pem`).
2. Set the following environment variables **before** running the agent.

   **macOS / Linux**
   ```bash
   export http_proxy=http://127.0.0.1:8866
   export https_proxy=http://127.0.0.1:8866
   export SSL_CERT_FILE=~/Desktop/Fiddler_Root_Certificate_Authority.pem
   export REQUESTS_CA_BUNDLE=~/Desktop/Fiddler_Root_Certificate_Authority.pem
   ```

   **Windows**
   ```cmd
   set http_proxy=http://127.0.0.1:8866
   set https_proxy=http://127.0.0.1:8866
   set SSL_CERT_FILE=%USERPROFILE%\Desktop\Fiddler_Root_Certificate_Authority.pem
   set REQUESTS_CA_BUNDLE=%USERPROFILE%\Desktop\Fiddler_Root_Certificate_Authority.pem
   ```

3. Pass the certificate path to `httpx` explicitly and remove `verify=False`:
   ```python
   import os
   verify = os.environ.get("SSL_CERT_FILE", True)
   httpx.Client(proxy=proxy_url, verify=verify)
   ```

   Or, if the Fiddler CA has been added to the system trust store, simply pass `verify=True` (the default).

For further details, see the [Setting Fiddler alongside Python applications](https://www.telerik.com/fiddler/fiddler-everywhere/documentation/capture-traffic/advanced-capturing-options/capturing-python-traffic) guide and the [export the Fiddler CA as PEM](https://www.telerik.com/fiddler/fiddler-everywhere/documentation/knowledge-base/how-to-create-pem) knowledge-base article.
