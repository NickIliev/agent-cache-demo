#!/usr/bin/env python3
"""
Bug Report Analyzer — Agent Cache Demo
---------------------------------------
Demonstrates how Fiddler Everywhere's Agent Cache eliminates repeated
token usage when developing and testing an agent.

The agent takes a bug report as input and returns a structured analysis:
severity, category, a plain-English summary, and a suggested next step.

During development you might run this agent dozens of times against the
same report while iterating on how you parse and display the response.
Every run makes a live HTTPS call and consumes tokens.

With Fiddler Everywhere's Agent Cache:
  1. The first run makes a real HTTPS call and consumes tokens.
  2. You enable the Cache switch in the Agent Calls tab for that session.
  3. All subsequent runs with the same request are served from Fiddler's
     cache — zero additional tokens consumed on the provider side.
"""

import os
import json
import warnings

import httpx
import anthropic

# ---------------------------------------------------------------------------
# Configuration  (override via environment variables)
# ---------------------------------------------------------------------------

FIDDLER_PROXY = os.environ.get("FIDDLER_PROXY", "http://127.0.0.1:8866")
USE_PROXY = os.environ.get("USE_PROXY", "true").lower() == "false" # Alternatively, set to "false" and use the Fiddler's terminal to forward traffic only when needed.
API_KEY = os.environ.get("ANTHROPIC_API_KEY") 
MODEL = os.environ.get("ANTHROPIC_MODEL", "claude-sonnet-4-20250514")

# ---------------------------------------------------------------------------
# Prompts
# ---------------------------------------------------------------------------

SYSTEM_PROMPT = """You are a software engineering assistant that analyzes bug reports.

For every bug report you receive, respond with a JSON object using this exact structure:
{
  "severity": "critical | high | medium | low",
  "category": "one of: crash, performance, ui, security, data, other",
  "summary": "one sentence plain-English summary of the issue",
  "suggested_next_step": "one concrete action the engineer should take first"
}

Respond with the JSON object only. No extra text, no markdown fences."""

# Fixed input keeps request payloads identical across runs — this is exactly
# the condition that makes Agent Cache effective: same request, same response,
# no reason to spend tokens twice.
SAMPLE_BUG_REPORT = """
Title: App crashes on login when offline

Steps to reproduce:
1. Disable network connectivity on the test device.
2. Open the app.
3. Enter valid credentials and tap Login.

Observed: The app crashes immediately with an unhandled NullPointerException in
NetworkManager.checkConnectivity() (NetworkManager.kt:142).

Expected: A friendly "You appear to be offline" message should be shown.

Device : Pixel 7, Android 14
Version: 3.4.1 (build 2240)
"""

# ---------------------------------------------------------------------------
# Client setup
# ---------------------------------------------------------------------------


