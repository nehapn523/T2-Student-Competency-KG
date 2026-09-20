from fastapi import FastAPI
from neo4j import GraphDatabase
import os
import json

# ============================================================
# FastAPI App
# ============================================================

app = FastAPI(
    title="Student Competency Knowledge Graph API",
    version="0.1.0"
)

# ============================================================
# Neo4j Aura Configuration
# ============================================================

URI = os.getenv("NEO4J_URI")
USERNAME = os.getenv("NEO4J_USERNAME")
PASSWORD = os.getenv("NEO4J_PASSWORD")

driver = GraphDatabase.driver(
    URI,
    auth=(USERNAME, PASSWORD)
)


# ============================================================
# Home / Health Check
# ============================================================

@app.get("/")
def home():
    return {
        "message": "T2 Student Competency API is running"
    }


# ============================================================
# T1 → T2
# Create / Update Student Profile
# ============================================================

@app.post("/student")
def create_student(profile: dict):

    student_id = profile["student_id"]
    name = profile["name"]
    cgpa = profile.get("cgpa")

    with driver.session() as session:

        # ----------------------------------------------------
        # Student
        # ----------------------------------------------------

        session.run(
            """
            MERGE (s:Student {id: $student_id})
            SET s.name = $name,
                s.cgpa = $cgpa
            """,
            student_id=student_id,
            name=name,
            cgpa=cgpa
        )

        # ----------------------------------------------------
        # Skills
        # ----------------------------------------------------

        for skill in profile.get("skills", []):

            session.run(
                """
                MERGE (sk:Skill {name: $skill})

                WITH sk
                MATCH (s:Student {id: $student_id})

                MERGE (s)-[r:DEMONSTRATES]->(sk)

                SET r.confidence_score = $confidence,
                    r.source = $source,
                    r.detail = $detail
                """,
                student_id=student_id,
                skill=skill["skill"],
                confidence=skill.get("confidence"),
                source=skill.get("source"),
                detail=skill.get("detail")
            )

        # ----------------------------------------------------
        # Projects
        # ----------------------------------------------------

        for project in profile.get("projects", []):

            session.run(
                """
                MERGE (p:Project {name: $name})

                SET p.description = $description,
                    p.source = $source

                WITH p
                MATCH (s:Student {id: $student_id})

                MERGE (s)-[:WORKED_ON]->(p)
                """,
                student_id=student_id,
                name=project["name"],
                description=project.get("description"),
                source=project.get("source")
            )

        # ----------------------------------------------------
        # Certifications
        # ----------------------------------------------------

        for cert in profile.get("certifications", []):

            session.run(
                """
                MERGE (c:Certification {name: $name})

                SET c.issuer = $issuer,
                    c.source = $source

                WITH c
                MATCH (s:Student {id: $student_id})

                MERGE (s)-[:EARNED]->(c)
                """,
                student_id=student_id,
                name=cert["name"],
                issuer=cert.get("issuer"),
                source=cert.get("source")
            )

        # ----------------------------------------------------
        # Coding Statistics
        # ----------------------------------------------------

        for stat in profile.get("coding_stats", []):

            metrics_json = json.dumps(
                stat.get("metrics", {})
            )

            session.run(
                """
                MERGE (cp:CodingProfile {
                    platform: $platform,
                    handle: $handle
                })

                SET cp.metrics = $metrics

                WITH cp
                MATCH (s:Student {id: $student_id})

                MERGE (s)-[:HAS_CODING_PROFILE]->(cp)
                """,
                student_id=student_id,
                platform=stat["platform"],
                handle=stat["handle"],
                metrics=metrics_json
            )

    return {
        "message": "Student profile loaded successfully",
        "studentId": student_id
    }


# ============================================================
# Get All Students
# T4 can use this to get available student IDs
# ============================================================

@app.get("/students")
def get_all_students():

    query = """
    MATCH (s:Student)
    RETURN s.id AS studentId,
           s.name AS studentName,
           s.cgpa AS cgpa
    ORDER BY s.id
    """

    try:

        with driver.session() as session:

            result = session.run(query)

            students = []

            for record in result:

                students.append({
                    "studentId": record["studentId"],
                    "studentName": record["studentName"],
                    "cgpa": record["cgpa"]
                })

        return {
            "students": students
        }

    except Exception as e:

        return {
            "error": "Failed to retrieve students",
            "details": str(e)
        }


# ============================================================
# T2 → T4
# Get Individual Student Profile
# ============================================================

@app.get("/student/{student_id}")
def get_student(student_id: str):

    query = """
    MATCH (s:Student {id: $student_id})

    OPTIONAL MATCH (s)-[d:DEMONSTRATES]->(sk:Skill)

    WITH s,
         collect({
             name: sk.name,
             confidence: d.confidence_score,
             source: d.source,
             detail: d.detail
         }) AS skills

    OPTIONAL MATCH (s)-[:WORKED_ON]->(p:Project)

    WITH s,
         skills,
         collect({
             name: p.name,
             description: p.description,
             source: p.source
         }) AS projects

    OPTIONAL MATCH (s)-[:EARNED]->(c:Certification)

    WITH s,
         skills,
         projects,
         collect({
             name: c.name,
             issuer: c.issuer,
             source: c.source
         }) AS certifications

    OPTIONAL MATCH (s)-[:HAS_CODING_PROFILE]->(cp:CodingProfile)

    RETURN s,
           skills,
           projects,
           certifications,
           collect({
               platform: cp.platform,
               handle: cp.handle,
               metrics: cp.metrics
           }) AS coding_stats
    """

    try:

        with driver.session() as session:

            result = session.run(
                query,
                student_id=student_id
            ).single()

    except Exception as e:

        return {
            "error": "Failed to retrieve student",
            "studentId": student_id,
            "details": str(e)
        }

    # --------------------------------------------------------
    # Student Not Found
    # --------------------------------------------------------

    if result is None:

        return {
            "error": "Student not found",
            "studentId": student_id
        }

    # --------------------------------------------------------
    # Convert metrics JSON string back to JSON object
    # --------------------------------------------------------

    coding_stats = []

    for stat in result["coding_stats"]:

        metrics = stat["metrics"]

        if isinstance(metrics, str):

            try:
                metrics = json.loads(metrics)

            except json.JSONDecodeError:
                pass

        coding_stats.append({
            "platform": stat["platform"],
            "handle": stat["handle"],
            "metrics": metrics
        })

    # --------------------------------------------------------
    # Student Information
    # --------------------------------------------------------

    student = result["s"]

    return {
        "studentId": student["id"],
        "studentName": student["name"],
        "cgpa": student.get("cgpa"),
        "skills": result["skills"],
        "projects": result["projects"],
        "certifications": result["certifications"],
        "coding_stats": coding_stats
    }