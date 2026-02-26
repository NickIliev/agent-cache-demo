# Stop Paying for the Same Answer Twice: Fiddler Everywhere's Agent Cache

If you have ever built a model-powered agent, you know the development loop. Write some code, fire it at the endpoint, check the response, tweak the parsing, fire it again. Repeat until the output looks right. It is a perfectly normal workflow — and it quietly drains your token budget with every single iteration.

Fiddler Everywhere's new **Agent Cache** feature is designed to break that cycle. Once you capture a response from a model-provider endpoint, you can flip a single switch and have Fiddler replay that response for every subsequent matching call — without the request ever leaving your machine. Same output, zero additional tokens consumed on the provider side.

This post walks through exactly how that works, using a small open-source demo project to make everything concrete.

---

## The Hidden Cost of Agent Development

Building an agent that calls a completion endpoint involves a lot of repetition that has nothing to do with the model itself. You are iterating on:

- How you construct the prompt
- How you parse and validate the structured response
- How you surface the result to the rest of your system
- How your error handling behaves when the response is malformed

None of those iterations require a new, unique response from the model. You already have a good one from the first call. But unless you manually save the raw response and mock it yourself, every `agent.py` invocation sends a fresh request, and the provider charges for it.

For a simple agent that exchanges a few hundred tokens per call, this might feel negligible. In practice, though:

- Development sessions can easily involve dozens of sequential runs.
- Teams have multiple developers iterating in parallel.
- Integration and regression test suites call the same endpoints repeatedly in CI.

The costs compound quickly, and none of that spend actually improves the agent.

---

## What Agent Cache Does

Fiddler Everywhere acts as a proxy that sits between your agent and the remote endpoint. When your agent makes an HTTPS call to, say, `api.anthropic.com`, Fiddler intercepts it, forwards it, and logs the full request–response pair in the **Traffic** pane.

The new **Agent Calls** tab is a focused view inside that pane. It automatically filters sessions to show only calls that target supported model-provider endpoints — so you are not wading through noise from other traffic. Every captured call gets a **Cache** toggle.

Enable the toggle, and Fiddler starts intercepting any outbound call that matches that session's request. Instead of forwarding the request, it immediately returns the cached response. The endpoint never receives the duplicate call. Your agent sees the exact same payload it would have received from a live call. Token count: zero.

Disable the toggle at any time and live traffic resumes, no restarts required.

---

## Faster Iterations, Lower Costs, More Predictable Testing

Agent Cache is built around three practical benefits that matter most during active development.

**Faster Iterations.**
Cache a previous run inside Fiddler Everywhere and cut the wait time between tweaks. You validate changes immediately and move through the development loop with far less friction.

**Lower Execution Costs.**
Reuse responses already captured in Fiddler Everywhere instead of triggering repeated live calls. The provider never sees the duplicate requests — so spend stays under control as you iterate.

**More Deterministic Testing.**
Identical inputs produce identical outputs, every time. That makes it straightforward to compare iterations, isolate regressions, and be confident about exactly what changed between runs.

---

## Demo: Bug Report Analyzer

To make this tangible, let's walk through [agent-cache-demo](https://github.com/your-org/agent-cache-demo) — a minimal Python agent that takes a fixed bug report and returns a structured analysis (severity, category, a plain-English summary, and a suggested next step). The input never changes between runs, which makes it a perfect showcase for Agent Cache: the model's answer to an identical prompt is always the same, so there is genuinely no reason to pay for it more than once.

### What the Agent Does

The core of `agent.py` is straightforward:

```python
message = client.messages.create(
    model=MODEL,
    max_tokens=256,
    system=SYSTEM_PROMPT,
    messages=[
        {"role": "user", "content": f"Analyze this bug report:\n\n{report}"}
    ],
)
```

It sends the bug report to the Claude API and expects a JSON response like this:

```json
{
  "severity": "high",
  "category": "crash",
  "summary": "App crashes with a NullPointerException when attempting to log in under no network connectivity.",
  "suggested_next_step": "Add a null or connectivity check in NetworkManager.checkConnectivity() before network calls."
}
```

That response is then formatted and printed to the terminal:

```
── Bug Report Analysis ─────────────────────────────────────
  Severity  : HIGH
  Category  : crash
  Summary   : App crashes with a NullPointerException when attempting to
              log in under no network connectivity.
  Next step : Add a null or connectivity check in
              NetworkManager.checkConnectivity() before network calls.
─────────────────────────────────────────────────────────────
```

### Setup

Clone the repository and install dependencies:

```bash
git clone https://github.com/your-org/agent-cache-demo
cd agent-cache-demo

python -m venv .venv
source .venv/bin/activate      # macOS / Linux
.venv\Scripts\activate         # Windows

pip install -r requirements.txt
export ANTHROPIC_API_KEY=sk-ant-...
```

### Step 1 — The First Live Call

Start Fiddler Everywhere. By default the agent routes its traffic through Fiddler automatically (via the `FIDDLER_PROXY` setting), so no capturing mode needs to be enabled — Fiddler just has to be running.

Run the agent:

```bash
python agent.py
```

