"""Saved poem sources and in-place generation, independent of the Anki UI."""
from difflib import SequenceMatcher
from html import escape, unescape
import json
from uuid import uuid4

from .gen_notes import cleanse_text, _poemlines_from_textlines

MASTER_MODEL = 'LPCG Saved Poem'
MASTER_FRONT = '<h3>{{Title}}</h3>{{#Author}}{{Author}}{{/Author}}'
MASTER_BACK = '{{FrontSide}}<hr id="answer">{{Line}}'
OLD_MASTER_FRONT = '<h3>{{Title}}</h3>{{Author}}<hr>{{Prompt}}'


def load_poems(col):
    if col.models.by_name(MASTER_MODEL) is None:
        return {}
    poems = {}
    for nid in col.find_notes('"note:LPCG Saved Poem"'):
        note = col.get_note(nid)
        if note['Metadata']:
            poems[note['PoemID']] = json.loads(unescape(note['Metadata']))
    return poems


def ensure_master_model(col):
    model = col.models.by_name(MASTER_MODEL)
    if model:
        template = model['tmpls'][0]
        # Update the original template without overwriting user customizations.
        if template['qfmt'] == OLD_MASTER_FRONT:
            template['qfmt'] = MASTER_FRONT
            template['afmt'] = MASTER_BACK
            template['name'] = 'Full poem'
            col.models.save(model)
        return model
    model = col.models.new(MASTER_MODEL)
    for field in ('PoemID', 'Title', 'Author', 'Line', 'Prompt', 'Metadata'):
        col.models.add_field(model, col.models.new_field(field))
    template = col.models.new_template('Full poem')
    template['qfmt'] = MASTER_FRONT
    template['afmt'] = MASTER_BACK
    col.models.add_template(model, template)
    model['css'] = ('.card { font-family: "Songti SC", "Noto Serif CJK SC", '
                    '"SimSun", serif; font-size: 24px; text-align: center; }')
    col.models.add(model)
    return model


def match_groups(old, new):
    """Match unchanged groups; equal-length replacements are text corrections.

    Unequal replacements get new cards rather than inheriting unrelated history.
    Disable the popular-element heuristic for poems with repeated refrains.
    """
    matched = {}
    for kind, a, b, c, d in SequenceMatcher(None, old, new, autojunk=False).get_opcodes():
        if kind == 'equal' or (kind == 'replace' and b - a == d - c):
            matched.update((c + i, a + i) for i in range(d - c))
    return matched


def full_poem_html(source):
    lines = []
    for line in source.splitlines():
        if line.lstrip().startswith('#'):
            continue
        line = line.split('#', 1)[0].rstrip()
        lines.append(escape(line) if line.strip() else '')
    return '<div style="white-space:pre-wrap;line-height:1.8">' + '\n'.join(lines).strip('\n') + '</div>'


def apply_mode(col, record, mode, undo_id=None):
    """Only resume cards that this toggle itself suspended."""
    if mode not in ('breakdown', 'full'):
        raise ValueError('Unknown review mode')
    owned = set(record.get('mode_suspended', []))
    active = [entry['nid'] for entry in record['groups']]
    inactive = [record['full_nid']]
    if mode == 'full':
        active, inactive = inactive, active
    for nid in inactive + record.get('retired', []):
        for card in col.get_note(nid).cards():
            if card.queue != -1:
                col.sched.suspend_cards([card.id])
                if undo_id is not None:
                    col.merge_undo_entries(undo_id)
                owned.add(card.id)
    for nid in active:
        for card in col.get_note(nid).cards():
            if card.id in owned:
                if card.queue == -1:
                    col.sched.unsuspend_cards([card.id])
                    if undo_id is not None:
                        col.merge_undo_entries(undo_id)
                owned.discard(card.id)
    record['mode_suspended'] = sorted(owned)
    record['mode'] = mode


