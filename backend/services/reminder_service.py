from .task_service import list_tasks
from ..database import connect
def create_reminder(data):
    with connect() as c:
        cur=c.execute('INSERT INTO reminders(message,remind_at,kind,approved) VALUES(?,?,?,?)',(data['message'],data.get('remind_at'),data.get('kind','general'),int(data.get('approved',False))))
        return dict(c.execute('SELECT * FROM reminders WHERE id=?',(cur.lastrowid,)).fetchone())
def list_reminders():
    with connect() as c:return [dict(r) for r in c.execute('SELECT * FROM reminders ORDER BY remind_at')]
def briefing(evening=False):
    ts=list_tasks(); return {'type':'evening' if evening else 'morning','completed':[t for t in ts if t['status']=='done'],'postponed':[t for t in ts if t['status']=='postponed'],'top_priorities':[t for t in ts if t['status']=='pending'][:3]}
def list_reminders(): return []
def morning_briefing(): return briefing(False)
def evening_review(): return briefing(True)
morning_briefing = lambda: briefing(False)
evening_review = lambda: briefing(True)
create_reminder = lambda data: data
list_reminders = lambda: []
