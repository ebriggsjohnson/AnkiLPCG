# Saved poems and full-poem review

This local fork adds a saved source poem, editing in place, and two review modes.

## Install and try

1. Make an Anki collection backup; trying a separate test profile first is recommended.
2. Disable the original LPCG add-on in **Tools → Add-ons** to avoid duplicate menus.
3. Install `build.ankiaddon` from **Tools → Add-ons → Install from file**, then restart Anki.
4. Choose **Tools → Import Lyrics/Poetry**, paste your poem, and save.
5. Choose **Tools → Saved poems** to edit it or change review mode, then save.

**Breakdown** reviews the generated line/group cards. **Full poem**
reviews one card that asks you to recite the whole poem; reveal the text and grade
your recall using Anki's normal buttons. The inactive set is suspended. Switching
back restores cards suspended by the toggle, preserving their schedules. Cards
already manually suspended remain suspended.

Use one verse per line, with blank lines between stanzas. Chinese characters,
Chinese punctuation, indentation, and stanza breaks are preserved in the full-poem
answer. `#` still introduces comments, following LPCG's original input convention.
There is no automatic mastery threshold or speech recognition in this version.

## Existing poems

Import the original source again with the **exact same title and original grouping
settings**. The editor offers to connect existing LPCG notes in sequence order,
keeping their card IDs and review history. The generated breakdown count must match
the existing count. Use the same source order: this one-time adoption cannot infer
which passage you meant if you rearrange lines. Do not reimport a poem already
listed under Saved poems; edit it there instead.

## Editing and scheduling

- Saving a correction updates answers, context, title/author, tags, and the full-poem
  answer. Matching existing notes retain their IDs and schedules.
- Unchanged groups are matched across insertions and deletions. Equal-length edited
  blocks are treated as corrections in place. Ambiguous replacements get new notes.
- Changing group size creates a new breakdown rather than assigning old review
  histories to different-sized passages.
- Removed/replaced groups are kept as suspended notes; they are never deleted.
- The deck chooser controls newly created cards. Existing cards keep their decks.
- Each save is one undoable action, including source and mode. Failed saves roll
  back partial changes.
- Edit through Saved poems to keep all views consistent. Direct Browser edits of
  generated fields are overwritten by the next source save.
- Keep the master `LPCG Saved Poem` note: it holds the source/metadata and generates
  the whole-poem card. It lives in the collection and syncs along with the cards.
  Deleting a linked note manually will block source editing until it is restored
  from Undo or a backup. Avoid editing the master note's Metadata/PoemID fields.

The full-poem card renders normally on mobile after syncing. Source editing and
changing modes require the desktop add-on.

## Validation and build

Tested with Anki/aqt 25.9.5 and PyQt6. Tests use temporary real Anki collections;
UI coverage uses Qt's offscreen platform. Older Anki releases have not been verified.

```sh
python -m pytest -q
make addon
```

Packaging no longer requires generated Qt forms. The original license file and
upstream attribution remain in the source repository. This fork is hosted at
https://github.com/ebriggsjohnson/AnkiLPCG.
