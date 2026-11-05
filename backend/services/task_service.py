import re
from datetime import date, timedelta
from ..database import connect
CATEGORIES={'study','personal','bill','health','household','work'}
def parse_task_text(text):
    low=text.lower(); category=next((c for c in CATEGORIES if c in low),'personal')
    priority=1 if any(x in low for x in ('urgent','today','asap','immediately')) else (2 if any(x in low for x in ('important','soon')) else 3)
    deadline=str(date.today()) if 'today' in low else (str(date.today()+timedelta(days=1)) if 'tomorrow' in low else None)
    if deadline is None:
        match=re.search(r'\b(?:by|on|due)\s+([^,.;]+)',text,flags=re.I)
        deadline=match.group(1).strip() if match else None
    title=re.sub(r'^\s*(add|create|remember|track)\s+(a\s+)?task\s*(to\s+)?','',text,flags=re.I)
    title=re.split(r'\s+(?:by|on|due)\s+',title,maxsplit=1,flags=re.I)[0]
    title=re.sub(r'\b(remind me to|please|urgent|asap|immediately|important|soon)\b','',title,flags=re.I).strip(' .,') or text
    return {'title':title,'deadline':deadline,'category':category,'priority':priority,'notes':text}
def create_task(data, approved=False):
    if not approved:return {'status':'pending_approval','preview':data}
    if data.get('text') and not data.get('title'): data={**parse_task_text(data['text']),**data}; data.pop('text',None)
    with connect() as c:
        cur=c.execute('INSERT INTO tasks(title,deadline,category,priority,notes,estimated_minutes,approved) VALUES(?,?,?,?,?,?,?)',(data.get('title'),data.get('deadline'),data.get('category','personal'),data.get('priority',3),data.get('notes',''),data.get('estimated_minutes',30),1)); return dict(c.execute('SELECT * FROM tasks WHERE id=?',(cur.lastrowid,)).fetchone())
def list_tasks(status=None):
    with connect() as c:return [dict(r) for r in c.execute('SELECT * FROM tasks WHERE (? IS NULL OR status=?) ORDER BY deadline,priority,estimated_minutes',(status,status))]
def get_task(task_id):
    with connect() as c:r=c.execute('SELECT * FROM tasks WHERE id=?',(task_id,)).fetchone(); return dict(r) if r else None
def update_task(task_id, updates):
    vals={k:v for k,v in updates.items() if v is not None and k in {'title','deadline','category','priority','notes','estimated_minutes','status'}}
    if not vals:return get_task(task_id)
    with connect() as c:c.execute('UPDATE tasks SET '+','.join(k+'=?' for k in vals)+' WHERE id=?',(*vals.values(),task_id))
    return get_task(task_id)
def postpone_task(task_id, postponed_to):
    with connect() as c:
        c.execute('UPDATE tasks SET status="postponed", postponed_to=? WHERE id=?',(postponed_to,task_id))
    return get_task(task_id)
def delete_task(task_id, approved=False):
    if not approved:return {'status':'pending_approval','task_id':task_id}
    with connect() as c:c.execute('DELETE FROM tasks WHERE id=?',(task_id,)); return {'deleted':task_id}
