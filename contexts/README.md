# `contexts/` — prior-context files for `-c`

## Why this folder exists

Without prior context the model answers cold, and on an ambiguous question it
guesses wrong. Asked *"how did you optimise the commits?"* with no context, it
assumed **git** commits. Given a Kafka briefing, it correctly read the same word
as consumer **offset** commits and answered from the right domain.

This folder is where those briefing files live, so they sit next to the tool
instead of scattered across the disk.

## What goes in one

Whatever orients the answer:

- the job posting and the seniority of the role
- the stack the interview will be about
- the language the interview is conducted in
- your own background, so the model does not claim things you cannot back up
- the questions you expect and how you want them answered

It reaches the model as a `system` message labelled as background information,
explicitly **not** as the question to answer.

## Usage

```bash
python main.py -c contexts/your_file.txt
```

The flag is optional and combines with `-P` and `-w`. The file is read and
validated **before** the hotkey listener starts, so the context is already in
place when you press the first hotkey.

## Format: number your sections

Only the sections that answer the question are sent to the model, so the file has
to be splittable. A section header is a line of `=` characters, a title that
starts with a number and a dot, and another line of `=`:

```
============================================================
4. CONSUMER LAG Y OBSERVABILIDAD
============================================================
```

Everything above the first numbered header — the banner and the "how to use this
sheet" rules — travels with every request, so keep that part short and put the
rules there. A file with no numbered headers still works: it is sent whole, which
costs about 4,200 tokens per question instead of 1,000-1,800.

Write each section so it stands on its own. The selector matches the words of the
question against the title and the body, and a section that only makes sense
after reading the previous one will arrive without it.

## Rules the loader enforces

`.md` or `.txt` only, up to 20,000 characters, valid UTF-8, not empty. A file
that breaks any of these prints the reason and exits with code 1 rather than
starting without the context you thought was loaded. See `phonexi/briefing.py`.

## Nothing in here is committed

`.gitignore` tracks this folder and this README, and ignores everything else in
it. Context files carry your name, your claimed experience and the company you
are interviewing with — this repository is public, so they stay local. Adding a
new `.txt` or `.md` here requires no `.gitignore` change; it is already ignored.

## Keeping this current

If the loader's rules change — the accepted extensions, the size limit, the way
the briefing is injected into the prompt — update the "Rules" section above and
the `-c` section of the root `README.md` in the same commit. The tests in
`tests/test_briefing.py` are the source of truth for the current behaviour.
