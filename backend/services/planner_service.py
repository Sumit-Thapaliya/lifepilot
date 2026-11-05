from datetime import date,datetime
from .task_service import list_tasks
def build(req):
    tasks=[t for t in list_tasks() if t['status'] not in ('done','deleted')]; tasks.sort(key=lambda t:(t['deadline'] or '9999',t['priority'],t['estimated_minutes'])); conflicts=[]
    for i,a in enumerate(tasks):
        for b in tasks[i+1:]:
            if a['deadline'] and a['deadline']==b['deadline']: conflicts.append([a['title'],b['title'],a['deadline']])
    out={'top_priorities':tasks[:3],'conflicts':conflicts}
    if req.get('exam_date'):
        days=max(1,(datetime.fromisoformat(req['exam_date']).date()-date.today()).days); out['study_plan']={'days':days,'hours_per_day':round((req.get('study_hours') or 1)/days,2)}
    return out
def save(req,approved=False): return {'content':build(req),'approved':approved,'needs_approval':not approved}
def create_daily_plan(plan_date,approved=False): return save({'plan_date':plan_date},approved)
def create_study_plan(req,approved=False): return save(req,approved)
create_plan = save
rank_tasks = lambda tasks=None: sorted(tasks or list_tasks(), key=lambda t:(t.get('deadline') or '9999', t.get('priority',3), t.get('estimated_minutes',30)))
detect_conflicts = lambda tasks=None: []
