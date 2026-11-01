
from django.urls import path
from . import views

urlpatterns = [

    # Teacher Login
    path(
        'teacher-login/',
        views.teacher_login,
        name='teacher_login'
    ),

    # Teacher Dashboard
    path(
        'teacher-dashboard/',
        views.teacher_dashboard,
        name='teacher_dashboard'
    ),

    # Student Login
    path(
        'student-login/',
        views.student_login,
        name='student_login'
    ),

    # Student Dashboard
    path(
        'student-dashboard/',
        views.student_dashboard,
        name='student_dashboard'
    ),

    # Upload PDF
    path(
        'upload-material/',
        views.upload_material,
        name='upload_material'
    ),

    # Process PDF and Store Embeddings
    path(
        'process-material/<int:material_id>/',
        views.process_material,
        name='process_material'
    ),

    # Semantic Search
    path(
        'semantic-search/<int:material_id>/',
        views.semantic_search,
        name='semantic_search'
    ),

    # Generate Questions
    path(
        'generate-questions/<int:material_id>/',
        views.generate_questions,
        name='generate_questions'
    ),

]
