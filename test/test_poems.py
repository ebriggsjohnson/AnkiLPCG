"""Exercise saving and suspension with real temporary Anki collections."""
import pytest
from anki.collection import Collection
from anki.notes import Note

from src.poems import save_poem, load_poems, match_groups, full_poem_html
from src.gen_notes import cleanse_text

CONFIG = {'endOfTextMarker': ' □', 'endOfStanzaMarker': ' ⊗'}
SOURCE = '床前明月光，\n疑是地上霜。\n\n举头望明月，\n低头思故乡。'


@pytest.fixture
def col(tmp_path):
    collection = Collection(str(tmp_path / 'collection.anki2'))
    model = collection.models.new('LPCG 1.0')
    for name in ('Line', 'Context', 'Title', 'Author', 'Sequence', 'Prompt'):
        collection.models.add_field(model, collection.models.new_field(name))
    template = collection.models.new_template('Poem')
    template['qfmt'] = '{{Title}} {{Context}} {{Prompt}}'
    template['afmt'] = '{{Line}}'
    collection.models.add_template(model, template)
    collection.models.add(model)
    yield collection
    collection.close()


def data(**changes):
    result = dict(title='静夜思', author='李白', source=SOURCE, tags=['中文'],
                  did=1, context_lines=2, recite_lines=1, group_lines=1, mode='breakdown')
    result.update(changes)
    return result


def save(col, values=None, pid=None):
    return save_poem(col, Note, values or data(), CONFIG, pid)[0]


def cards(col, record):
    return [col.get_note(e['nid']).cards()[0] for e in record['groups']]


def test_correct_typo_updates_answer_and_context_keeps_schedule(col):
    pid = save(col)
    original = load_poems(col)[pid]
    card = cards(col, original)[0]
    card.type, card.queue, card.ivl, card.due = 2, 2, 35, 60
    col.update_card(card)
    values = data(source=SOURCE.replace('明月光', '明月光辉'))
    save(col, values, pid)
    updated = load_poems(col)[pid]
    assert [e['nid'] for e in updated['groups']] == [e['nid'] for e in original['groups']]
    revised = cards(col, updated)[0]
    assert (revised.id, revised.ivl, revised.due) == (card.id, 35, 60)
    assert '明月光辉' in col.get_note(updated['groups'][0]['nid'])['Line']
    assert '明月光辉' in col.get_note(updated['groups'][1]['nid'])['Context']
    assert '明月光辉' in col.get_note(updated['full_nid'])['Line']


def test_toggle_preserves_history_and_manual_suspension(col):
    pid = save(col)
    record = load_poems(col)[pid]
    original = cards(col, record)
    col.sched.suspend_cards([original[0].id])
    card = original[1]
    card.type, card.queue, card.ivl, card.due = 2, 2, 40, 90
    col.update_card(card)
    save(col, data(mode='full'), pid)
    record = load_poems(col)[pid]
    assert all(c.queue == -1 for c in cards(col, record))
    full_card = col.get_note(record['full_nid']).cards()[0]
    assert full_card.queue != -1
    assert col.get_note(record['full_nid'])['Prompt'] == ''
    save(col, data(), pid)
    record = load_poems(col)[pid]
    restored = cards(col, record)
    assert restored[0].queue == -1
    assert restored[1].queue == 2
    assert (restored[1].ivl, restored[1].due) == (40, 90)
    assert col.get_note(record['full_nid']).cards()[0].queue == -1
    # Repeated saves don't create duplicate cards.
    save(col, data(), pid)
    assert col.note_count() == 5


def test_insert_delete_retains_matching_ids_and_archives_removed(col):
    pid = save(col)
    original = load_poems(col)[pid]
    inserted = data(source=SOURCE.replace('疑是地上霜。', '新的一句。\n疑是地上霜。'))
    save(col, inserted, pid)
    updated = load_poems(col)[pid]
    assert updated['groups'][0]['nid'] == original['groups'][0]['nid']
    assert updated['groups'][2]['nid'] == original['groups'][1]['nid']
    added = updated['groups'][1]['nid']
    save(col, data(), pid)
    record = load_poems(col)[pid]
    assert added in record['retired']
    assert col.get_note(added).cards()[0].queue == -1
    save(col, data(mode='full'), pid)
    save(col, data(), pid)
    assert col.get_note(added).cards()[0].queue == -1


