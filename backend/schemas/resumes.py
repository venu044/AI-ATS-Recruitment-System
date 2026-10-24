from typing import List
from pydantic import BaseModel, Field

class Education(BaseModel):
    degree: str = ""
    institution: str = ""
    field: str = ""
    year: str = ""

class Experience(BaseModel):
    role: str = ""
    organization: str = ""
    duration: str = ""
    description: str = ""

class ResumeProfile(BaseModel):
    name: str = ""
    email: str = ""
    phone: str = ""
    education: List[Education] = Field(default_factory=list)
    skills: List[str] = Field(default_factory=list)
    experience: List[Experience] = Field(default_factory=list)
    research_interests: List[str] = Field(default_factory=list)
    publications: List[str] = Field(default_factory=list)
    certifications: List[str] = Field(default_factory=list)
