# ---
# jupyter:
#   jupytext:
#     formats: ipynb,py:percent
#     text_representation:
#       extension: .py
#       format_name: percent
#       format_version: '1.3'
#       jupytext_version: 1.19.5
#   kernelspec:
#     display_name: Python 3 (ipykernel)
#     language: python
#     name: python3
# ---

# %% [markdown]
# #### Strength Acknowledgement Evaluator
#
# Checks whether teacher feedback (from CoGrader) actually **acknowledges something the student did well**, versus giving feedback that's only corrective, generic, or vague.
#
# Sends each `(student essay, teacher feedback)` pair to an OpenAI model (gbt-5.4) along with a detailed rubric, and getting back a structured score plus reasoning.
#
# ### Required files in folder:
# - `.env` — contains `OPENAI_API_KEY`
# - `config.json` — says which model to use and where the prompt files are
# - `system.txt` / `user.txt` — the actual rubric and prompt template sent to OpenAI model
# - `input_schema.json` / `output_schema.json` — states student text + feedack text / answer format
# - `fixtures.json` *(optional)* — a couple of known test cases used to sanity-check the pipeline
# - CSV of student essays + feedback to be scored
#
# ### Usage:
# 1. **Setup** — installs packages, loads your API key
# 2. **Section 1** — loads the rubric and config files
# 3. **Section 2** — defines the functions that actually call the model
# 4. **Section 3** — quick single-example test, so you can eyeball one result before committing to a full run
# 5. **Section 4** — runs 2 known test cases to confirm the pipeline is behaving correctly
# 6. **Section 5** — scores your real CSV file, row by row, and saves the results
#

# %%
# %pip install -qU openai pandas python-dotenv

# %%
import getpass
import os
from dotenv import load_dotenv
import json
import hashlib
import csv as csv_mod
from pathlib import Path

try:
    ASSETS_DIR = Path(__file__).resolve().parent
except NameError:
    ASSETS_DIR = Path.cwd()

load_dotenv(ASSETS_DIR / ".env")

if "OPENAI_API_KEY" not in os.environ:
    os.environ["OPENAI_API_KEY"] = getpass.getpass("Enter your OpenAI API key: ")

print(f"ASSETS_DIR resolved to: {ASSETS_DIR}")
print(f"  .env found here:      {(ASSETS_DIR / '.env').exists()}")
print(f"  key loaded:           {'OPENAI_API_KEY' in os.environ}")

# %% [markdown]
# ## 1. Load rubric and config (assets)
#
# Loads `config.json` + the standalone schemas. 
# Each prompt file's sha256 is checked against the hash
# declared in `config.json` — a drift tripwire so the notebook fails loudly if `system.txt`
# or `user.txt` change without `config.json` being updated to match.
#
# **Expected output:** a summary showing the model name, temperature, and the three prompt files loaded with their character counts and hashes. If you see a `[warn] sha256 mismatch`, it's worth investigating — usually it means the file was edited after being hashed.
#

# %%
with open(ASSETS_DIR / "config.json", encoding="utf-8") as f:
    CONFIG = json.load(f)

with open(ASSETS_DIR / "input_schema.json", encoding="utf-8") as f:
    INPUT_SCHEMA = json.load(f)
with open(ASSETS_DIR / "output_schema.json", encoding="utf-8") as f:
    OUTPUT_SCHEMA = json.load(f)

_STEP = CONFIG["steps"][0]

PROMPT_MESSAGES = []  # list of (role, text) tuples, preserving config order
for msg_spec in _STEP["prompt"]["messages"]:
    role = msg_spec["role"]
    path = ASSETS_DIR / msg_spec["source_path"]
    text = path.read_text(encoding="utf-8")
    actual_sha = hashlib.sha256(text.encode("utf-8")).hexdigest()
    declared_sha = msg_spec["sha256"]
    if actual_sha != declared_sha:
        print(
            f"  [warn] sha256 mismatch for role={role!r} ({msg_spec['source_path']}): "
            f"declared={declared_sha[:16]}... actual={actual_sha[:16]}..."
        )
    PROMPT_MESSAGES.append((role, text))