def test_full_poem_preserves_chinese_stanzas_and_escapes_markup(col):
    assert SOURCE in full_poem_html(SOURCE)
    assert '&lt;script&gt;' in full_poem_html('诗<script>')
    pid = save(col, data(source='诗<字>\n第二句'))
    record = load_poems(col)[pid]
    assert '&lt;字&gt;' in col.get_note(record['groups'][0]['nid'])['Line']
    assert load_poems(col)[pid]['source'] == '诗<字>\n第二句'


def test_adopt_existing_notes(col):
    ids = []
    from src.gen_notes import _poemlines_from_textlines
    for line in _poemlines_from_textlines(cleanse_text(SOURCE, CONFIG), 1):
        note = Note(col, col.models.by_name('LPCG 1.0'))
        line.populate_note(note, '静夜思', '李白', [], 2, 1, 1)
        col.add_note(note, 1)
        ids.append(note.id)
    pid, _ = save_poem(col, Note, data(), CONFIG, adopt_ids=list(reversed(ids)))
    assert [e['nid'] for e in load_poems(col)[pid]['groups']] == ids
    assert col.note_count() == 5


def test_repeated_lines_and_unequal_replacements():
    assert match_groups(['甲', '乙', '甲'], ['甲', '新', '乙', '甲']) == {0: 0, 2: 1, 3: 2}
    assert match_groups(['甲', '乙'], ['丙', '丁', '戊']) == {}


@pytest.mark.parametrize('source', ['', '\n\n', '# 注释', ' # 注释\n\n'])
def test_empty_input_rejected_without_notes(col, source):
    with pytest.raises(ValueError):
        save(col, data(source=source))
    assert col.note_count() == 0


def test_save_is_one_undoable_action(col):
    pid = save(col)
    before = load_poems(col)[pid]
    save(col, data(source=SOURCE.replace('明月光', '明月光辉'), mode='full'), pid)
    col.undo()
    assert load_poems(col)[pid] == before
    assert '明月光辉' not in col.get_note(before['groups'][0]['nid'])['Line']
    assert cards(col, before)[0].queue != -1


def test_failure_rolls_back_partial_update(col, monkeypatch):
    pid = save(col)
    before = load_poems(col)[pid]
    original_update = col.update_note
    calls = []

    def fail_second(note):
        calls.append(note.id)
        if len(calls) == 2:
            raise RuntimeError('Simulated write failure')
        return original_update(note)

    monkeypatch.setattr(col, 'update_note', fail_second)
    with pytest.raises(RuntimeError):
        save(col, data(source=SOURCE.replace('明月光', '明月光辉')), pid)
    assert load_poems(col)[pid] == before
    assert '明月光辉' not in col.get_note(before['groups'][0]['nid'])['Line']


def test_deleted_note_does_not_partially_update_source(col):
    pid = save(col)
    before = load_poems(col)[pid]
    col.remove_notes([before['groups'][1]['nid']])
    with pytest.raises(Exception):
        save(col, data(source=SOURCE.replace('明月光', '明月光辉')), pid)
    assert load_poems(col)[pid] == before
    assert '明月光辉' not in col.get_note(before['groups'][0]['nid'])['Line']


def test_large_poem_single_undo_and_changed_grouping(col):
    source = '\n'.join(f'诗句{i}' for i in range(100))
    pid = save(col, data(source=source))
    before = load_poems(col)[pid]
    assert len(before['groups']) == 100
    save(col, data(source=source, group_lines=2), pid)
    after = load_poems(col)[pid]
    assert len(after['groups']) == 50
    assert len(after['retired']) == 100
    col.undo()
    assert load_poems(col)[pid] == before
    assert col.note_count() == 101


