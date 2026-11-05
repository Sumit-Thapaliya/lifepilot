from ..database import connect
def set_value(k,v):
    with connect() as c:c.execute('INSERT INTO memory(key,value) VALUES(?,?) ON CONFLICT(key) DO UPDATE SET value=excluded.value,updated_at=CURRENT_TIMESTAMP',(k,v))
    return {'key':k,'value':v}
def all_values():
    with connect() as c:return {r['key']:r['value'] for r in c.execute('SELECT key,value FROM memory')}
set_memory = set_value
get_memory = all_values
