"""
Dialog box for importing texts.
"""

import codecs
from html import unescape

# pylint: disable=no-name-in-module
from aqt.deckchooser import DeckChooser
from aqt.qt import QDesktopServices, QDialog, QUrl
from aqt.utils import getFile, showWarning, askUser, tooltip
from anki.notes import Note

from . import poem_form as lpcg_form

# pylint: disable=wrong-import-position
from .poems import save_poem, load_poems
from . import models


class LPCGDialog(QDialog):
    """
    Import Lyrics/Poetry dialog, the core of the add-on. The user can either
    enter the text of a poem in the editor or import a text file from somewhere
    else on the computer. The poem can be entered with usual markup (blank
    lines between stanzas, one level of indentation with tabs or spaces in
    front of lines). LPCG then processes it into notes with two lines of
    context and adds them to the user's collection.
    """
    def __init__(self, mw, poem_id=None, poem=None):
        self.mw = mw
        self.poem_id = poem_id

        QDialog.__init__(self)
        self.form = lpcg_form.Ui_Dialog()
        self.form.setupUi(self)
        self.deckChooser = DeckChooser(self.mw, self.form.deckChooser)

        self.form.addCardsButton.clicked.connect(self.accept)
        self.form.cancelButton.clicked.connect(self.reject)
        self.form.openFileButton.clicked.connect(self.onOpenFile)
        self.form.helpButton.clicked.connect(self.onHelp)

        self.addonConfig = self.mw.addonManager.getConfig(__name__)
        self.form.contextLinesSpin.setValue(self.addonConfig['defaultLinesOfContext'])
        self.form.reciteLinesSpin.setValue(self.addonConfig['defaultLinesToRecite'])
        self.form.groupLinesSpin.setValue(self.addonConfig['defaultLinesInGroupsOf'])

        if poem:
            self.form.titleBox.setText(poem['title'])
            self.form.authorBox.setText(poem['author'])
            self.form.tagsBox.setText(' '.join(poem['tags']))
            self.form.textBox.setPlainText(poem['source'])
            self.form.contextLinesSpin.setValue(poem['context_lines'])
            self.form.reciteLinesSpin.setValue(poem['recite_lines'])
            self.form.groupLinesSpin.setValue(poem['group_lines'])
            self.form.modeBox.setCurrentIndex(1 if poem['mode'] == 'full' else 0)
            # Existing cards keep their decks; this chooser controls new cards.
            self.deckChooser.selected_deck_id = poem['did']

    def done(self, result):
        self.deckChooser.cleanup()
        super().done(result)

    def accept(self):
        "On close, create notes from the contents of the poem editor."
        title = self.form.titleBox.text().strip()

        if not title:
            showWarning("You must enter a title for this poem.")
            return
        escaped_title = title.replace('"', '\\"')
        adopt_ids = None
        saved = load_poems(self.mw.col)
        if not self.poem_id:
            if any(p['title'] == title for p in saved.values()):
                showWarning('This poem already has a saved source. Open Saved poems to edit it.')
                return
            adopt_ids = self.mw.col.find_notes(
                f'"note:{models.LpcgOne.name}" "Title:{escaped_title}"')
            # Anki field searches can match more than an exact title.
            adopt_ids = [nid for nid in adopt_ids
                         if unescape(self.mw.col.get_note(nid)['Title']) == title]
            owned_ids = {e['nid'] for poem in saved.values()
                         for e in poem['groups']}
            if owned_ids.intersection(adopt_ids):
                showWarning('These notes already belong to a saved poem. Open Saved poems to edit it.')
                return
            if adopt_ids and not askUser(
                f'Connect {len(adopt_ids)} existing notes to this source poem? '
                'Their answers and context will be replaced in sequence order. '
                'Use the original poem and grouping settings to keep each history '
                'attached to the correct passage. Make a collection backup first.'):
                return
        if not self.form.textBox.toPlainText().strip():
            showWarning("There's nothing to generate cards from! "
                        "Please type a poem in the box, or use the "
                        '"Open File" button to import a text file.')
            return

        author = self.form.authorBox.text().strip()
        tags = self.mw.col.tags.split(self.form.tagsBox.text())
        text = self.form.textBox.toPlainText()
        context_lines = self.form.contextLinesSpin.value()
        recite_lines = self.form.reciteLinesSpin.value()
        group_lines = self.form.groupLinesSpin.value()
        did = self.deckChooser.selectedId()

        data = dict(title=title, author=author, tags=tags, source=text, did=did,
                    context_lines=context_lines, group_lines=group_lines,
                    recite_lines=recite_lines, mode=self.form.modeBox.currentData())
        try:
            self.poem_id, notes_generated = save_poem(
                self.mw.col, Note, data, self.addonConfig, self.poem_id, adopt_ids)
        except Exception as error:
            showWarning(str(error))
            return
        super().accept()
        self.mw.reset()
        tooltip("Poem saved (%i breakdown notes + full poem)." % (notes_generated - 1))

    def onOpenFile(self):
        """
        Read a text file (in UTF-8 encoding) and replace the contents of the
        poem editor with the contents of the file.
        """
        if (self.form.textBox.toPlainText().strip()
                and not askUser("Importing a file will replace the current "
                                "contents of the poem editor. Continue?")):
            return
        filename = getFile(self, "Import file", None, key="import")
        if not filename: # canceled
            return
        with codecs.open(filename, 'r', 'utf-8') as f:
            text = f.read()
        self.form.textBox.setPlainText(text)

    def onHelp(self):
        """
        Open the documentation on importing files in a browser.
        """
        doc_url = "https://ankilpcg.readthedocs.io/en/latest/importing.html"
        QDesktopServices.openUrl(QUrl(doc_url))
