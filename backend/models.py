from dataclasses import dataclass
from typing import Optional
@dataclass
class Task: id:int; title:str; deadline:Optional[str]=None; category:str='personal'; priority:int=3; notes:str=''; estimated_minutes:int=30; status:str='pending'; approved:bool=True
@dataclass
class Bill: id:int; name:str; amount:float=0; due_date:Optional[str]=None; recurrence:str='monthly'; approved:bool=True
