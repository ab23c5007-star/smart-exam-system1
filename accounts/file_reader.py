
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth import authenticate, login
from django.contrib.auth.decorators import login_required
from django.core.exceptions import ObjectDoesNotExist
from django.http import HttpResponseForbidden

from .models import CourseMaterial
from .vector_store import save_chunks, search_chunks
from .question_generator import generate_question_from_text
from .file_reader import read_pdf


# ---------------------------------
# Check User Role
# ---------------------------------
def has_role(user, required_role):
    try:
        return user.profile.role == required_role
    except ObjectDoesNotExist:
        return False


# ---------------------------------
# Teacher Login
# ---------------------------------
def teacher_login(request):

    if request.method == "POST":

        username = request.POST.get("username", "")
        password = request.POST.get("password", "")

        user = authenticate(
            request,
            username=username,
            password=password
        )

        if user is None:
            return render(
                request,
                "teacher_login.html",
                {"error": "Invalid username or password."}
            )

        if not has_role(user, "teacher"):
            return render(
                request,
                "teacher_login.html",
                {"error": "This account is not a teacher account."}
            )

        login(request, user)
        return redirect("teacher_dashboard")

    return render(request, "teacher_login.html")


# ---------------------------------
# Teacher Dashboard
# ---------------------------------
@login_required
def teacher_dashboard(request):

    if not has_role(request.user, "teacher"):
        return HttpResponseForbidden("Teachers only.")

    materials = CourseMaterial.objects.filter(
        teacher=request.user
    ).order_by("-uploaded_at")

    return render(
        request,
        "teacher_dashboard.html",
        {"materials": materials}
    )


# ---------------------------------
# Student Login
# ---------------------------------
def student_login(request):

    if request.method == "POST":

        username = request.POST.get("username", "")
        password = request.POST.get("password", "")

        user = authenticate(
            request,
            username=username,
            password=password
        )

        if user is None:
            return render(
                request,
                "student_login.html",
                {"error": "Invalid username or password."}
            )

        if not has_role(user, "student"):
            return render(
                request,
                "student_login.html",
                {"error": "This account is not a student account."}
            )

        login(request, user)
        return redirect("student_dashboard")

    return render(request, "student_login.html")


# ---------------------------------
# Student Dashboard
# ---------------------------------
@login_required
def student_dashboard(request):

    if not has_role(request.user, "student"):
        return HttpResponseForbidden("Students only.")

    return render(
        request,
        "student_dashboard.html"
    )


# ---------------------------------
# Upload Course Material
# ---------------------------------
@login_required
def upload_material(request):

    if not has_role(request.user, "teacher"):
        return HttpResponseForbidden("Teachers only.")

    if request.method == "POST":

        title = request.POST.get("title", "").strip()
        uploaded_file = request.FILES.get("file")

        if not title or not uploaded_file:
            return render(
                request,
                "upload_material.html",
                {
                    "error": "Please provide a title and a PDF file."
                }
            )

        if not uploaded_file.name.lower().endswith(".pdf"):
            return render(
                request,
                "upload_material.html",
                {"error": "Only PDF files are supported."}
            )

        if uploaded_file.size > 20 * 1024 * 1024:
            return render(
                request,
                "upload_material.html",
                {"error": "PDF must be 20 MB or smaller."}
            )

        if uploaded_file.read(5) != b"%PDF-":
            uploaded_file.seek(0)

            return render(
                request,
                "upload_material.html",
                {"error": "The uploaded file is not a valid PDF."}
            )

        uploaded_file.seek(0)

        CourseMaterial.objects.create(
            teacher=request.user,
            title=title,
            file=uploaded_file
        )

        return render(
            request,
            "upload_material.html",
            {"message": "Course material uploaded successfully!"}
        )

    return render(request, "upload_material.html")


# ---------------------------------
# Split Text into Chunks
# ---------------------------------
def split_text_into_chunks(text, chunk_size=500):

    words = text.split()
    chunks = []

    for i in range(0, len(words), chunk_size):

        chunk = " ".join(
            words[i:i + chunk_size]
        )

        chunks.append(chunk)

    return chunks