print(f"Loaded {CONFIG['evaluator']['id']}")
print(f"  model:       {_STEP['model']['provider']}/{_STEP['model']['name']}")
print(f"  temperature: {_STEP['generation']['temperature']}")
print(f"  prompts:")
for msg_spec, (role, text) in zip(_STEP["prompt"]["messages"], PROMPT_MESSAGES):
    sha = hashlib.sha256(text.encode("utf-8")).hexdigest()[:12]
    print(f"    {role:>6}  {msg_spec['source_path']:<14} ({len(text):>5} chars, sha {sha})")

# %% [markdown]
# ## 2. Prompt rendering + model call
#
# - **`render_prompt(...)`** - fills `{student_text}` / `{feedback_text}` placeholders from `user.txt.
# message.
# - **`call_model(...)`** —  sends the rendered message to OpenAI with `response_format` constrained
# to `OUTPUT_SCHEMA` (structured outputs), so the parsed JSON always matches `output_schema.json`.
# - **`is_acknowledges_strength(student_text, feedback_text)`** — the main function. Combines the two steps above and safely catches any errors (API issues, bad input, etc.) so one failed row doesn't crash the whole notebook — it just returns an error message as a string instead.

# %%
from openai import OpenAI

_client = OpenAI()

def render_prompt(student_text: str, feedback_text: str):
    rendered = []
    for role, text in PROMPT_MESSAGES:
        filled = text.replace("{student_text}", student_text).replace("{feedback_text}", feedback_text)
        rendered.append({"role": role, "content": filled})
    return rendered


def call_model(rendered_messages, model_name=None, temperature=None):
    model_name = model_name or _STEP["model"]["name"]
    temperature = temperature if temperature is not None else _STEP["generation"]["temperature"]

    resp = _client.chat.completions.create(
        model=model_name,
        temperature=temperature,
        messages=rendered_messages,
        response_format={
            "type": "json_schema",
            "json_schema": {
                "name": "EvaluatorOutput",
                "schema": OUTPUT_SCHEMA,
                "strict": True,
            },
        },
    )
    raw_text = resp.choices[0].message.content
    parsed = json.loads(raw_text)
    return {
        "rendered_prompt": rendered_messages,
        "raw_text": raw_text,
        "formatted_output": parsed,
        "usage": resp.usage.model_dump() if resp.usage else None,
    }


def is_acknowledges_strength(student_text: str, feedback_text: str):
    """
    Evaluate whether feedback acknowledges strengths in the student's text using the
    canonical config in config.json + system.txt + user.txt.

    Returns a dict with full I/O trace fields:
      - rendered_prompt:  the actual messages sent to the model.
      - raw_text:         the model's verbatim JSON string output.
      - formatted_output: the parsed dict matching OUTPUT_SCHEMA.
      - usage:             token-usage metadata if the provider returned it.
    """
    try:
        rendered_messages = render_prompt(student_text, feedback_text)
        return call_model(rendered_messages)
    except Exception as e:
        return f"Error evaluating text: {e}"


# %% [markdown]
# ## 3. Try it on a single example
#

# %%
sample_student_text = """Some people think AI-powered pets are a good alternative to real pets because they could help around the house etc."""
sample_feedback_text = """You're right, the AI pets could help around the house. Can you find some other details from the article that you could add to make your claim stronger?"""

case_output = is_acknowledges_strength(sample_student_text, sample_feedback_text)
case_output

# %% [markdown]
# ## 4. Run + score `fixtures.json`
# 2 Known test cases: — one case that *should* score 1 (feedback that praises something specific) and one that *should* score 0 (feedback that's purely corrective).
#

# %%
fixtures_path = ASSETS_DIR / CONFIG["fixtures"]["path"]
if not fixtures_path.exists():
    print(f"(no fixtures.json yet at {fixtures_path}; skipping fixture run)")
