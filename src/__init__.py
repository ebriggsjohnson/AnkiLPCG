"""
LPCG - Lyrics/Poetry Cloze Generator
Copyright (c) 2016-2023 Soren Bjornstad <anki@sorenbjornstad.com>
                        and the LPCG community.

License: GNU AGPL, version 3 or later.
See LICENSE file or <http://www.gnu.org/licenses/agpl.html> for details.
"""

import sys

# don't try to set up the UI if running unit tests
if 'pytest' not in sys.modules:
    # pylint: disable=import-error, no-name-in-module
    # pylint: disable=invalid-name
    import aqt
    from aqt.qt import QAction, QInputDialog  # type: ignore
    from aqt.utils import showWarning

    from .lpcg_dialog import LPCGDialog
    from . import models
    from .poems import load_poems, ensure_master_model, MASTER_MODEL

    def open_dialog():
        "Launch the add-poem dialog."
        current_version = aqt.mw.col.get_config('lpcg_model_version', default="none")
        if not models.LpcgOne.is_at_version(current_version):
            showWarning(
                "Your LPCG note type is out of date and needs to be upgraded "
                "before you can use LPCG. To upgrade the note type, restart Anki "
                "and respond yes to the prompt.")
            return
        dialog = LPCGDialog(aqt.mw)
        dialog.exec()

    def open_saved_poem():
        poems = load_poems(aqt.mw.col)
        if not poems:
            showWarning('No saved poems yet. Import a poem first. To connect an '
                        'existing poem, paste its source with the same title and grouping settings.')
            return
        entries = sorted(poems.items(), key=lambda item: item[1]['title'])
        labels = [f"{p['title']} — {p['author']} ({p['mode']}) [{pid[:8]}]"
                  for pid, p in entries]
        label, ok = QInputDialog.getItem(aqt.mw, 'Saved poems', 'Edit poem / change review mode',
                                       labels, 0, False)
        if ok:
            pid, poem = entries[labels.index(label)]
            dialog = LPCGDialog(aqt.mw, pid, poem)
            dialog.exec()

    def update_saved_poem_template():
        if aqt.mw.col.models.by_name(MASTER_MODEL):
            ensure_master_model(aqt.mw.col)

    if aqt.mw is not None:
        action = QAction(aqt.mw)
        action.setText("Import &Lyrics/Poetry")
        aqt.mw.form.menuTools.addAction(action)
        action.triggered.connect(open_dialog)

        saved_action = QAction('Saved poems', aqt.mw)
        aqt.mw.form.menuTools.addAction(saved_action)
        saved_action.triggered.connect(open_saved_poem)

        aqt.gui_hooks.profile_did_open.append(models.ensure_note_type)

        aqt.gui_hooks.profile_did_open.append(update_saved_poem_template)