def build_client() -> anthropic.Anthropic:
    """
    Return an Anthropic client.

    When USE_PROXY=true (the default), all HTTPS traffic is routed through
    Fiddler Everywhere so the Agent Calls tab can capture and cache the calls.

    SSL verification behaviour (proxy mode only):
      - If SSL_CERT_FILE or REQUESTS_CA_BUNDLE points to the exported Fiddler
        root CA (PEM), httpx verifies Fiddler's certificate properly — no
        verify=False needed.  Export the CA from Fiddler Everywhere via
        Settings > HTTPS > Advanced > Export Root Certificate (PEM/ASCII).
      - Otherwise verification is disabled (verify=False) as a convenience for
        local demo use only.  Never use this in production.

    When USE_PROXY=false the agent connects directly to the provider.  Traffic
    can still be captured by launching this script from Fiddler's built-in
    terminal (Traffic pane → Terminal button), which pre-configures the proxy
    and CA for every child process automatically.
    """
    if not API_KEY:
        raise EnvironmentError(
            "ANTHROPIC_API_KEY environment variable is not set.\n"
            "Set it before running:\n\n"
            "  export ANTHROPIC_API_KEY=sk-ant-..."
        )

    if USE_PROXY:
        print(f"[proxy]  Routing HTTPS calls through Fiddler at {FIDDLER_PROXY}")

        # Prefer an explicit CA bundle so verify=False is not needed.
        ssl_cert = os.environ.get("SSL_CERT_FILE") or os.environ.get("REQUESTS_CA_BUNDLE")
        if ssl_cert:
            verify: str | bool = ssl_cert
            print(f"[proxy]  SSL verification using CA bundle: {ssl_cert}")
        else:
            verify = False
            # Suppress the InsecureRequestWarning raised by httpx when verify=False.
            warnings.filterwarnings("ignore", message=".*SSL.*")
            print(
                "[proxy]  SSL verification is disabled (verify=False) — demo mode only.\n"
                "[proxy]  To remove verify=False, export the Fiddler root CA and set\n"
                "[proxy]  SSL_CERT_FILE or REQUESTS_CA_BUNDLE to its path.\n"
                "[proxy]  See README.md — SSL / TLS Note for step-by-step instructions."
            )

        http_client = httpx.Client(proxy=FIDDLER_PROXY, verify=verify)
        return anthropic.Anthropic(api_key=API_KEY, http_client=http_client)

    # Direct connection — no Fiddler proxy in the code.
    # Traffic can still be captured by running this script from Fiddler's
    # built-in terminal (Traffic pane → Terminal button).
    print("[proxy]  USE_PROXY=false — connecting directly to the provider.")
    print("[proxy]  To capture traffic without code changes, launch this script")
    print("[proxy]  from Fiddler's built-in terminal instead.")
    return anthropic.Anthropic(api_key=API_KEY)


# ---------------------------------------------------------------------------
# Core agent logic
# ---------------------------------------------------------------------------


def analyze_bug_report(client: anthropic.Anthropic, report: str) -> dict:
    """
    Send a bug report to the model and return the structured analysis.

    Token usage is printed explicitly so you can see the cost difference
    between a real call and a Fiddler-cached call (the latter shows 0).
    """
    message = client.messages.create(
        model=MODEL,
        max_tokens=256,
        system=SYSTEM_PROMPT,
        messages=[
            {"role": "user", "content": f"Analyze this bug report:\n\n{report}"}
        ],
    )

    usage = message.usage
    total = usage.input_tokens + usage.output_tokens
    print(
        f"[tokens] Input: {usage.input_tokens:,}  |  "
        f"Output: {usage.output_tokens:,}  |  "
        f"Total: {total:,}"
    )

    raw = message.content[0].text.strip()
    return json.loads(raw)


def display_analysis(analysis: dict) -> None:
    """Pretty-print the structured bug report analysis."""
    print("\n── Bug Report Analysis ─────────────────────────────────────")
    print(f"  Severity  : {analysis.get('severity', 'N/A').upper()}")
    print(f"  Category  : {analysis.get('category', 'N/A')}")
    print(f"  Summary   : {analysis.get('summary', 'N/A')}")
    print(f"  Next step : {analysis.get('suggested_next_step', 'N/A')}")
    print("─────────────────────────────────────────────────────────────\n")


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------


if __name__ == "__main__":
    print("Bug Report Analyzer — Agent Cache Demo")
    print("=" * 60)
    print("\nBug report submitted:")
    print(SAMPLE_BUG_REPORT)

    client = build_client()

    try:
        result = analyze_bug_report(client, SAMPLE_BUG_REPORT)
        display_analysis(result)
    except json.JSONDecodeError as exc:
        print(f"\n[error] Could not parse model response as JSON: {exc}")
    except anthropic.APIStatusError as exc:
        print(f"\n[error] API error {exc.status_code}: {exc.message}")
    except anthropic.APIConnectionError:
        print(
            "\n[error] Could not reach the API endpoint.\n"
            "  - Check that Fiddler Everywhere is running and capturing traffic.\n"
            "  - Verify FIDDLER_PROXY points to the correct address and port.\n"
            "  - Or set USE_PROXY=false to connect directly."
        )
