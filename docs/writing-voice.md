# Writing voice calibration

Agents should write like a person who makes choices, not like a model arranging
acceptable phrases. The fastest way to get that right is not to describe the
voice in adjectives. It is to make the person write, then turn their samples
into rules.

This page is the exercise. It works best with a person in the loop: an agent
runs the prompts, the person answers in their own words, and the agent does not
touch public copy until the rules below are agreed.

## What not to do

- Do not ask "how would you describe your writing style?" People are bad at
  this and so is everyone.
- Do not guess the voice from other projects, past sessions, or an existing
  "tone" paragraph. Samples from *this* repository and *this* person win.
- Do not treat AI-writing detectors or humanizers as the standard. They can
  flag a pattern. They do not supply the rhythm or the judgment.

## The exercise

Ask two or three prompts at a time. Wait for the answers, then go again. Aim
for 15–20 short samples total. Mix these kinds:

1. Rewrite an actual line from this repository that reads like AI copy. Quote
   the file and the line first. Pick one that uses a clipped antithesis
   ("The label changes. The deduction does not."), a slogan stack, or a
   hollow intensifier.
2. Write the error message for: a source download failed its checksum; a
   survey release is missing a required artifact; you hit an API rate limit.
3. Describe Microdata Lab to a stranger at a party, in two sentences.
4. Write the empty state for "no analyses in this catalog yet."
5. The one piece of praise for a passing analysis that would not make you
   cringe.
6. Text a friend about something that went wrong today.
7. Three phrases that make you want to close a tab.

After about eight samples, stop and give a **voice hypothesis**: five to eight
concrete, falsifiable rules you have inferred — rhythm, sentence length,
punctuation habits, how praise is handled, how bad news is handled, what is
refused. Then test it: take one piece of repository copy, write three
variants, and ask which is closest and why. Use the correction to revise the
rules. Repeat until the person says it is right.

The voice this project wants is dry and flat. Understatement, not jokes. If a
proposed line is quippy or winking, it missed.

## What the rules should cover

- Rhythm and sentence-length variation (a page of clipped fragments reads as
  generated too).
- Punctuation habits, including em dashes. One that earns the interruption,
  not three per paragraph.
- How praise is handled: observed and specific, not manufactured cheer.
- How bad news is handled: plainly, with the consequence and the next step.
- What is refused: startup gloss, fake revelations ("This isn't X. It's Y."),
  slogan stacks, mechanical trios, canned bridges.
- Claims of simplicity that skip the annoying step. If an account, key,
  approval, download, or limitation exists, say so.

## Where the results live

The agreed rules go in `docs/writing-voice.md` (this file), replacing the
generic guidance with the person's actual rules and their samples as
reference. The samples teach better than the rules, so keep the good ones.

The working questionnaire lives in `docs/writing-voice.template.md`. Copy it,
fill it in, and paste the completed answers back here when the calibration is
done. Do not paste the filled questionnaire anywhere else.

## Before shipping any public copy

- Read `docs/writing-voice.md` and follow its rules from the first draft. A
  "voice pass" at the end cannot rescue generic copy.
- Check every string that reaches a reader: Markdown, chart titles, callout
  boxes drawn onto media frames, subtitles, notes, and fallback tables.
- Keep facts, numbers, legal constraints, and honest-framing limits fixed
  while editing voice. Voice edits change shape, never claims.
- If a line still sounds generated, rewrite it from the claims. Do not defend
  it and do not keep sanding the same draft.
