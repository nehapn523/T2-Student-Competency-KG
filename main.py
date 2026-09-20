from fastapi import FastAPI
from neo4j import GraphDatabase
import os

app = FastAPI(title="Student Competency Knowledge Graph API")

# Neo4j Aura credentials
URI = os.getenv("NEO4J_URI")
USERNAME = os.getenv("NEO4J_USERNAME")
PASSWORD = os.getenv("NEO4J_PASSWORD")

driver = GraphDatabase.driver(
    URI,
    auth=(USERNAME, PASSWORD)
)


@app.get("/")
def home():
    return {
        "message": "T2 Student Competency API is running"
    }


@app.get("/student/{student_id}")
def get_student(student_id: str):

    query = """
    MATCH (s:Student {id: $student_id})

    OPTIONAL MATCH (s)-[d:DEMONSTRATES]->(sk:Skill)
    WITH s,
         collect({
             name: sk.name,
             confidence: d.confidence_score,
             source: d.source
         }) AS skills

    OPTIONAL MATCH (s)-[:WORKED_ON]->(p:Project)
    WITH s, skills,
         collect({
             name: p.name
         }) AS projects

    OPTIONAL MATCH (s)-[:STUDIED]->(c:Course)
    WITH s, skills, projects,
         collect({
             name: c.name
         }) AS courses

    OPTIONAL MATCH (s)-[:EARNED]->(cert:Certification)
    RETURN s,
           skills,
           projects,
           courses,
           collect({
               name: cert.name
           }) AS certifications
    """

    with driver.session() as session:
        result = session.run(
            query,
            student_id=student_id
        ).single()

    if result is None:
        return {
            "error": "Student not found",
            "studentId": student_id
        }

    return {
        "studentId": result["s"]["id"],
        "studentName": result["s"]["name"],
        "skills": result["skills"],
        "projects": result["projects"],
        "courses": result["courses"],
        "certifications": result["certifications"]
    }