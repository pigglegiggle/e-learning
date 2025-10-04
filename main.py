from fastapi import FastAPI, HTTPException, UploadFile, File, Form
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse, JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import Optional, List
import mysql.connector
import hashlib
import os
import shutil
from datetime import datetime

app = FastAPI()

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Create directories
os.makedirs("static", exist_ok=True)
os.makedirs("uploads/materials", exist_ok=True)
os.makedirs("uploads/submissions", exist_ok=True)
os.makedirs("uploads/profiles", exist_ok=True)

# Mount static files
app.mount("/static", StaticFiles(directory="static"), name="static")
app.mount("/uploads", StaticFiles(directory="uploads"), name="uploads")

# Database connection
def get_db():
    return mysql.connector.connect(
        host=os.getenv("DB_HOST", "localhost"),
        user=os.getenv("DB_USER", "root"),
        password=os.getenv("DB_PASSWORD", ""),
        database=os.getenv("DB_NAME", "elearning")
    )

# Pydantic models
class UserRegister(BaseModel):
    email: str
    password: str
    full_name: str
    role: str

class UserLogin(BaseModel):
    email: str
    password: str

class Course(BaseModel):
    title: str
    description: str

class Announcement(BaseModel):
    title: str
    content: str

class Assignment(BaseModel):
    title: str
    description: str
    due_date: Optional[str] = None

class GradeSubmission(BaseModel):
    grade: float
    feedback: Optional[str] = None

# Helper function to hash password
def hash_password(password: str) -> str:
    return hashlib.sha256(password.encode()).hexdigest()

# Root endpoint
@app.get("/")
def read_root():
    return FileResponse("static/index.html")

# Auth endpoints
@app.post("/api/register")
def register(user: UserRegister):
    try:
        db = get_db()
        cursor = db.cursor()
        hashed_pw = hash_password(user.password)

        cursor.execute(
            "INSERT INTO users (email, password, full_name, role) VALUES (%s, %s, %s, %s)",
            (user.email, hashed_pw, user.full_name, user.role)
        )
        db.commit()
        user_id = cursor.lastrowid

        cursor.close()
        db.close()

        return {"success": True, "user_id": user_id, "message": "User registered successfully"}
    except mysql.connector.IntegrityError:
        raise HTTPException(status_code=400, detail="Email already exists")
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/login")
def login(user: UserLogin):
    try:
        db = get_db()
        cursor = db.cursor(dictionary=True)
        hashed_pw = hash_password(user.password)

        cursor.execute(
            "SELECT id, email, full_name, role, profile_picture FROM users WHERE email = %s AND password = %s",
            (user.email, hashed_pw)
        )
        result = cursor.fetchone()

        cursor.close()
        db.close()

        if result:
            return {"success": True, "user": result}
        else:
            raise HTTPException(status_code=401, detail="Invalid credentials")
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

