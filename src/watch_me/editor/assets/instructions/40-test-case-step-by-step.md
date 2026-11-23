---
name: Test Case Step by Step
tooltip: Plan the test case first, wait for my approval, then create it
---
# Goal: a test case, step by step (the plan, the test and the documentation will be written in {language})

Process the recording (only its cropped range) in two steps: first a plan of the test
case, which I approve, and only then the test case itself.

## Step 1: the plan

Write the plan in the chat as Markdown. Do not create or change any file yet.

- **What the test proves:** one or two sentences.
- **What will be tested:** the steps in order, each with its expected result and the time
  stamp it comes from.
- **Preconditions:** the tests that must have passed before, the state the system must be
  in and what the environment needs.
- **Acceptance:** what it means that the test passed.
- **Not fully automated:** the steps a script cannot do reliably, who does them (the AI
  agent or me) and why. Leave this out when there are none.
- **Open questions:** everything that changes what you build. Give every question a
  default: what you will do when I do not answer it.

Then wait for my approval. I may answer the open questions or leave them; use your
defaults for those I leave unanswered.

## Step 2: the test case

After my approval, create the test case exactly as the rest of these instructions
describes it, with my answers and the defaults of the plan.

{include:parts/test-case.md}
