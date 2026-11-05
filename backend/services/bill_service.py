from ..database import connect
def bills():
    with connect() as c:return [dict(x) for x in c.execute('SELECT * FROM bills ORDER BY due_date')]
def create(d):
    with connect() as c:
        cur=c.execute('INSERT INTO bills(name,amount,due_date,recurrence,approved) VALUES(?,?,?,?,?)',(d['name'],d.get('amount',0),d.get('due_date'),d.get('recurrence','monthly'),int(d.get('approved',False)))); return dict(c.execute('SELECT * FROM bills WHERE id=?',(cur.lastrowid,)).fetchone())
list_bills = bills
create_bill = create
list_bills = bills
create_bill = create
