from django.urls import path
from . import views

urlpatterns = [
    # Auth
    path('', views.home_view, name='home'),
    path('login/', views.login_view, name='login'),
    path('logout/', views.logout_view, name='logout'),
    path('change-password/', views.change_password_view, name='change_password'),
    path('account/profile/', views.edit_profile_view, name='edit_profile'),
    path('account/settings/', views.account_settings_view, name='account_settings'),

    # Public
    path('schedule/', views.public_schedule, name='public_schedule'),
    path('schedule/export/', views.public_schedule_export, name='public_schedule_export'),

    # ─── System Manager ───
    path('admin-dashboard/', views.system_manager_dashboard, name='system_manager_dashboard'),

    # Universities
    path('universities/', views.university_list, name='university_list'),
    path('universities/add/', views.university_add, name='university_add'),
    path('universities/<int:pk>/edit/', views.university_edit, name='university_edit'),
    path('universities/<int:pk>/delete/', views.university_delete, name='university_delete'),

    # Branches
    path('branches/', views.branch_list, name='branch_list'),
    path('branches/add/', views.branch_add, name='branch_add'),
    path('branches/<int:pk>/edit/', views.branch_edit, name='branch_edit'),
    path('branches/<int:pk>/delete/', views.branch_delete, name='branch_delete'),

    # Colleges
    path('colleges/', views.college_list, name='college_list'),
    path('colleges/add/', views.college_add, name='college_add'),
    path('colleges/<int:pk>/edit/', views.college_edit, name='college_edit'),
    path('colleges/<int:pk>/delete/', views.college_delete, name='college_delete'),

    # Rooms (admin)
    path('admin/rooms/', views.room_list_admin, name='room_list_admin'),
    path('admin/rooms/add/', views.room_add_admin, name='room_add_admin'),
    path('admin/rooms/<int:pk>/edit/', views.room_edit_admin, name='room_edit_admin'),
    path('admin/rooms/<int:pk>/delete/', views.room_delete_admin, name='room_delete_admin'),

    # Halls (admin)
    path('admin/halls/', views.hall_list_admin, name='hall_list_admin'),
    path('admin/halls/add/', views.hall_add_admin, name='hall_add_admin'),
    path('admin/halls/<int:pk>/edit/', views.hall_edit_admin, name='hall_edit_admin'),
    path('admin/halls/<int:pk>/delete/', views.hall_delete_admin, name='hall_delete_admin'),

    # Users (admin)
    path('admin/users/', views.user_list_admin, name='user_list_admin'),
    path('admin/users/add-manager/', views.college_manager_add, name='college_manager_add'),
    path('admin/users/<int:pk>/delete/', views.user_delete_admin, name='user_delete_admin'),

    # All Schedules (admin)
    path('admin/all-schedules/', views.all_schedules_admin, name='all_schedules_admin'),

    # ─── College Manager ───
    path('cm/dashboard/', views.college_manager_dashboard, name='college_manager_dashboard'),

    # Departments
    path('cm/departments/', views.cm_department_list, name='cm_department_list'),
    path('cm/departments/add/', views.cm_department_add, name='cm_department_add'),
    path('cm/departments/assign/', views.cm_department_assign, name='cm_department_assign'),
    path('cm/departments/<int:pk>/edit/', views.cm_department_edit, name='cm_department_edit'),
    path('cm/departments/<int:pk>/delete/', views.cm_department_delete, name='cm_department_delete'),

    # Academic Periods
    path('cm/academic-periods/', views.cm_academic_periods, name='cm_academic_periods'),
    path('cm/academic-periods/dept/<int:dept_id>/', views.cm_academic_period_setup, name='cm_academic_period_setup'),
    path('cm/academic-periods/<int:pk>/delete/', views.cm_period_delete, name='cm_period_delete'),

    # Courses
    path('cm/courses/', views.cm_course_list, name='cm_course_list'),
    path('cm/courses/add/', views.cm_course_add, name='cm_course_add'),
    path('cm/courses/<int:pk>/edit/', views.cm_course_edit, name='cm_course_edit'),
    path('cm/courses/<int:pk>/delete/', views.cm_course_delete, name='cm_course_delete'),

    # Specializations
    path('cm/specializations/', views.cm_specialization_list, name='cm_specialization_list'),
    path('cm/specializations/add/', views.cm_specialization_add, name='cm_specialization_add'),
    path('cm/specializations/<int:pk>/delete/', views.cm_specialization_delete, name='cm_specialization_delete'),

    # Instructors
    path('cm/instructors/', views.cm_instructor_list, name='cm_instructor_list'),
    path('cm/instructors/add/', views.cm_instructor_add, name='cm_instructor_add'),
    path('cm/instructors/<int:pk>/edit/', views.cm_instructor_edit, name='cm_instructor_edit'),
    path('cm/instructors/<int:pk>/delete/', views.cm_instructor_delete, name='cm_instructor_delete'),

    # Rooms (CM)
    path('cm/rooms/', views.cm_room_list, name='cm_room_list'),
    path('cm/rooms/add/', views.cm_room_add, name='cm_room_add'),
    path('cm/rooms/assign/', views.cm_room_assign, name='cm_room_assign'),
    path('cm/rooms/<int:pk>/edit/', views.cm_room_edit, name='cm_room_edit'),
    path('cm/rooms/<int:pk>/remove/', views.cm_room_remove, name='cm_room_remove'),

    # Halls (CM)
    path('cm/halls/', views.cm_hall_list, name='cm_hall_list'),
    path('cm/halls/add/', views.cm_hall_add, name='cm_hall_add'),
    path('cm/halls/assign/', views.cm_hall_assign, name='cm_hall_assign'),
    path('cm/halls/<int:pk>/edit/', views.cm_hall_edit, name='cm_hall_edit'),
    path('cm/halls/<int:pk>/remove/', views.cm_hall_remove, name='cm_hall_remove'),

    # Students
    path('cm/students/', views.cm_student_list, name='cm_student_list'),
    path('cm/students/add/', views.cm_student_add, name='cm_student_add'),
    path('cm/students/<int:pk>/delete/', views.cm_student_delete, name='cm_student_delete'),

    # Student Settings
    path('cm/student-settings/<int:period_id>/', views.cm_student_settings, name='cm_student_settings'),

    # Lecture Schedule
    path('cm/schedule/lectures/', views.cm_lecture_schedule, name='cm_lecture_schedule'),
    path('cm/schedule/lectures/add/', views.cm_lecture_add, name='cm_lecture_add'),
    path('cm/schedule/lectures/<int:pk>/edit/', views.cm_lecture_edit, name='cm_lecture_edit'),
    path('cm/schedule/lectures/<int:pk>/delete/', views.cm_lecture_delete, name='cm_lecture_delete'),

    # Lab Schedule
    path('cm/schedule/labs/', views.cm_lab_schedule, name='cm_lab_schedule'),
    path('cm/schedule/labs/add/', views.cm_lab_add, name='cm_lab_add'),
    path('cm/schedule/labs/<int:pk>/edit/', views.cm_lab_edit, name='cm_lab_edit'),
    path('cm/schedule/labs/<int:pk>/delete/', views.cm_lab_delete, name='cm_lab_delete'),

    # Change Requests
    path('cm/requests/', views.cm_requests_list, name='cm_requests_list'),
    path('cm/requests/<int:pk>/approve/', views.cm_request_approve, name='cm_request_approve'),
    path('cm/requests/<int:pk>/reject/', views.cm_request_reject, name='cm_request_reject'),

    # Reports
    path('cm/reports/professor/', views.cm_report_professor_schedule, name='cm_report_professor'),
    path('cm/reports/room/', views.cm_report_room_schedule, name='cm_report_room'),

    # Deadline
    path('cm/deadline/', views.cm_deadline_settings, name='cm_deadline_settings'),

    # Notifications (CM)
    path('cm/notifications/', views.cm_notifications, name='cm_notifications'),

    # ─── NEW FEATURES ───

    # Analytics Dashboard
    path('analytics/', views.analytics_dashboard, name='analytics_dashboard'),

    # Change Log
    path('changelog/', views.changelog_list, name='changelog_list'),
    path('changelog/<int:log_id>/restore/', views.schedule_restore, name='schedule_restore'),

    # Export / Import
    path('export-import/', views.export_import_page, name='export_import_page'),
    path('export/lectures/csv/', views.export_lectures_csv, name='export_lectures_csv'),
    path('export/labs/csv/', views.export_labs_csv, name='export_labs_csv'),
    path('export/lectures/excel/', views.export_lectures_excel, name='export_lectures_excel'),
    path('export/schedule/pdf/', views.export_schedule_pdf, name='export_schedule_pdf'),
    path('import/template/', views.import_schedule_template, name='import_schedule_template'),
    path('import/csv/', views.import_schedule_csv, name='import_schedule_csv'),

    # Notifications Center
    path('notifications/', views.notifications_center, name='notifications_center'),
    path('notifications/mark-read/', views.notifications_mark_read, name='notifications_mark_read'),

    # ─── Professor ───
    path('professor/schedule/', views.professor_schedule, name='professor_schedule'),
    path('professor/requests/', views.professor_requests, name='professor_requests'),
    path('professor/requests/add/', views.professor_request_add, name='professor_request_add'),
    path('professor/requests/<int:pk>/delete/', views.professor_request_delete, name='professor_request_delete'),
    path('professor/taught/<int:schedule_id>/', views.professor_taught_lecture, name='professor_taught_lecture'),
    path('professor/notifications/', views.professor_notifications, name='professor_notifications'),

    # ─── Student ───
    path('student/schedule/', views.student_schedule, name='student_schedule'),

    # ─── Dept Head Management (College Manager only) ───
    path('cm/dept-heads/', views.cm_dept_head_list, name='cm_dept_head_list'),
    path('cm/dept-heads/add/', views.cm_dept_head_add, name='cm_dept_head_add'),
    path('cm/dept-heads/<int:pk>/delete/', views.cm_dept_head_delete, name='cm_dept_head_delete'),

    # ─── API ───
    path('api/check-conflicts/', views.api_check_conflicts, name='api_check_conflicts'),
    path('api/check-conflicts-advanced/', views.api_check_conflicts_advanced, name='api_check_conflicts_advanced'),
    path('api/check-lab-conflicts/', views.api_check_lab_conflicts_advanced, name='api_check_lab_conflicts_advanced'),
    path('api/periods/', views.api_get_periods, name='api_get_periods'),
    path('api/courses/', views.api_get_courses, name='api_get_courses'),
    path('api/rooms/', views.api_get_rooms, name='api_get_rooms'),
    path('api/halls/', views.api_get_halls, name='api_get_halls'),
    path('api/unread-count/', views.api_unread_count, name='api_unread_count'),

    # ─── Public APIs (no login required) ───
    path('api/public/departments/', views.api_public_departments, name='api_public_departments'),
    path('api/public/periods/', views.api_public_periods, name='api_public_periods'),
    path('api/public/schedule/', views.api_public_schedule_data, name='api_public_schedule_data'),
    path('cm/schedule/lectures/bulk-delete/', views.cm_lecture_bulk_delete, name='cm_lecture_bulk_delete'),
    path('cm/schedule/labs/bulk-delete/', views.cm_lab_bulk_delete, name='cm_lab_bulk_delete'),
    path('cm/schedule/lectures/<int:pk>/quick-edit/', views.cm_lecture_inline_edit, name='cm_lecture_inline_edit'),
    path('cm/schedule/labs/<int:pk>/quick-edit/', views.cm_lab_inline_edit, name='cm_lab_inline_edit'),
]
