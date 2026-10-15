# Reddit — Comment Voice (avoiding "hi bot")

When drafting replies on reddit.com via browser-harness, the comment has to read like a real user typing on their phone. Reddit users are unusually good at clocking LLM output and will reply "hi bot" the moment they spot it. Once that happens the parent account loses credibility on that subreddit.

## Tells that get you flagged

- **Em-dashes (`—`).** Phone keyboards don't produce them. Almost nobody types them. They are the single strongest LLM tell on Reddit right now.
- **Parallel structure.** "X is basically Y without Z", "not just X, but Y", "the X, the Y, and the Z".
- **Balanced both-sides framing.** "Either works", "both have merit", "it depends on your use case".
- **Sycophantic openers.** "Totally get it", "great point", "ah interesting", "yeah so basically".
- **Tricolons.** Three-item lists with the same grammatical shape.
- **Uniform sentence length.** Every sentence ~15 words = bot. Real comments are jagged.
- **Forced all-lowercase.** Used to read casual, now reads as a bot trying to seem casual. Mix it.
- **Over-clean grammar.** Real Redditors have stray apostrophes, run-ons, abandoned thoughts.

## What reads human

- **Mix sentence length aggressively.** Short. Then one that rambles a bit and trails into a side point. Short again.
- **One idea per comment.** Walls of structured analysis = bot. If the reply has three sections it's too long.
- **Opinions with rough edges.** "tbh idk", "probably wrong but", "this might be a hot take". Hedge like a person, not like a paper.
- **Light typos and contractions.** "u", "ur", "tho", "kinda", "theres", "im", "its" (where "it's" is correct), missing apostrophes, double periods at the end..
- **Specific weird examples.** "i had this happen on a flask app last week" beats "for instance, in a typical web application".
- **Trailing thoughts.** "..." at the end of a sentence is very human. So is starting a sentence with "and" or "but".

## Example — bot vs human

**Bot:**
> Totally get it — the handoff board pre-structures the next session so you don't start from scratch. With fork you're basically doing that in-session without the manual transfer step. Either works; fork is just lower friction once you've got momentum going.

**Human:**
> yeah notion boards work but the upkeep gets old fast. fork basically gives u the handoff free, context just kinda sits in the new branch lol. only thing is if the session dies then its lost, so for anything multi day i still try to write it down somewhere just in case..

## Sub-specific calibration

- **Technical subs** (r/programming, r/ClaudeAI, r/MachineLearning): can be slightly more formal, but still no em-dashes, still mixed length, still one idea.
- **General subs** (r/AskReddit, r/mildlyinteresting): heavier slang, more typos, shorter.
- **Niche enthusiast subs**: match the in-group jargon if you know it, otherwise stay generic and don't fake it.

## Posting via browser-harness

Reddit's comment box is a contenteditable Lexical editor (not a textarea). After clicking into it:

```python
click(x, y)  # focus the comment box
type_text("your reply here")
# Don't use js() to set innerHTML — Lexical won't register it as user input
```

Submit button is `button[type="submit"]` inside the comment form, but is disabled until Lexical sees real keystrokes. If the button stays grey after `type_text`, you set the text via JS instead of typing — redo it with `type_text` or `press_key` calls.

After submit, Reddit takes 1-3 seconds to show the comment in the thread. Wait and re-screenshot before assuming it posted.