def test_dialog_load_edit_and_toggle(col, monkeypatch):
    import os
    os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
    from types import SimpleNamespace
    import aqt
    from anki.lang import set_lang
    set_lang('en')
    from aqt.qt import QApplication
    from src import lpcg_dialog
    app = QApplication.instance() or QApplication([])
    mw = SimpleNamespace(col=col, addonManager=SimpleNamespace(getConfig=lambda _: dict(
        CONFIG, defaultLinesOfContext=2, defaultLinesToRecite=1, defaultLinesInGroupsOf=1)),
        reset=lambda: None)
    monkeypatch.setattr(lpcg_dialog, 'tooltip', lambda _: None)
    monkeypatch.setattr(lpcg_dialog, 'showWarning', lambda text: pytest.fail(text))
    pid = save(col)
    dialog = lpcg_dialog.LPCGDialog(mw, pid, load_poems(col)[pid])
    assert dialog.form.titleBox.text() == '静夜思'
    assert dialog.form.textBox.toPlainText() == SOURCE
    dialog.form.modeBox.setCurrentIndex(1)
    dialog.form.textBox.setPlainText(SOURCE.replace('明月光', '明月光辉'))
    dialog.accept()
    assert load_poems(col)[pid]['mode'] == 'full'
    assert '明月光辉' in load_poems(col)[pid]['source']
    app.processEvents()


def test_original_model_can_be_created_and_used(tmp_path, monkeypatch):
    import aqt
    from types import SimpleNamespace
    from src import models
    collection = Collection(str(tmp_path / 'fresh.anki2'))
    try:
        monkeypatch.setattr(aqt, 'mw', SimpleNamespace(col=collection))
        models.ensure_note_type()
        pid = save(collection)
        record = load_poems(collection)[pid]
        assert '静夜思' in cards(collection, record)[0].question()
        assert '床前明月光' in collection.get_note(record['full_nid']).cards()[0].answer()
    finally:
        collection.close()


def test_quotes_are_not_treated_as_comments_and_overlap_updates(col):
    source = "月光\nIt's a poem / ‘诗’\n最后一句"
    pid = save(col, data(source=source, recite_lines=2, mode='full'))
    record = load_poems(col)[pid]
    assert "It's a poem" in col.get_note(record['groups'][0]['nid'])['Line']
    assert all(c.queue == -1 for c in cards(col, record))
    save(col, data(source=source.replace('a poem', 'the poem'), recite_lines=2), pid)
    updated = load_poems(col)[pid]
    assert "It's the poem" in col.get_note(updated['groups'][0]['nid'])['Line']
    assert "It's the poem" in col.get_note(updated['groups'][1]['nid'])['Line']
    assert "It's the poem" in col.get_note(updated['groups'][2]['nid'])['Context']


def test_existing_full_template_is_simplified_without_changing_cards(col):
    from src.poems import ensure_master_model, MASTER_MODEL, OLD_MASTER_FRONT
    pid = save(col)
    record = load_poems(col)[pid]
    before = col.get_note(record['full_nid']).cards()[0]
    model = col.models.by_name(MASTER_MODEL)
    model['tmpls'][0]['qfmt'] = OLD_MASTER_FRONT
    model['tmpls'][0]['name'] = 'Full poem / 全诗'
    col.models.save(model)
    ensure_master_model(col)
    after = col.get_note(record['full_nid']).cards()[0]
    assert (after.id, after.queue, after.due, after.ivl) == (before.id, before.queue, before.due, before.ivl)
    assert '<hr' not in after.question()
    assert 'Recite' not in after.question()
    assert '静夜思' in after.question() and '李白' in after.question()
    assert after.answer().count('<hr') == 1
    assert '床前明月光' in after.answer()
    assert col.models.by_name(MASTER_MODEL)['tmpls'][0]['name'] == 'Full poem'
    model = col.models.by_name(MASTER_MODEL)
    model['tmpls'][0]['qfmt'] = '{{Title}} custom layout'
    col.models.save(model)
    ensure_master_model(col)
    assert col.models.by_name(MASTER_MODEL)['tmpls'][0]['qfmt'] == '{{Title}} custom layout'