# Profile endpoints
@app.get("/api/profile/{user_id}")
def get_profile(user_id: int):
    try:
        db = get_db()
        cursor = db.cursor(dictionary=True)

        cursor.execute(
            "SELECT id, email, full_name, role, profile_picture FROM users WHERE id = %s",
            (user_id,)
        )
        result = cursor.fetchone()

        cursor.close()
        db.close()

        if result:
            return result
        else:
            raise HTTPException(status_code=404, detail="User not found")
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/profile/{user_id}/update")
async def update_profile(user_id: int, full_name: str = Form(...), file: Optional[UploadFile] = File(None)):
    try:
        db = get_db()
        cursor = db.cursor()

        profile_picture = None
        if file:
            file_extension = os.path.splitext(file.filename)[1]
            filename = f"profile_{user_id}_{datetime.now().timestamp()}{file_extension}"
            file_path = f"uploads/profiles/{filename}"

            with open(file_path, "wb") as buffer:
                shutil.copyfileobj(file.file, buffer)

            profile_picture = f"/{file_path}"
            cursor.execute(
                "UPDATE users SET full_name = %s, profile_picture = %s WHERE id = %s",
                (full_name, profile_picture, user_id)
            )
        else:
            cursor.execute(
                "UPDATE users SET full_name = %s WHERE id = %s",
                (full_name, user_id)
            )

        db.commit()
        cursor.close()
        db.close()

        return {"success": True, "profile_picture": profile_picture, "message": "Profile updated"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

# Course endpoints
@app.get("/api/courses")
def get_all_courses(user_id: Optional[int] = None):
    try:
        db = get_db()
        cursor = db.cursor(dictionary=True)

        if user_id:
            # Get courses with enrollment status
            cursor.execute("""
                SELECT c.*, u.full_name as instructor_name,
                       CASE WHEN e.id IS NOT NULL THEN 1 ELSE 0 END as is_enrolled
                FROM courses c
                JOIN users u ON c.instructor_id = u.id
                LEFT JOIN enrollments e ON c.id = e.course_id AND e.student_id = %s
            """, (user_id,))
        else:
            cursor.execute("""
                SELECT c.*, u.full_name as instructor_name
                FROM courses c
                JOIN users u ON c.instructor_id = u.id
            """)

        courses = cursor.fetchall()

        cursor.close()
        db.close()

        return courses
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/courses/instructor/{instructor_id}")
def get_instructor_courses(instructor_id: int):
    try:
        db = get_db()
        cursor = db.cursor(dictionary=True)

        cursor.execute("SELECT * FROM courses WHERE instructor_id = %s", (instructor_id,))
        courses = cursor.fetchall()

        cursor.close()
        db.close()

        return courses
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/courses/{course_id}")
def get_course(course_id: int, user_id: Optional[int] = None):
    try:
        db = get_db()
        cursor = db.cursor(dictionary=True)

        cursor.execute("""
            SELECT c.*, u.full_name as instructor_name
            FROM courses c
            JOIN users u ON c.instructor_id = u.id
            WHERE c.id = %s
        """, (course_id,))
        course = cursor.fetchone()

        if not course:
            raise HTTPException(status_code=404, detail="Course not found")

        # Check enrollment
        is_enrolled = False
        is_instructor = False
        if user_id:
            cursor.execute(
                "SELECT id FROM enrollments WHERE course_id = %s AND student_id = %s",
                (course_id, user_id)
            )
            is_enrolled = cursor.fetchone() is not None
            is_instructor = course['instructor_id'] == user_id

        course['is_enrolled'] = is_enrolled
        course['is_instructor'] = is_instructor

        cursor.close()
        db.close()

        return course
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/courses")
def create_course(course: Course, instructor_id: int):
    try:
        db = get_db()
        cursor = db.cursor()

        cursor.execute(
            "INSERT INTO courses (title, description, instructor_id) VALUES (%s, %s, %s)",
            (course.title, course.description, instructor_id)
        )
        db.commit()
        course_id = cursor.lastrowid

        cursor.close()
        db.close()

        return {"success": True, "course_id": course_id}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/courses/{course_id}/enroll")
def enroll_course(course_id: int, student_id: int):
    try:
        db = get_db()
        cursor = db.cursor()

        cursor.execute(
            "INSERT INTO enrollments (course_id, student_id) VALUES (%s, %s)",
            (course_id, student_id)
        )
        db.commit()

        cursor.close()
        db.close()

        return {"success": True, "message": "Enrolled successfully"}
    except mysql.connector.IntegrityError:
        raise HTTPException(status_code=400, detail="Already enrolled")
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

# Materials endpoints
@app.get("/api/courses/{course_id}/materials")
def get_materials(course_id: int):
    try:
        db = get_db()
        cursor = db.cursor(dictionary=True)

        cursor.execute("SELECT * FROM materials WHERE course_id = %s ORDER BY uploaded_at DESC", (course_id,))
        materials = cursor.fetchall()

        cursor.close()
        db.close()

        return materials
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/courses/{course_id}/materials")
async def upload_material(course_id: int, title: str = Form(...), file: UploadFile = File(...)):
    try:
        file_extension = os.path.splitext(file.filename)[1].lower()
        file_type = "other"
        if file_extension == ".pdf":
            file_type = "pdf"
        elif file_extension in [".mp4", ".avi", ".mov", ".wmv"]:
            file_type = "video"

        filename = f"material_{course_id}_{datetime.now().timestamp()}_{file.filename}"
        file_path = f"uploads/materials/{filename}"

        with open(file_path, "wb") as buffer:
            shutil.copyfileobj(file.file, buffer)

        db = get_db()
        cursor = db.cursor()

        cursor.execute(
            "INSERT INTO materials (course_id, title, file_path, file_type) VALUES (%s, %s, %s, %s)",
            (course_id, title, f"/{file_path}", file_type)
        )
        db.commit()

        cursor.close()
        db.close()

        return {"success": True, "message": "Material uploaded"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/materials/{material_id}")
def get_material(material_id: int):
    try:
        db = get_db()
        cursor = db.cursor(dictionary=True)

        cursor.execute("SELECT * FROM materials WHERE id = %s", (material_id,))
        material = cursor.fetchone()

        cursor.close()
        db.close()

        if material:
            return material
        else:
            raise HTTPException(status_code=404, detail="Material not found")
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.put("/api/materials/{material_id}")
async def update_material(material_id: int, title: str = Form(...), file: Optional[UploadFile] = File(None)):
    try:
        db = get_db()
        cursor = db.cursor(dictionary=True)

        # Get current material
        cursor.execute("SELECT * FROM materials WHERE id = %s", (material_id,))
        current_material = cursor.fetchone()
        
        if not current_material:
            raise HTTPException(status_code=404, detail="Material not found")

        file_path = current_material['file_path']
        
        if file:
            # Delete old file
            old_file_path = current_material['file_path'].lstrip('/')
            if os.path.exists(old_file_path):
                os.remove(old_file_path)
            
            # Upload new file
            file_extension = os.path.splitext(file.filename)[1].lower()
            file_type = "other"
            if file_extension == ".pdf":
                file_type = "pdf"
            elif file_extension in [".mp4", ".avi", ".mov", ".wmv"]:
                file_type = "video"

            filename = f"material_{current_material['course_id']}_{datetime.now().timestamp()}_{file.filename}"
            file_path = f"uploads/materials/{filename}"

            with open(file_path, "wb") as buffer:
                shutil.copyfileobj(file.file, buffer)

            file_path = f"/{file_path}"

            cursor.execute(
                "UPDATE materials SET title = %s, file_path = %s, file_type = %s WHERE id = %s",
                (title, file_path, file_type, material_id)
            )
        else:
            cursor.execute(
                "UPDATE materials SET title = %s WHERE id = %s",
                (title, material_id)
            )

        db.commit()
        cursor.close()
        db.close()

        return {"success": True, "message": "Material updated"}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.delete("/api/materials/{material_id}")
def delete_material(material_id: int):
    try:
        db = get_db()
        cursor = db.cursor(dictionary=True)

        # Get file path before deleting
        cursor.execute("SELECT file_path FROM materials WHERE id = %s", (material_id,))
        material = cursor.fetchone()

        if material:
            # Delete physical file
            file_path = material['file_path'].lstrip('/')
            if os.path.exists(file_path):
                os.remove(file_path)

            # Delete from database
            cursor.execute("DELETE FROM materials WHERE id = %s", (material_id,))
            db.commit()

        cursor.close()
        db.close()

        return {"success": True, "message": "Material deleted"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

# Announcements endpoints
@app.get("/api/courses/{course_id}/announcements")
def get_announcements(course_id: int):
    try:
        db = get_db()
        cursor = db.cursor(dictionary=True)

        cursor.execute(
            "SELECT * FROM announcements WHERE course_id = %s ORDER BY created_at DESC",
            (course_id,)
        )
        announcements = cursor.fetchall()

        cursor.close()
        db.close()

        return announcements
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/courses/{course_id}/announcements")
def create_announcement(course_id: int, announcement: Announcement):
    try:
        db = get_db()
        cursor = db.cursor()

        cursor.execute(
            "INSERT INTO announcements (course_id, title, content) VALUES (%s, %s, %s)",
            (course_id, announcement.title, announcement.content)
        )
        db.commit()

        cursor.close()
        db.close()

        return {"success": True, "message": "Announcement created"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/announcements/{announcement_id}")
def get_announcement(announcement_id: int):
    try:
        db = get_db()
        cursor = db.cursor(dictionary=True)

        cursor.execute("SELECT * FROM announcements WHERE id = %s", (announcement_id,))
        announcement = cursor.fetchone()

        cursor.close()
        db.close()

        if announcement:
            return announcement
        else:
            raise HTTPException(status_code=404, detail="Announcement not found")
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.put("/api/announcements/{announcement_id}")
def update_announcement(announcement_id: int, announcement: Announcement):
    try:
        db = get_db()
        cursor = db.cursor()

        cursor.execute(
            "UPDATE announcements SET title = %s, content = %s WHERE id = %s",
            (announcement.title, announcement.content, announcement_id)
        )
        db.commit()

        cursor.close()
        db.close()

        return {"success": True, "message": "Announcement updated"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.delete("/api/announcements/{announcement_id}")
def delete_announcement(announcement_id: int):
    try:
        db = get_db()
        cursor = db.cursor()

        cursor.execute("DELETE FROM announcements WHERE id = %s", (announcement_id,))
        db.commit()

        cursor.close()
        db.close()

        return {"success": True, "message": "Announcement deleted"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
        raise HTTPException(status_code=500, detail=str(e))

# Assignments endpoints
@app.get("/api/courses/{course_id}/assignments")
def get_assignments(course_id: int, student_id: Optional[int] = None):
    try:
        db = get_db()
        cursor = db.cursor(dictionary=True)

        if student_id:
            cursor.execute("""
                SELECT a.*, s.id as submission_id, s.grade, s.feedback, s.submitted_at
                FROM assignments a
                LEFT JOIN submissions s ON a.id = s.assignment_id AND s.student_id = %s
                WHERE a.course_id = %s
                ORDER BY a.due_date ASC
            """, (student_id, course_id))
        else:
            cursor.execute(
                "SELECT * FROM assignments WHERE course_id = %s ORDER BY due_date ASC",
                (course_id,)
            )

        assignments = cursor.fetchall()

        cursor.close()
        db.close()

        return assignments
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/assignments/{assignment_id}")
def get_assignment_details(assignment_id: int, student_id: Optional[int] = None):
    try:
        db = get_db()
        cursor = db.cursor(dictionary=True)

        # Get assignment details
        cursor.execute("""
            SELECT a.*, c.title as course_title, u.full_name as instructor_name
            FROM assignments a
            JOIN courses c ON a.course_id = c.id
            JOIN users u ON c.instructor_id = u.id
            WHERE a.id = %s
        """, (assignment_id,))
        assignment = cursor.fetchone()

        if not assignment:
            raise HTTPException(status_code=404, detail="Assignment not found")

        # Get submission status if student_id provided
        if student_id:
            cursor.execute("""
                SELECT * FROM submissions 
                WHERE assignment_id = %s AND student_id = %s
            """, (assignment_id, student_id))
            submission = cursor.fetchone()
            assignment['submission'] = submission

        cursor.close()
        db.close()

        return assignment
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/courses/{course_id}/assignments")
async def create_assignment(course_id: int, title: str = Form(...), description: str = Form(...), 
                           due_date: Optional[str] = Form(None), file: Optional[UploadFile] = File(None)):
    try:
        db = get_db()
        cursor = db.cursor()

        # Validate course exists first
        cursor.execute("SELECT id FROM courses WHERE id = %s", (course_id,))
        course = cursor.fetchone()
        if not course:
            cursor.close()
            db.close()
            raise HTTPException(status_code=404, detail=f"Course with id {course_id} not found")

        file_path = None
        if file:
            filename = f"assignment_{course_id}_{datetime.now().timestamp()}_{file.filename}"
            file_path = f"uploads/materials/{filename}"

            with open(file_path, "wb") as buffer:
                shutil.copyfileobj(file.file, buffer)

            file_path = f"/{file_path}"

        cursor.execute(
            "INSERT INTO assignments (course_id, title, description, due_date, instruction_file) VALUES (%s, %s, %s, %s, %s)",
            (course_id, title, description, due_date, file_path)
        )
        db.commit()
        assignment_id = cursor.lastrowid

        cursor.close()
        db.close()

        return {"success": True, "assignment_id": assignment_id, "message": "Assignment created"}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.put("/api/assignments/{assignment_id}")
async def update_assignment(assignment_id: int, title: str = Form(...), description: str = Form(...), 
                           due_date: Optional[str] = Form(None), file: Optional[UploadFile] = File(None)):
    try:
        db = get_db()
        cursor = db.cursor()

        file_path = None
        if file:
            filename = f"assignment_{assignment_id}_{datetime.now().timestamp()}_{file.filename}"
            file_path = f"uploads/materials/{filename}"

            with open(file_path, "wb") as buffer:
                shutil.copyfileobj(file.file, buffer)

            file_path = f"/{file_path}"

            cursor.execute(
                "UPDATE assignments SET title = %s, description = %s, due_date = %s, instruction_file = %s WHERE id = %s",
                (title, description, due_date, file_path, assignment_id)
            )
        else:
            cursor.execute(
                "UPDATE assignments SET title = %s, description = %s, due_date = %s WHERE id = %s",
                (title, description, due_date, assignment_id)
            )

        db.commit()
        cursor.close()
        db.close()

        return {"success": True, "message": "Assignment updated"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.delete("/api/assignments/{assignment_id}")
def delete_assignment(assignment_id: int):
    try:
        db = get_db()
        cursor = db.cursor()

        # Delete assignment (submissions will be deleted by CASCADE)
        cursor.execute("DELETE FROM assignments WHERE id = %s", (assignment_id,))
        db.commit()

        cursor.close()
        db.close()

        return {"success": True, "message": "Assignment deleted"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

# Submissions endpoints
@app.get("/api/assignments/{assignment_id}/submissions")
def get_submissions(assignment_id: int):
    try:
        db = get_db()
        cursor = db.cursor(dictionary=True)

        cursor.execute("""
            SELECT s.*, u.full_name as student_name, u.email as student_email
            FROM submissions s
            JOIN users u ON s.student_id = u.id
            WHERE s.assignment_id = %s
            ORDER BY s.submitted_at DESC
        """, (assignment_id,))
        submissions = cursor.fetchall()

        cursor.close()
        db.close()

        return submissions
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/assignments/{assignment_id}/submit")
async def submit_assignment(assignment_id: int, student_id: int = Form(...), content: str = Form(""), file: Optional[UploadFile] = File(None)):
    try:
        file_path = None
        if file:
            filename = f"submission_{assignment_id}_{student_id}_{datetime.now().timestamp()}_{file.filename}"
            file_path = f"uploads/submissions/{filename}"

            with open(file_path, "wb") as buffer:
                shutil.copyfileobj(file.file, buffer)

            file_path = f"/{file_path}"

        db = get_db()
        cursor = db.cursor()

        cursor.execute("""
            INSERT INTO submissions (assignment_id, student_id, file_path, content)
            VALUES (%s, %s, %s, %s)
            ON DUPLICATE KEY UPDATE file_path = %s, content = %s, submitted_at = CURRENT_TIMESTAMP
        """, (assignment_id, student_id, file_path, content, file_path, content))
        db.commit()

        cursor.close()
        db.close()

        return {"success": True, "message": "Assignment submitted"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/submissions/{submission_id}/grade")
def grade_submission(submission_id: int, grade_data: GradeSubmission):
    try:
        db = get_db()
        cursor = db.cursor()

        cursor.execute(
            "UPDATE submissions SET grade = %s, feedback = %s, graded_at = CURRENT_TIMESTAMP WHERE id = %s",
            (grade_data.grade, grade_data.feedback, submission_id)
        )
        db.commit()

        cursor.close()
        db.close()

        return {"success": True, "message": "Submission graded"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

# Enrolled courses for student
@app.get("/api/student/{student_id}/courses")
def get_enrolled_courses(student_id: int):
    try:
        db = get_db()
        cursor = db.cursor(dictionary=True)

        cursor.execute("""
            SELECT c.*, u.full_name as instructor_name
            FROM courses c
            JOIN users u ON c.instructor_id = u.id
            JOIN enrollments e ON c.id = e.course_id
            WHERE e.student_id = %s
            ORDER BY e.enrolled_at DESC
        """, (student_id,))
        courses = cursor.fetchall()

        cursor.close()
        db.close()

        return courses
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
