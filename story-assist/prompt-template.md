# Story Assembly Prompt — paste-into-Claude version

This is the zero-setup way to use story-assist. Total time: ~2 minutes.

## How to use it

1. Run the **transcribe** tool on your interview folder. It creates
   `transcripts/_ALL_TRANSCRIPTS.txt`.
2. Open [claude.ai](https://claude.ai) and start a new chat.
3. Copy the entire prompt below, fill in the two `<<< >>>` blanks, and paste
   it in. For the transcripts, open `_ALL_TRANSCRIPTS.txt`, Select All, Copy,
   and paste where indicated (or attach the file to the chat instead).
4. You'll get back a selects list with exact timecodes, a suggested story
   order, ranked alternate takes, and a list of gaps to cover with B-roll/VO.

Only transcript text goes to Claude — never footage.

---

## THE PROMPT (copy everything below this line)

You are an experienced documentary/corporate video editor's assistant. I'm
cutting a corporate interview piece and need you to find the usable statements
in my transcripts and propose a story structure.

**The deliverable:** a 2:30–4:00 corporate video.

**The client's narrative goal:**

<<< PASTE THE CLIENT BRIEF / NARRATIVE GOAL HERE — a sentence or a paragraph,
whatever you have. Example: "Celebrate the ops team's turnaround this year;
upbeat; must mention the new Dallas facility; ends on looking forward to 2027." >>>

**Rules — follow these exactly:**

1. **Never invent or paraphrase quotes.** Every quote must appear verbatim in
   the transcripts below, and every timecode must be copied from the transcript
   line the quote comes from. If you are not sure of a timecode, say so rather
   than guessing.
2. Prefer statements that are **complete sentences with clean delivery** — no
   false starts, no mid-sentence restarts, no trailing "um, yeah". Note when a
   quote needs a breath edit (e.g. "usable from 'The biggest change…'").
3. The speaker of each quote is identified by the CLIP/SPEAKER header above it.

**Give me exactly these four sections:**

### 1. Selected statements
A table with one row per select:
| # | Speaker | Clip | In | Out | Quote (verbatim) | Why it serves the narrative |

In/Out are the `[HH:MM:SS]` timestamps from the transcript (Out = the next
segment's timestamp or ~the quote's end). 10–20 selects for a 2:30–4:00 piece.

### 2. Suggested story order
Arrange the selects into a running order using this act structure, with a
one-line rationale per act:
- **Hook** (0:00–0:20): the strongest emotional or surprising line
- **Context** (0:20–0:50): who/what/why — set the scene
- **Substance** (0:50–2:45): the meat — 2–3 mini-topics, each built from
  complementary quotes from different speakers where possible
- **Close** (last 20–40s): resolution / forward-looking line

Estimate the running time of the assembled selects and say whether it's over
or under target.

### 3. Alternate takes
Where the same idea is said more than once (by the same or different speakers),
list the alternatives ranked by delivery quality (complete sentence, no false
starts, energy), with timecodes, so I can choose on the timeline.

### 4. Gaps
What does the narrative goal need that is NOT in the footage? For each gap,
suggest whether it's a B-roll + VO fix, a graphic, or a pickup question to
request. Keep it practical.

**The transcripts:**

<<< PASTE THE ENTIRE CONTENTS OF _ALL_TRANSCRIPTS.txt HERE
(or attach the file to the chat and write "see attached file") >>>

---

## After you get the answer

- Sanity-check 2–3 timecodes by scrubbing to them in Premiere. If they're
  solid, trust the rest; if one is off, tell Claude "the timecode for select
  #N is wrong, re-check it against the transcript" and it will correct itself.
- Follow-ups that work well:
  - "Cut this down to a 60-second version."
  - "The client says don't mention X — rework the order without those selects."
  - "Give me two more alternates for the hook."
