from typing import Optional, Literal
from pydantic import BaseModel, Field
Category=Literal['study','personal','bill','health','household','work']
class TaskCreate(BaseModel):
    title:Optional[str]=None; text:Optional[str]=None; deadline:Optional[str]=None; category:Category='personal'; priority:int=Field(3,ge=1,le=5); notes:str=''; estimated_minutes:int=Field(30,ge=1); approved:bool=False
class TaskUpdate(BaseModel):
    title:Optional[str]=None; deadline:Optional[str]=None; category:Optional[Category]=None; priority:Optional[int]=Field(None,ge=1,le=5); notes:Optional[str]=None; estimated_minutes:Optional[int]=None; status:Optional[str]=None
class BillCreate(BaseModel): name:str; amount:float=0; due_date:Optional[str]=None; recurrence:str='monthly'; approved:bool=False
class Approval(BaseModel): approved:bool
class PlanRequest(BaseModel): plan_date:Optional[str]=None; exam_date:Optional[str]=None; study_hours:Optional[float]=None; approved:bool=False
DailyPlanRequest=PlanRequest
StudyPlanRequest=PlanRequest
class ReminderCreate(BaseModel): message:str; remind_at:Optional[str]=None; kind:str='general'; approved:bool=False
class PostponeRequest(BaseModel): postponed_to: str
class MemoryUpdate(BaseModel): key:str; value:str
DailyPlanRequest = PlanRequest
StudyPlanRequest = PlanRequest
