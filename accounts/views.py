
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth import authenticate, login
from django.contrib.auth.decorators import login_required
from django.core.exceptions import ObjectDoesNotExist
from django.http import HttpResponseForbidden

from .models import CourseMaterial
from .vector_store import save_chunks, search_chunks
from .question_generator import generate_question_from_text

import pymupdf


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

        try:
            role = user.profile.role
        except ObjectDoesNotExist:
            role = None

        if role != "teacher":
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

    role = getattr(
        getattr(request.user, "profile", None),
        "role",
        None
    )

    if role != "teacher":
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

        try:
            role = user.profile.role
        except ObjectDoesNotExist:
            role = None

        if role != "student":
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

    role = getattr(
        getattr(request.user, "profile", None),
        "role",
        None
    )

    if role != "student":
        return HttpResponseForbidden("Students only.")

    return render(
        request,
        "student_dashboard.html"
    )


# ---------------------------------
# Upload Course Material (PDF)
# ---------------------------------
@login_required
def upload_material(request):

    role = getattr(
        getattr(request.user, "profile", None),
        "role",
        None
    )

    if role != "teacher":
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
                {
                    "error": "Only PDF files are supported."
                }
            )

        if uploaded_file.size > 20 * 1024 * 1024:
            return render(
                request,
                "upload_material.html",
                {
                    "error": "PDF must be 20 MB or smaller."
                }
            )

        if uploaded_file.read(5) != b"%PDF-":
            uploaded_file.seek(0)

            return render(
                request,
                "upload_material.html",
                {
                    "error": "The uploaded file is not a valid PDF."
                }
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
            {
                "message": "Course material uploaded successfully!"
            }
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
# Process PDF and Save Embeddings
# ---------------------------------
@login_required
def process_material(request, material_id):

    role = getattr(
        getattr(request.user, "profile", None),
        "role",
        None
    )

    if role != "teacher":
        return HttpResponseForbidden("Teachers only.")

    material = get_object_or_404(
        CourseMaterial,
        id=material_id,
        teacher=request.user
    )

    extracted_text = ""

    # Step 1: Extract PDF text
    with pymupdf.open(material.file.path) as pdf:
        for page in pdf:
            extracted_text += page.get_text() + "\n"

    # Step 2: Split into chunks
    chunks = split_text_into_chunks(extracted_text)

    # Step 3: Save embeddings in ChromaDB
    saved_count = save_chunks(material, chunks)

    # Step 4: Display results
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


# ---------------------------------
# Semantic Search
# ---------------------------------
@login_required
def semantic_search(request, material_id):

    role = getattr(
        getattr(request.user, "profile", None),
        "role",
        None
    )

    if role != "teacher":
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

    role = getattr(
        getattr(request.user, "profile", None),
        "role",
        None
    )

    if role != "teacher":
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

        # Step 1: Read question counts
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

        # Step 2: Validate question counts
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

        # Step 3: Choose question type for first test
        if mcq_count > 0:
            question_type = "mcq"

        elif tf_count > 0:
            question_type = "true_false"

        else:
            question_type = "essay"

        # Step 4: Read lecture and generate one question
        try:

            lecture_text = ""

            with pymupdf.open(material.file.path) as pdf:

                for page in pdf:
                    lecture_text += page.get_text() + "\n"

            if not lecture_text.strip():

                context["message"] = (
                    "No readable text found in the PDF."
                )

            else:

                generated_question = generate_question_from_text(
                    lecture_text,
                    question_type
                )

                context["generated_question"] = generated_question

                # Step 5: Display correct generation status
                if generated_question.startswith("Generation failed:"):

                    context["message"] = (
                        "Question generation failed. "
                        "Please check the details below."
                    )

                elif (
                    "MCQ options are incomplete." in generated_question
                    or "Could not generate a usable answer." in generated_question
                ):

                    context["message"] = (
                        "A question draft was generated, "
                        "but the MCQ is incomplete. "
                        "Teacher review is required."
                    )

                else:

                    context["message"] = (
                        "A question draft was generated. "
                        "Please review its accuracy "
                        "before using it."
                    )

        except Exception as error:

            context["message"] = (
                f"Question generation failed: {error}"
            )

    return render(
        request,
        "generate_questions.html",
        context
    )
