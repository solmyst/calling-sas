"""Post-call request review. All follow-up records are local; no external tools."""
import hashlib
import json
from typing import Annotated
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, ConfigDict, Field, field_validator
from .engine import now, private
from .store import Store

Text = Annotated[str, Field(max_length=200)]


class StrictModel(BaseModel):
    model_config = ConfigDict(extra='forbid', str_strip_whitespace=True)


class Fields(StrictModel):
    service: Text = ''
    preferred_day: Text = ''
    preferred_time: Text = ''
    timezone: Text = ''
    business_need: Text = ''
    callback_window: Text = ''

    @field_validator('timezone')
    @classmethod
    def timezone_exists(cls, value):
        if value:
            try:
                ZoneInfo(value)
            except (ZoneInfoNotFoundError, ValueError):
                raise ValueError('Use an IANA timezone, such as Asia/Kolkata.') from None
        return value


class Revision(StrictModel):
    revision: int = Field(ge=0)


class Review(Revision):
    fields: Fields
    owner: str = Field(default='', max_length=80)
    notes: str = Field(default='', max_length=1000)


def transcript_hash(call):
    return hashlib.sha256(json.dumps(call['transcript'], sort_keys=True, ensure_ascii=False).encode()).hexdigest()


def request_state(call):
    return call.get('business_request') or dict(revision=0, status='needs_review',
        fields=Fields().model_dump(), evidence={}, owner='', notes='', audit=[], source='none')


def integrations():
    return {kind:dict(status='disabled', label='Not connected', external_actions=False)
            for kind in ('calendar', 'crm')}


def grounded_fields(raw, call):
    """Untrusted model output must quote customer words; no inferred dates/times."""
    if not isinstance(raw, dict) or set(raw) - set(Fields.model_fields):
        raise ValueError('Invalid extraction fields')
    values, evidence = {}, {}
    for key, item in raw.items():
        if item is None:
            continue
        if not isinstance(item, dict) or set(item) != {'value', 'quote', 'turn_index'}:
            raise ValueError('Missing extraction evidence')
        index, value, quote = item['turn_index'], item['value'], item['quote']
        if type(index) is not int or not 0 <= index < len(call['transcript']):
            raise ValueError('Invalid transcript reference')
        turn = call['transcript'][index]
        if (turn['role'] != 'customer' or not isinstance(value, str) or not isinstance(quote, str)
                or not value.strip() or not quote.strip() or len(quote) > 2000
                or quote not in turn['text'] or value.casefold() not in quote.casefold()):
            raise ValueError('Unsupported extracted value')
        values[key] = private(value)
        evidence[key] = dict(quote=private(quote), turn_index=index)
    return Fields.model_validate(values).model_dump(), evidence


def router(store, extractor):
    api = APIRouter(prefix='/api/calls/{id}/request')

    def call_for(db, id, revision=None):
        call = Store.get(db, 'calls', id)
        if not call:
            raise HTTPException(404, 'Conversation not found')
        if revision is not None:
            if call['status'] == 'in_progress':
                raise HTTPException(409, 'End the conversation before reviewing its request.')
            if request_state(call)['revision'] != revision:
                raise HTTPException(409, 'This request changed. Reopen it before saving.')
        return call

    def response(db, call):
        return dict(request=request_state(call), integrations=integrations(),
                    lead=Store.get(db, 'leads', 'lead-' + call['id']))

    def save(db, call, state, action):
        previous = request_state(call)
        state.update(revision=previous['revision'] + 1, updated_at=now(),
                     transcript_sha256=transcript_hash(call),
                     audit=(previous['audit'] + [dict(action=action, at=now(), actor='Workspace operator')])[-50:])
        call['business_request'] = state
        Store.put(db, 'calls', call)
        return response(db, call)

    @api.get('')
    def get(id: str):
        with store.transaction() as db:
            return response(db, call_for(db, id))

    @api.put('')
    def review(id: str, body: Review):
        with store.transaction() as db:
            call = call_for(db, id, body.revision)
            fields = {k:private(v) for k,v in body.fields.model_dump().items()}
            if not any(fields.values()):
                raise HTTPException(422, 'Record at least one request detail.')
            state = dict(fields=fields, owner=private(body.owner), notes=private(body.notes),
                         status='reviewed', source='operator', evidence={})
            return save(db, call, state, 'Request reviewed')

    @api.post('/extract')
    async def extract(id: str, body: Revision):
        with store.transaction() as db:
            call = call_for(db, id, body.revision)
            if not any(t['role'] == 'customer' for t in call['transcript']):
                raise HTTPException(422, 'No customer statements to extract.')
            before = transcript_hash(call)
        try:
            if extractor is None:
                raise ValueError('No configured extractor')
            raw = await extractor(call)
            fields, evidence = grounded_fields(raw, call)
        except Exception:
            raise HTTPException(503, 'Details could not be extracted. Your saved request is unchanged; enter the details manually.') from None
        with store.transaction() as db:
            latest = call_for(db, id, body.revision)
            if transcript_hash(latest) != before:
                raise HTTPException(409, 'The transcript changed. Reopen the conversation.')
            previous = request_state(latest)
            state = dict(fields=fields, evidence=evidence, status='needs_review', source='model',
                         owner=previous['owner'], notes=previous['notes'])
            return save(db, latest, state, 'Model suggestions extracted')

    @api.post('/follow-up')
    def follow_up(id: str, body: Revision):
        with store.transaction() as db:
            call = call_for(db, id, body.revision)
            state = request_state(call)
            if state['status'] != 'reviewed' or state.get('transcript_sha256') != transcript_hash(call):
                raise HTTPException(409, 'Review the current request before creating a follow-up.')
            if not state['owner']:
                raise HTTPException(422, 'Assign an owner before creating a follow-up.')
            contact = Store.get(db, 'contacts', call['contact_id'])
            if not contact or not contact['consent'] or contact['do_not_call'] or call.get('outcome') == 'opted_out':
                raise HTTPException(409, 'This contact is not eligible for follow-up.')
            existing = Store.get(db, 'leads', 'lead-' + id)
            if existing and existing['request_revision'] == state['revision']:
                return response(db, call)
            stamp = now()
            lead = dict(id='lead-' + id, call_id=id, contact_id=call['contact_id'],
                        contact_name=call['contact_snapshot']['name'], fields=state['fields'],
                        owner=state['owner'], notes=state['notes'], request_revision=state['revision'],
                        status='needs_team_follow_up', scope='workspace_local', sync_status='not_connected',
                        created_at=existing['created_at'] if existing else stamp, updated_at=stamp)
            Store.put(db, 'leads', lead)
            task = Store.get(db, 'tasks', 'task-' + id) or dict(id='task-' + id, created_at=stamp)
            task.update(call_id=id, contact_name=lead['contact_name'], owner=state['owner'],
                        title='Review request and verify availability' if state['fields']['service'] else 'Review customer request',
                        status='open', mode=call['mode'], lead_id=lead['id'], request_revision=state['revision'])
            Store.put(db, 'tasks', task)
            state['audit'] = (state['audit'] + [dict(action='Local lead and follow-up saved', at=stamp, actor='Workspace operator')])[-50:]
            call['business_request'] = state
            Store.put(db, 'calls', call)
            return response(db, call)

    return api