else:
    fixtures = json.loads(fixtures_path.read_text(encoding="utf-8"))
    print(f"Loaded {len(fixtures)} fixtures from {fixtures_path.name}\n")

    results = []
    for fx in fixtures:
        expected = fx["expected"]["acknowledges_strength_score"]
        out = is_acknowledges_strength(fx["input"]["student_text"], fx["input"]["feedback_text"])
        if isinstance(out, str):
            results.append({"id": fx["id"], "status": "error", "predicted": None,
                             "expected": expected, "error": out})
            continue
        predicted = out["formatted_output"]["acknowledges_strength_score"]
        status = "PASS" if predicted == expected else "FAIL"
        results.append({"id": fx["id"], "status": status, "predicted": predicted,
                         "expected": expected, "description": fx.get("description", "")})

    print("=" * 78)
    print(f"{'ID':>5}  {'STATUS':<8}  {'PREDICTED':<10}  {'EXPECTED':<10}  DESCRIPTION")
    print("=" * 78)
    for r in results:
        print(f"{r['id']:>5}  {r['status']:<8}  {str(r['predicted']):<10}  {str(r['expected']):<10}  {r.get('description','')[:40]}")

    n = len(results)
    n_pass = sum(1 for r in results if r["status"] == "PASS")
    n_fail = sum(1 for r in results if r["status"] == "FAIL")
    n_err = sum(1 for r in results if r["status"] == "error")
    print("=" * 78)
    print(f"Summary: {n_pass} pass, {n_fail} fail, {n_err} error -- total {n}")

# %% [markdown]
# ## 5. Score a CSV of student/feedback pairs
#
# Appends the `eval_*` columns (matching `output_schema.json`'s `key_features` plus the overall
# score and reasoning) to every row of an input CSV and writes a scored copy.
#
# Set `CSV_PATH`, `STUDENT_COL`, and `FEEDBACK_COL` for your file below.
#

# %%
CSV_PATH = ASSETS_DIR / "Cograder_Data_Results.csv"
OUT_PATH = ASSETS_DIR / "Cograder_Data_Results_Scored.csv"
STUDENT_COL = "generated_text"
FEEDBACK_COL = "cograder_feedback"

CSV_EVAL_COLUMNS = [
    "eval_presence_of_praise",
    "eval_specificity",
    "eval_anchoring_to_evidence",
    "eval_process_vs_trait_framing",
    "eval_warranted_acknowledgement",
    "eval_strength_acknowledged_overall",
    "eval_reasoning",
]

with open(CSV_PATH, newline="", encoding="utf-8") as f:
    reader = csv_mod.DictReader(f)
    fieldnames = list(reader.fieldnames)
    rows = list(reader)

for col in CSV_EVAL_COLUMNS:
    if col not in fieldnames:
        fieldnames.append(col)

for i, row in enumerate(rows):
    out = is_acknowledges_strength(row[STUDENT_COL], row[FEEDBACK_COL])
    if isinstance(out, str):
        print(f"  row {i}: ERROR - {out}")
        continue
    parsed = out["formatted_output"]
    kf = parsed["key_features"]
    row["eval_presence_of_praise"] = kf["presence_of_praise"]["met"]
    row["eval_specificity"] = kf["specificity"]["met"]
    row["eval_anchoring_to_evidence"] = kf["anchoring_to_evidence"]["met"]
    row["eval_process_vs_trait_framing"] = kf["process_vs_trait_framing"]["met"]
    # "warranted_acknowledgement" isn't a key_feature in output_schema.json;
    # treat it as praise being accurate/grounded (not false/misleading praise).
    row["eval_warranted_acknowledgement"] = kf["anchoring_to_evidence"]["met"]
    row["eval_strength_acknowledged_overall"] = parsed["acknowledges_strength_score"]
    row["eval_reasoning"] = parsed["reasoning"]
    print(f"  row {i}: score={parsed['acknowledges_strength_score']}")

with open(OUT_PATH, "w", newline="", encoding="utf-8") as f:
    writer = csv_mod.DictWriter(f, fieldnames=fieldnames)
    writer.writeheader()
    writer.writerows(rows)

print(f"\nWrote {len(rows)} rows -> {OUT_PATH}")