The terminal shows the result and, crucially, the token consumption:

```
[tokens] Input: 312  |  Output: 68  |  Total: 380
```

Switch to Fiddler Everywhere and open **Traffic > Agent Calls**. You will see the captured call to `api.anthropic.com` with the full request and response visible.

This is your baseline. You paid for 380 tokens. That is fair — you needed the live call to validate the end-to-end flow.

### Step 2 — Enable the Cache

In the **Agent Calls** grid, find the captured session and flip its **Cache** switch to on. That is the entire configuration step.

### Step 3 — All Subsequent Runs Are Free

Run the agent again:

```bash
python agent.py
```

The output in the terminal is byte-for-byte identical to the first run, including the token count display. Switch to the **Agent Calls** tab in Fiddler and you will see a new session entry for this run — Fiddler did intercept the request. The difference is what happened next: because the **Cache** switch was on, Fiddler served the stored response immediately and never forwarded the request to the provider. The endpoint never saw the call.

You can now iterate on `agent.py` as many times as you need — refactor the display logic, test the error handler, adjust the JSON parsing, add logging — and none of those runs cost a single token.

---

## Routing Options: Working With or Without the Proxy in Code

The demo exposes a `USE_PROXY` environment variable that illustrates two common setups you might encounter on real projects.

**`USE_PROXY=true` (the default)**
The agent explicitly sets the `FIDDLER_PROXY` address in the `httpx.Client` constructor. Every HTTPS call is routed to Fiddler regardless of your system proxy settings. Fiddler just needs to be running — no capturing mode required.

**`USE_PROXY=false`**
The agent connects directly to the provider. This matches scenarios where you cannot or do not want to touch the application code. You can still capture the traffic by launching the agent from the **Fiddler's built-in terminal** (open it from the Traffic pane via the **Terminal** button). That terminal instance is pre-configured with the correct proxy address and a trusted CA certificate, so every process started from it — including `agent.py` — is captured automatically, with no code changes needed.

---

## SSL / TLS in Practice

Because Fiddler sits between your agent and the provider, it needs to decrypt HTTPS traffic. The demo uses `verify=False` for simplicity, but that is intentionally a demo-only shortcut.

For any real use there are two cleaner options:

**Option A — Fiddler's terminal (zero configuration)**
Launch `agent.py` from Fiddler's built-in terminal. The terminal handles both the proxy and the CA trust automatically.

**Option B — Export the CA and set environment variables**
Export the Fiddler root certificate from **Settings > HTTPS > Advanced > Export Root Certificate (PEM/ASCII)** and point your Python environment at it:

```bash
export SSL_CERT_FILE=~/Desktop/Fiddler_Root_Certificate_Authority.pem
export REQUESTS_CA_BUNDLE=~/Desktop/Fiddler_Root_Certificate_Authority.pem
```

The agent picks these up automatically — `verify=False` is never set. See the [Setting Fiddler alongside Python applications](https://www.telerik.com/fiddler/fiddler-everywhere/documentation/capture-traffic/advanced-capturing-options/capturing-python-traffic) guide for the full walkthrough.

---

## When to Use Agent Cache

Agent Cache is particularly valuable in these scenarios:

**Iterating on response parsing.** Your agent already returns a correct response from the model. You are now working on how your code handles that response — formatting, validation, error recovery. None of that work requires fresh model calls.

**Sharing a working state with teammates.** Cache a known-good response and share the Fiddler session. Everyone on the team can run against the same replay without burning tokens or depending on network access to the provider.

**Running a regression suite.** If your test suite exercises the same request paths repeatedly, caching the first response lets the suite run in full without accumulating provider costs. Once you genuinely need to test against a live endpoint, toggle the cache off.

**Working offline or in restricted environments.** Once the cache is populated, your agent keeps working even without connectivity to the provider.

---

## Things to Keep in Mind

- **Cache matching is request-based.** If your agent changes the prompt, the model, or any request headers, the cached session will no longer match. Capture and cache the updated variant separately.
- **The cache lives in the current Fiddler session.** Closing and reopening Fiddler clears the cache state, so the next run after a restart will make a live call.
- **Cache is for development, not staging.** Agent Cache is designed for development and testing workflows where deterministic, repeatable responses are the goal. Do not use it as a substitute for response validation against a live endpoint when preparing to ship.

---

## Availability

Agent Cache is available on Fiddler Everywhere **Trial**, **Pro**, and **Enterprise** tiers. The feature is not included in Lite licenses.

---

## Try It Yourself

The full demo is on GitHub. Clone it, set your Anthropic API key, and you can see the before-and-after token counts yourself in under five minutes.

The point is not really the 380 tokens saved in a single run. It is the dozens of runs you make in a typical development session, the parallel runs across a team, and the automated test executions in CI — all of which can stop paying for answers they already have.

Agent Cache does not change how you build agents. It just removes the tax on iterating.

---

*Fiddler Everywhere is available at [telerik.com/fiddler](https://www.telerik.com/fiddler). The demo project is at [github.com/your-org/agent-cache-demo](https://github.com/your-org/agent-cache-demo).*