def save_poem(col, note_constructor, data, config, poem_id=None, adopt_ids=None):
    """One undoable action; roll back partial writes if generation fails."""
    undo_id = col.add_custom_undo_entry('Save LPCG poem')
    try:
        result = _save_poem(col, note_constructor, data, config, poem_id, adopt_ids, undo_id)
        col.merge_undo_entries(undo_id)
        return result
    except Exception:
        col.merge_undo_entries(undo_id)
        col.undo()
        raise


def _save_poem(col, note_constructor, data, config, poem_id, adopt_ids, undo_id):
    """Create/update notes without deleting cards or resetting their schedules."""
    if data['mode'] not in ('full', 'breakdown'):
        raise ValueError('Unknown review mode')
    poems = load_poems(col)
    poem_id = poem_id or uuid4().hex
    previous = poems.get(poem_id, {})
    source = data['source']
    # Escape literal markup before the generator adds its own HTML.
    text = cleanse_text(escape(source, quote=False), config)
    if not text:
        raise ValueError('The poem contains no text lines.')
    parsed = _poemlines_from_textlines(text, data['group_lines'])
    keys = [tuple(line._get_text(1)) for line in parsed]
    if adopt_ids:
        owned = {e['nid'] for poem in poems.values() for e in poem['groups']}
        if owned.intersection(adopt_ids):
            raise ValueError('These notes already belong to a saved poem.')
        notes = sorted((col.get_note(nid) for nid in adopt_ids),
                       key=lambda n: int(n['Sequence']))
        if len(notes) != len(keys):
            raise ValueError('Existing note count differs from the generated breakdown. '
                             'Use the original grouping settings before adopting this poem.')
        previous = {'groups': [{'key': list(key), 'nid': note.id}
                               for key, note in zip(keys, notes)]}
    old_groups = previous.get('groups', [])
    matches = (match_groups([tuple(e['key']) for e in old_groups], keys)
               if previous.get('group_lines', data['group_lines']) == data['group_lines']
               else {})
    model = col.models.by_name('LPCG 1.0')
    if model is None:
        raise ValueError('The LPCG note type is missing. Restart Anki first.')
    required = {'Line', 'Context', 'Title', 'Author', 'Sequence', 'Prompt'}
    if not required.issubset({f['name'] for f in model['flds']}):
        raise ValueError('The LPCG note type is missing required fields.')
    # Resolve every saved reference before writing anything (e.g. deleted notes).
    existing = {e['nid']: col.get_note(e['nid']) for e in old_groups}
    for nid in previous.get('retired', []):
        col.get_note(nid)
    full = (col.get_note(previous['full_nid']) if 'full_nid' in previous
            else note_constructor(col, ensure_master_model(col)))
    col.merge_undo_entries(undo_id)
    record = dict(data)
    record['groups'] = []
    record['retired'] = list(previous.get('retired', []))
    record['mode_suspended'] = list(previous.get('mode_suspended', []))
    for i, line in enumerate(parsed):
        old = old_groups[matches[i]] if i in matches else None
        note = existing[old['nid']] if old else note_constructor(col, model)
        note['Prompt'] = ''
        line.populate_note(note, escape(data['title']), escape(data['author']),
                           data['tags'], data['context_lines'], data['recite_lines'], data['did'])
        if old:
            col.update_note(note)
        else:
            col.add_note(note, data['did'])
        col.merge_undo_entries(undo_id)
        record['groups'].append({'key': list(keys[i]), 'nid': note.id})
    used = {e['nid'] for e in record['groups']}
    record['retired'].extend(e['nid'] for e in old_groups if e['nid'] not in used)
    full['Title'] = escape(data['title'])
    full['Author'] = escape(data['author'])
    full['PoemID'] = poem_id
    full['Prompt'] = ''
    full['Line'] = full_poem_html(source)
    full.tags = data['tags']
    if 'full_nid' in previous:
        col.update_note(full)
    else:
        col.add_note(full, data['did'])
    col.merge_undo_entries(undo_id)
    record['full_nid'] = full.id
    apply_mode(col, record, data['mode'], undo_id)
    full['Metadata'] = escape(json.dumps(record, ensure_ascii=False))
    col.update_note(full)
    return poem_id, len(record['groups']) + 1