# ---------------------------------
# Process PDF
# ---------------------------------
@login_required
def process_material(request, material_id):

    if not has_role(request.user, "teacher"):
        return HttpResponseForbidden("Teachers only.")

    material = get_object_or_404(
        CourseMaterial,
        id=material_id,
        teacher=request.user
    )

    try:

        # Step 1: Read PDF using file_reader.py
        result = read_pdf(material.file.path)

        extracted_text = result["text"]

        # Step 2: Split extracted text
        chunks = split_text_into_chunks(
            extracted_text
        )

        # Step 3: Save embeddings in ChromaDB
        saved_count = save_chunks(
            material,
            chunks
        )

        # Step 4: Show results
        return render(
            request,
            "process_material.html",
            {
                "material": material,
                "extracted_text": extracted_text,
                "chunks": chunks,
                "saved_count": saved_count
            }
        )

    except ValueError as error:

        return render(
            request,
            "process_material.html",
            {
                "material": material,
                "error": str(error),
                "extracted_text": "",
                "chunks": [],
                "saved_count": 0
            }
        )


# ---------------------------------
# Semantic Search
# ---------------------------------
@login_required
def semantic_search(request, material_id):

    if not has_role(request.user, "teacher"):
        return HttpResponseForbidden("Teachers only.")

    material = get_object_or_404(
        CourseMaterial,
        id=material_id,
        teacher=request.user
    )

    question = ""
    results = []

    if request.method == "POST":

        question = request.POST.get(
            "question", ""
        ).strip()

        if question:

            results = search_chunks(
                material,
                question
            )

    return render(
        request,
        "semantic_search.html",
        {
            "material": material,
            "question": question,
            "results": results
        }
    )


# ---------------------------------
# Generate Questions Using AI
# ---------------------------------
@login_required
def generate_questions(request, material_id):

    if not has_role(request.user, "teacher"):
        return HttpResponseForbidden("Teachers only.")

    material = get_object_or_404(
        CourseMaterial,
        id=material_id,
        teacher=request.user
    )

    context = {
        "material": material,
        "message": "",
        "generated_question": ""
    }

    if request.method == "POST":

        # Step 1: Read requested counts
        try:

            mcq_count = int(
                request.POST.get("mcq_count", "0")
            )

            tf_count = int(
                request.POST.get("tf_count", "0")
            )

            essay_count = int(
                request.POST.get("essay_count", "0")
            )

        except (ValueError, TypeError):

            context["message"] = (
                "Please enter valid question numbers."
            )

            return render(
                request,
                "generate_questions.html",
                context
            )

        counts = [
            mcq_count,
            tf_count,
            essay_count
        ]

        if any(count < 0 or count > 20 for count in counts):

            context["message"] = (
                "Each question count must be between 0 and 20."
            )

            return render(
                request,
                "generate_questions.html",
                context
            )

        if sum(counts) == 0:

            context["message"] = (
                "Please select at least one question."
            )

            return render(
                request,
                "generate_questions.html",
                context
            )

        # Step 2: Read PDF using file_reader.py
        try:

            result = read_pdf(
                material.file.path
            )

            lecture_text = result["text"]

            # Step 3: Generate selected types
            generated_sections = []

            question_requests = [
                ("mcq", mcq_count),
                ("true_false", tf_count),
                ("essay", essay_count)
            ]

            for question_type, count in question_requests:

                if count == 0:
                    continue

                generated = generate_question_from_text(
                    lecture_text,
                    question_type,
                    count
                )

                section = (
                    f"TYPE: {question_type.upper()}\n"
                    f"{generated}"
                )

                generated_sections.append(section)

            generated_question = "\n\n".join(
                generated_sections
            )

            context["generated_question"] = generated_question

            # Step 4: Show accurate status
            failed = "Generation failed:" in generated_question

            incomplete = (
                "MCQ options are incomplete." in generated_question
                or "PARTIAL RESULT" in generated_question
            )

            if failed:

                context["message"] = (
                    "Some question generation failed. "
                    "Please review the details below."
                )

            elif incomplete:

                context["message"] = (
                    "Some question drafts are incomplete. "
                    "Teacher review is required."
                )

            else:

                context["message"] = (
                    "Question drafts generated. "
                    "Please verify all answers before use."
                )

        except ValueError as error:

            context["message"] = str(error)

        except Exception as error:

            context["message"] = (
                f"Question generation failed: {error}"
            )

    return render(
        request,
        "generate_questions.html",
        context
    )
