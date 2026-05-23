from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.http import JsonResponse, HttpResponse
from django.db.models import Q, Count
from django.db import IntegrityError, transaction
from django.views.decorators.http import require_POST
from django.core.paginator import Paginator
import json
import bcrypt
from datetime import datetime, date

from .models import (
    UnifiedUser, University, Branch, College, Department, CollegeDepartment,
    AcademicYear, DepartmentAcademicPeriod, DepartmentStudentSettings,
    Specialization, Course, Room, Hall, CollegeRoom, CollegeHall,
    Professor, ProfessorCollegeRelation, ExternalCollaborator, Student,
    Role, LectureSchedule, LabSchedule, AlternativeTime, TaughtLecture,
    Notification, Semester, ScheduleDeadline, EmailSettings, EmailTemplate,
    ScheduleChangeLog,
)
from .views_extras import (
    log_schedule_change, serialize_lecture, serialize_lab,
    analytics_dashboard, changelog_list, schedule_restore,
    export_import_page, export_lectures_csv, export_labs_csv,
    export_lectures_excel, export_schedule_pdf,
    import_schedule_template, import_schedule_csv,
    notifications_mark_read, api_unread_count, api_check_conflicts_advanced,
    api_check_lab_conflicts_advanced, public_schedule_export,
)
from .views_analytics import build_analytics_data
from .forms import (
    LoginForm, UniversityForm, BranchForm, CollegeForm, DepartmentForm,
    AcademicYearForm, DepartmentAcademicPeriodForm, DepartmentStudentSettingsForm,
    SpecializationForm, CourseForm, RoomForm, HallForm, ProfessorForm,
    StudentForm, CollegeManagerForm, LectureScheduleForm, LabScheduleForm,
    AlternativeTimeForm, ChangePasswordForm, ScheduleDeadlineForm, EmailSettingsForm
)

DAY_ORDER = ['Saturday', 'Sunday', 'Monday', 'Tuesday', 'Wednesday', 'Thursday']
DAY_NAMES = {
    'Saturday': 'السبت', 'Sunday': 'الأحد', 'Monday': 'الاثنين',
    'Tuesday': 'الثلاثاء', 'Wednesday': 'الأربعاء', 'Thursday': 'الخميس',
}


def _notify_students_schedule_change(schedule, action):
    """Send notifications to students affected by a schedule change."""
    try:
        action_msgs = {
            'add': f'تمت إضافة محاضرة جديدة: {schedule.course.course_name} - {DAY_NAMES.get(schedule.day_of_week, schedule.day_of_week)} {str(schedule.start_time)[:5]}',
            'edit': f'تم تعديل موعد محاضرة: {schedule.course.course_name} - {DAY_NAMES.get(schedule.day_of_week, schedule.day_of_week)} {str(schedule.start_time)[:5]}',
            'delete': f'تم حذف محاضرة: {schedule.course.course_name}',
        }
        subject_msgs = {
            'add': 'محاضرة جديدة في جدولك',
            'edit': 'تحديث في جدول المحاضرات',
            'delete': 'حذف محاضرة من الجدول',
        }
        msg = action_msgs.get(action, f'تغيير في الجدول: {schedule.course.course_name}')
        subject = subject_msgs.get(action, 'تحديث في الجدول الدراسي')

        # Notify students in the same period/department
        affected_students = UnifiedUser.objects.filter(
            user_type='student',
            department=schedule.department,
        )
        notifs = [
            Notification(
                recipient=student,
                recipient_type='student',
                subject=subject,
                message=msg,
                status='sent',
            )
            for student in affected_students
        ]
        if notifs:
            Notification.objects.bulk_create(notifs, ignore_conflicts=True)

        # Notify the professor
        try:
            prof_user = UnifiedUser.objects.get(user_type='professor', user_id=schedule.professor_id)
            Notification.objects.create(
                recipient=prof_user,
                recipient_type='professor',
                subject=subject,
                message=msg,
                status='sent',
            )
        except UnifiedUser.DoesNotExist:
            pass
    except Exception:
        pass


# ─────────────────────────────────────────────
# Auth Views
# ─────────────────────────────────────────────

def login_view(request):
    if request.user.is_authenticated:
        return redirect('home')
    if request.method == 'POST':
        form = LoginForm(request.POST)
        if form.is_valid():
            username = form.cleaned_data['username']
            password = form.cleaned_data['password']
            user = authenticate(request, username=username, password=password)
            if user:
                login(request, user)
                return redirect('home')
            else:
                messages.error(request, 'اسم المستخدم أو كلمة المرور غير صحيحة')
    else:
        form = LoginForm()
    return render(request, 'login.html', {'form': form})


def logout_view(request):
    logout(request)
    return redirect('login')


@login_required
def home_view(request):
    user = request.user
    if user.user_type == 'system_manager':
        return redirect('system_manager_dashboard')
    elif user.user_type == 'college_manager':
        return redirect('college_manager_dashboard')
    elif user.user_type == 'department_head':
        return redirect('college_manager_dashboard')
    elif user.user_type == 'professor':
        return redirect('professor_schedule')
    elif user.user_type == 'student':
        return redirect('student_schedule')
    return redirect('login')


# ─────────────────────────────────────────────
# Decorators / Helpers
# ─────────────────────────────────────────────

def require_system_manager(view_func):
    def wrapper(request, *args, **kwargs):
        if not request.user.is_authenticated or request.user.user_type != 'system_manager':
            messages.error(request, 'ليس لديك صلاحية للوصول لهذه الصفحة')
            return redirect('login')
        return view_func(request, *args, **kwargs)
    wrapper.__name__ = view_func.__name__
    return wrapper


def require_college_manager(view_func):
    """Allow college_manager AND department_head (scoped by get_accessible_dept_ids)."""
    def wrapper(request, *args, **kwargs):
        if not request.user.is_authenticated or request.user.user_type not in ('college_manager', 'department_head'):
            messages.error(request, 'ليس لديك صلاحية للوصول لهذه الصفحة')
            return redirect('login')
        return view_func(request, *args, **kwargs)
    wrapper.__name__ = view_func.__name__
    return wrapper


def require_college_manager_only(view_func):
    """Strictly allow college_manager only (not department_head)."""
    def wrapper(request, *args, **kwargs):
        if not request.user.is_authenticated or request.user.user_type != 'college_manager':
            messages.error(request, 'ليس لديك صلاحية للوصول لهذه الصفحة')
            return redirect('login')
        return view_func(request, *args, **kwargs)
    wrapper.__name__ = view_func.__name__
    return wrapper


def require_professor(view_func):
    def wrapper(request, *args, **kwargs):
        if not request.user.is_authenticated or request.user.user_type != 'professor':
            messages.error(request, 'ليس لديك صلاحية للوصول لهذه الصفحة')
            return redirect('login')
        return view_func(request, *args, **kwargs)
    wrapper.__name__ = view_func.__name__
    return wrapper


def require_department_head(view_func):
    """Allow ONLY department_head — not college_manager."""
    def wrapper(request, *args, **kwargs):
        if not request.user.is_authenticated or request.user.user_type != 'department_head':
            messages.error(request, 'ليس لديك صلاحية للوصول لهذه الصفحة — هذه الوظيفة مخصصة لرئيس القسم')
            return redirect('login')
        return view_func(request, *args, **kwargs)
    wrapper.__name__ = view_func.__name__
    return wrapper


def require_student(view_func):
    def wrapper(request, *args, **kwargs):
        if not request.user.is_authenticated or request.user.user_type != 'student':
            messages.error(request, 'ليس لديك صلاحية للوصول لهذه الصفحة')
            return redirect('login')
        return view_func(request, *args, **kwargs)
    wrapper.__name__ = view_func.__name__
    return wrapper


def get_college_for_manager(user):
    """Return the college for a college_manager or department_head."""
    if user.user_type == 'department_head':
        return user.college
    try:
        role = Role.objects.get(id=user.user_id, role='مدير_كلية')
        return role.college
    except Role.DoesNotExist:
        return user.college


def get_accessible_dept_ids(user):
    """Return a list of department IDs accessible to this user.

    - department_head → only their own department
    - college_manager → all departments in their college
    - system_manager  → all departments (returns None to skip filtering)
    """
    if user.user_type == 'department_head':
        return [user.department_id] if user.department_id else []
    college = get_college_for_manager(user)
    if college:
        return list(CollegeDepartment.objects.filter(college=college).values_list('department_id', flat=True))
    return list(Department.objects.values_list('id', flat=True))


def check_lecture_conflicts(department_id, professor_id, room_id, day, start_time, end_time, exclude_id=None):
    conflicts = []
    qs = LectureSchedule.objects.filter(
        day_of_week=day,
        start_time__lt=end_time,
        end_time__gt=start_time
    )
    if exclude_id:
        qs = qs.exclude(id=exclude_id)

    # Room conflict
    room_conflict = qs.filter(room_id=room_id).select_related('course', 'department').first()
    if room_conflict:
        conflicts.append({
            'type': 'room',
            'message': f'تعارض في القاعة: مع مادة {room_conflict.course.course_name} - قسم {room_conflict.department.name}'
        })

    # Professor conflict
    prof_conflict = qs.filter(professor_id=professor_id).select_related('course', 'department').first()
    if prof_conflict:
        conflicts.append({
            'type': 'professor',
            'message': f'تعارض للأستاذ: مع مادة {prof_conflict.course.course_name} - قسم {prof_conflict.department.name}'
        })

    # Student/department conflict
    dept_conflict = qs.filter(department_id=department_id).select_related('course').first()
    if dept_conflict:
        conflicts.append({
            'type': 'department',
            'message': f'تعارض للطلاب: مع مادة {dept_conflict.course.course_name}'
        })

    return conflicts


def check_lab_conflicts(department_id, professor_id, hall_id, day, start_time, end_time, exclude_id=None):
    """Server-side conflict check for lab scheduling."""
    conflicts = []
    qs = LabSchedule.objects.filter(
        day_of_week=day,
        start_time__lt=end_time,
        end_time__gt=start_time
    )
    if exclude_id:
        qs = qs.exclude(id=exclude_id)

    # Hall conflict
    hall_conflict = qs.filter(hall_id=hall_id).select_related('course', 'department').first()
    if hall_conflict:
        conflicts.append({
            'type': 'hall',
            'message': f'تعارض في المعمل: مع مادة {hall_conflict.course.course_name} - قسم {hall_conflict.department.name}'
        })

    # Professor conflict (check both lectures and labs)
    prof_lab_conflict = qs.filter(professor_id=professor_id).select_related('course', 'department').first()
    if prof_lab_conflict:
        conflicts.append({
            'type': 'professor',
            'message': f'تعارض للأستاذ في المعامل: مع مادة {prof_lab_conflict.course.course_name} - قسم {prof_lab_conflict.department.name}'
        })

    # Professor in lecture schedule at same time
    lec_qs = LectureSchedule.objects.filter(
        day_of_week=day, start_time__lt=end_time, end_time__gt=start_time,
        professor_id=professor_id
    )
    prof_lec_conflict = lec_qs.select_related('course', 'department').first()
    if prof_lec_conflict:
        conflicts.append({
            'type': 'professor',
            'message': f'تعارض للأستاذ مع محاضرة: {prof_lec_conflict.course.course_name} - قسم {prof_lec_conflict.department.name}'
        })

    # Student/department conflict
    dept_conflict = qs.filter(department_id=department_id).select_related('course').first()
    if dept_conflict:
        conflicts.append({
            'type': 'department',
            'message': f'تعارض لمجموعة الطلاب: مع مادة {dept_conflict.course.course_name}'
        })

    return conflicts


# ─────────────────────────────────────────────
# System Manager Views
# ─────────────────────────────────────────────

@require_system_manager
def system_manager_dashboard(request):
    from django.db.models import Case, When, IntegerField, Sum
    from django.db import connection

    with connection.cursor() as cursor:
        cursor.execute("""
            SELECT
                (SELECT COUNT(*) FROM universities) AS universities,
                (SELECT COUNT(*) FROM branches) AS branches,
                (SELECT COUNT(*) FROM colleges) AS colleges,
                (SELECT COUNT(*) FROM departments) AS departments,
                (SELECT COUNT(*) FROM users WHERE TRUE) AS professors,
                (SELECT COUNT(*) FROM students) AS students,
                (SELECT COUNT(*) FROM rooms) AS rooms,
                (SELECT COUNT(*) FROM halls) AS halls,
                (SELECT COUNT(*) FROM lecture_schedule) AS lecture_schedules,
                (SELECT COUNT(*) FROM lab_schedule) AS lab_schedules,
                (SELECT COUNT(*) FROM roles WHERE role = 'مدير_كلية') AS college_managers,
                (SELECT COUNT(*) FROM alternative_times WHERE status = 'pending') AS pending_requests
        """)
        row = cursor.fetchone()

    stats = {
        'universities': row[0],
        'branches': row[1],
        'colleges': row[2],
        'departments': row[3],
        'professors': row[4],
        'students': row[5],
        'rooms': row[6],
        'halls': row[7],
        'lecture_schedules': row[8],
        'lab_schedules': row[9],
        'college_managers': row[10],
        'pending_requests': row[11],
    }
    recent_schedules = LectureSchedule.objects.select_related('course', 'department', 'professor').order_by('-created_at')[:5]
    recent_changelog = ScheduleChangeLog.objects.select_related('changed_by').order_by('-changed_at')[:10]
    return render(request, 'timetable/system_manager_dashboard.html', {
        'stats': stats,
        'recent_schedules': recent_schedules,
        'recent_changelog': recent_changelog,
    })


# Universities
@require_system_manager
def university_list(request):
    universities = University.objects.annotate(branch_count=Count('branches')).order_by('name')
    return render(request, 'timetable/universities.html', {'universities': universities})


@require_system_manager
def university_add(request):
    if request.method == 'POST':
        form = UniversityForm(request.POST)
        if form.is_valid():
            form.save()
            messages.success(request, 'تم إضافة الجامعة بنجاح')
            return redirect('university_list')
    else:
        form = UniversityForm()
    return render(request, 'timetable/form.html', {'form': form, 'title': 'إضافة جامعة', 'back_url': 'university_list'})


@require_system_manager
def university_edit(request, pk):
    university = get_object_or_404(University, pk=pk)
    if request.method == 'POST':
        form = UniversityForm(request.POST, instance=university)
        if form.is_valid():
            form.save()
            messages.success(request, 'تم تعديل الجامعة بنجاح')
            return redirect('university_list')
    else:
        form = UniversityForm(instance=university)
    return render(request, 'timetable/form.html', {'form': form, 'title': 'تعديل الجامعة', 'back_url': 'university_list'})


@require_system_manager
def university_delete(request, pk):
    university = get_object_or_404(University, pk=pk)
    if request.method == 'POST':
        university.delete()
        messages.success(request, 'تم حذف الجامعة بنجاح')
        return redirect('university_list')
    return render(request, 'timetable/confirm_delete.html', {'object': university, 'title': 'حذف الجامعة', 'back_url': 'university_list'})


# Branches
@require_system_manager
def branch_list(request):
    university_id = request.GET.get('university_id')
    branches = Branch.objects.select_related('university').order_by('university__name', 'name')
    if university_id:
        branches = branches.filter(university_id=university_id)
    universities = University.objects.all()
    return render(request, 'timetable/branches.html', {
        'branches': branches, 'universities': universities, 'selected_university': university_id
    })


@require_system_manager
def branch_add(request):
    if request.method == 'POST':
        form = BranchForm(request.POST)
        if form.is_valid():
            form.save()
            messages.success(request, 'تم إضافة الفرع بنجاح')
            return redirect('branch_list')
    else:
        form = BranchForm()
    return render(request, 'timetable/form.html', {'form': form, 'title': 'إضافة فرع', 'back_url': 'branch_list'})


@require_system_manager
def branch_edit(request, pk):
    branch = get_object_or_404(Branch, pk=pk)
    if request.method == 'POST':
        form = BranchForm(request.POST, instance=branch)
        if form.is_valid():
            form.save()
            messages.success(request, 'تم تعديل الفرع بنجاح')
            return redirect('branch_list')
    else:
        form = BranchForm(instance=branch)
    return render(request, 'timetable/form.html', {'form': form, 'title': 'تعديل الفرع', 'back_url': 'branch_list'})


@require_system_manager
def branch_delete(request, pk):
    branch = get_object_or_404(Branch, pk=pk)
    if request.method == 'POST':
        branch.delete()
        messages.success(request, 'تم حذف الفرع بنجاح')
        return redirect('branch_list')
    return render(request, 'timetable/confirm_delete.html', {'object': branch, 'title': 'حذف الفرع', 'back_url': 'branch_list'})


# Colleges
@require_system_manager
def college_list(request):
    colleges = College.objects.select_related('branch', 'branch__university').order_by('name')
    return render(request, 'timetable/colleges.html', {'colleges': colleges})


@require_system_manager
def college_add(request):
    if request.method == 'POST':
        form = CollegeForm(request.POST)
        if form.is_valid():
            form.save()
            messages.success(request, 'تم إضافة الكلية بنجاح')
            return redirect('college_list')
    else:
        form = CollegeForm()
    return render(request, 'timetable/form.html', {'form': form, 'title': 'إضافة كلية', 'back_url': 'college_list'})


@require_system_manager
def college_edit(request, pk):
    college = get_object_or_404(College, pk=pk)
    if request.method == 'POST':
        form = CollegeForm(request.POST, instance=college)
        if form.is_valid():
            form.save()
            messages.success(request, 'تم تعديل الكلية بنجاح')
            return redirect('college_list')
    else:
        form = CollegeForm(instance=college)
    return render(request, 'timetable/form.html', {'form': form, 'title': 'تعديل الكلية', 'back_url': 'college_list'})


@require_system_manager
def college_delete(request, pk):
    college = get_object_or_404(College, pk=pk)
    if request.method == 'POST':
        college.delete()
        messages.success(request, 'تم حذف الكلية بنجاح')
        return redirect('college_list')
    return render(request, 'timetable/confirm_delete.html', {'object': college, 'title': 'حذف الكلية', 'back_url': 'college_list'})


# Rooms (System Manager)
@require_system_manager
def room_list_admin(request):
    rooms = Room.objects.select_related('college').order_by('college__name', 'name')
    return render(request, 'timetable/rooms_admin.html', {'rooms': rooms})


@require_system_manager
def room_add_admin(request):
    if request.method == 'POST':
        form = RoomForm(request.POST)
        if form.is_valid():
            room = form.save()
            CollegeRoom.objects.get_or_create(college=room.college, room=room, defaults={'relation_type': 'owner'})
            messages.success(request, 'تم إضافة القاعة بنجاح')
            return redirect('room_list_admin')
    else:
        form = RoomForm()
    return render(request, 'timetable/form.html', {'form': form, 'title': 'إضافة قاعة', 'back_url': 'room_list_admin'})


@require_system_manager
def room_edit_admin(request, pk):
    room = get_object_or_404(Room, pk=pk)
    if request.method == 'POST':
        form = RoomForm(request.POST, instance=room)
        if form.is_valid():
            form.save()
            messages.success(request, 'تم تعديل القاعة بنجاح')
            return redirect('room_list_admin')
    else:
        form = RoomForm(instance=room)
    return render(request, 'timetable/form.html', {'form': form, 'title': 'تعديل القاعة', 'back_url': 'room_list_admin'})


@require_system_manager
def room_delete_admin(request, pk):
    room = get_object_or_404(Room, pk=pk)
    if request.method == 'POST':
        room.delete()
        messages.success(request, 'تم حذف القاعة بنجاح')
        return redirect('room_list_admin')
    return render(request, 'timetable/confirm_delete.html', {'object': room, 'title': 'حذف القاعة', 'back_url': 'room_list_admin'})


# Halls (System Manager)
@require_system_manager
def hall_list_admin(request):
    halls = Hall.objects.select_related('college').order_by('college__name', 'name')
    return render(request, 'timetable/halls_admin.html', {'halls': halls})


@require_system_manager
def hall_add_admin(request):
    if request.method == 'POST':
        form = HallForm(request.POST)
        if form.is_valid():
            hall = form.save()
            CollegeHall.objects.get_or_create(college=hall.college, hall=hall, defaults={'relation_type': 'owner'})
            messages.success(request, 'تم إضافة المعمل بنجاح')
            return redirect('hall_list_admin')
    else:
        form = HallForm()
    return render(request, 'timetable/form.html', {'form': form, 'title': 'إضافة معمل', 'back_url': 'hall_list_admin'})


@require_system_manager
def hall_edit_admin(request, pk):
    hall = get_object_or_404(Hall, pk=pk)
    if request.method == 'POST':
        form = HallForm(request.POST, instance=hall)
        if form.is_valid():
            form.save()
            messages.success(request, 'تم تعديل المعمل بنجاح')
            return redirect('hall_list_admin')
    else:
        form = HallForm(instance=hall)
    return render(request, 'timetable/form.html', {'form': form, 'title': 'تعديل المعمل', 'back_url': 'hall_list_admin'})


@require_system_manager
def hall_delete_admin(request, pk):
    hall = get_object_or_404(Hall, pk=pk)
    if request.method == 'POST':
        hall.delete()
        messages.success(request, 'تم حذف المعمل بنجاح')
        return redirect('hall_list_admin')
    return render(request, 'timetable/confirm_delete.html', {'object': hall, 'title': 'حذف المعمل', 'back_url': 'hall_list_admin'})


# System Manager - User Management
@require_system_manager
def user_list_admin(request):
    user_type = request.GET.get('type', '')
    users = UnifiedUser.objects.select_related('college', 'department').order_by('user_type', 'full_name')
    if user_type:
        users = users.filter(user_type=user_type)
    return render(request, 'timetable/users_admin.html', {'users': users, 'selected_type': user_type})


@require_system_manager
def college_manager_add(request):
    if request.method == 'POST':
        form = CollegeManagerForm(request.POST)
        if form.is_valid():
            try:
                with transaction.atomic():
                    role = form.save()
                    password = form.cleaned_data.get('password_plain', 'password123')
                    hashed = bcrypt.hashpw(password.encode('utf-8'), bcrypt.gensalt()).decode('utf-8')
                    UnifiedUser.objects.create(
                        user_type='college_manager',
                        user_id=role.id,
                        username=role.username,
                        full_name=role.full_name,
                        email=role.email or '',
                        college=role.college,
                        password=hashed,
                        is_active=True,
                    )
                messages.success(request, 'تم إضافة مدير الكلية بنجاح')
                return redirect('user_list_admin')
            except IntegrityError:
                form.add_error('username', 'اسم المستخدم هذا مستخدم بالفعل. الرجاء اختيار اسم آخر.')
    else:
        form = CollegeManagerForm()
    return render(request, 'timetable/form.html', {'form': form, 'title': 'إضافة مدير كلية', 'back_url': 'user_list_admin'})


@require_system_manager
def user_delete_admin(request, pk):
    user = get_object_or_404(UnifiedUser, pk=pk)
    if request.method == 'POST':
        user.delete()
        messages.success(request, 'تم حذف المستخدم بنجاح')
        return redirect('user_list_admin')
    return render(request, 'timetable/confirm_delete.html', {'object': user, 'title': 'حذف المستخدم', 'back_url': 'user_list_admin'})


# System Manager - All Schedules Report
@require_system_manager
def all_schedules_admin(request):
    college_id = request.GET.get('college_id')
    department_id = request.GET.get('department_id')

    lectures = LectureSchedule.objects.select_related(
        'course', 'department', 'professor', 'room', 'period', 'period__year'
    ).order_by('department__name', 'day_of_week', 'start_time')

    labs = LabSchedule.objects.select_related(
        'course', 'department', 'professor', 'hall', 'period', 'period__year'
    ).order_by('department__name', 'day_of_week', 'start_time')

    if college_id:
        lectures = lectures.filter(department__collegedepartment__college_id=college_id)
        labs = labs.filter(department__collegedepartment__college_id=college_id)

    if department_id:
        lectures = lectures.filter(department_id=department_id)
        labs = labs.filter(department_id=department_id)

    colleges = College.objects.all()
    departments = Department.objects.all()
    return render(request, 'timetable/all_schedules_admin.html', {
        'lectures': lectures, 'labs': labs,
        'colleges': colleges, 'departments': departments,
        'selected_college': college_id, 'selected_department': department_id,
        'day_order': DAY_ORDER, 'day_names': DAY_NAMES,
    })


# ─────────────────────────────────────────────
# College Manager Views
# ─────────────────────────────────────────────

@require_college_manager
def college_manager_dashboard(request):
    college = get_college_for_manager(request.user)
    if not college:
        messages.error(request, 'لم يتم تحديد الكلية')
        return redirect('login')

    dept_ids = get_accessible_dept_ids(request.user)
    is_dept_head = request.user.user_type == 'department_head'

    if is_dept_head:
        stats = {
            'departments': len(dept_ids),
            'professors': Professor.objects.filter(
                Q(college=college) | Q(college_relations__college=college)
            ).distinct().count(),
            'rooms': CollegeRoom.objects.filter(college=college, is_active=True).count(),
            'halls': CollegeHall.objects.filter(college=college, is_active=True).count(),
            'lecture_schedules': LectureSchedule.objects.filter(department_id__in=dept_ids).count(),
            'lab_schedules': LabSchedule.objects.filter(department_id__in=dept_ids).count(),
            'pending_requests': AlternativeTime.objects.filter(
                schedule__department_id__in=dept_ids, status='pending'
            ).count(),
        }
        recent_lectures = LectureSchedule.objects.filter(
            department_id__in=dept_ids
        ).select_related('course', 'department', 'professor').order_by('-created_at')[:5]
        pending_requests = AlternativeTime.objects.filter(
            schedule__department_id__in=dept_ids, status='pending'
        ).select_related('professor').order_by('-created_at')[:5]
    else:
        # College manager: show org structure stats only
        from timetable.models import CollegeDepartment
        dept_head_count = UnifiedUser.objects.filter(
            user_type='department_head', college=college
        ).count()
        stats = {
            'departments': CollegeDepartment.objects.filter(college=college).count(),
            'dept_heads': dept_head_count,
            'professors': Professor.objects.filter(
                Q(college=college) | Q(college_relations__college=college)
            ).distinct().count(),
            'rooms': CollegeRoom.objects.filter(college=college, is_active=True).count(),
            'halls': CollegeHall.objects.filter(college=college, is_active=True).count(),
            'lecture_schedules': LectureSchedule.objects.filter(department_id__in=dept_ids).count(),
            'lab_schedules': LabSchedule.objects.filter(department_id__in=dept_ids).count(),
            'pending_requests': 0,
        }
        recent_lectures = LectureSchedule.objects.filter(
            department_id__in=dept_ids
        ).select_related('course', 'department', 'professor').order_by('-created_at')[:5]
        pending_requests = []

    deadline = ScheduleDeadline.objects.order_by('-created_at').first()
    recent_changelog = ScheduleChangeLog.objects.select_related('changed_by').order_by('-changed_at')[:10]

    return render(request, 'timetable/college_manager_dashboard.html', {
        'college': college,
        'stats': stats,
        'recent_lectures': recent_lectures,
        'pending_requests': pending_requests,
        'deadline': deadline,
        'recent_changelog': recent_changelog,
        'day_names': DAY_NAMES,
        'is_dept_head': is_dept_head,
    })


# College Manager - Departments (CM-only: dept heads cannot manage departments)
@require_college_manager_only
def cm_department_list(request):
    college = get_college_for_manager(request.user)
    college_depts = CollegeDepartment.objects.filter(college=college).select_related('department')
    all_depts = Department.objects.exclude(
        id__in=[cd.department_id for cd in college_depts]
    )
    return render(request, 'timetable/cm_departments.html', {
        'college': college, 'college_depts': college_depts, 'all_depts': all_depts
    })


@require_college_manager_only
def cm_department_add(request):
    college = get_college_for_manager(request.user)
    if request.method == 'POST':
        form = DepartmentForm(request.POST)
        if form.is_valid():
            dept = form.save()
            CollegeDepartment.objects.create(college=college, department=dept)
            messages.success(request, 'تم إضافة القسم بنجاح')
            return redirect('cm_department_list')
    else:
        form = DepartmentForm()
    return render(request, 'timetable/form.html', {'form': form, 'title': 'إضافة قسم جديد', 'back_url': 'cm_department_list'})


@require_college_manager_only
def cm_department_assign(request):
    college = get_college_for_manager(request.user)
    if request.method == 'POST':
        dept_id = request.POST.get('department_id')
        if dept_id:
            dept = get_object_or_404(Department, pk=dept_id)
            CollegeDepartment.objects.get_or_create(college=college, department=dept)
            messages.success(request, f'تم إضافة القسم {dept.name} للكلية')
        return redirect('cm_department_list')
    return redirect('cm_department_list')


@require_college_manager_only
def cm_department_edit(request, pk):
    college_depts = get_accessible_dept_ids(request.user)
    dept = get_object_or_404(Department, pk=pk, id__in=college_depts)
    if request.method == 'POST':
        form = DepartmentForm(request.POST, instance=dept)
        if form.is_valid():
            form.save()
            messages.success(request, 'تم تعديل القسم بنجاح')
            return redirect('cm_department_list')
    else:
        form = DepartmentForm(instance=dept)
    return render(request, 'timetable/form.html', {'form': form, 'title': 'تعديل القسم', 'back_url': 'cm_department_list'})


@require_college_manager_only
def cm_department_delete(request, pk):
    college = get_college_for_manager(request.user)
    college_depts = get_accessible_dept_ids(request.user)
    dept = get_object_or_404(Department, pk=pk, id__in=college_depts)
    if request.method == 'POST':
        CollegeDepartment.objects.filter(college=college, department_id=pk).delete()
        messages.success(request, 'تم إزالة القسم من الكلية')
        return redirect('cm_department_list')
    return render(request, 'timetable/confirm_delete.html', {'object': dept, 'title': 'إزالة القسم', 'back_url': 'cm_department_list'})


# College Manager - Academic Periods
@require_department_head
def cm_academic_periods(request):
    college = get_college_for_manager(request.user)
    college_depts = get_accessible_dept_ids(request.user)
    periods = DepartmentAcademicPeriod.objects.filter(
        department_id__in=college_depts
    ).select_related('department', 'year').order_by('department__name', 'year__year_number', 'semester_type')
    return render(request, 'timetable/cm_academic_periods.html', {
        'college': college, 'periods': periods
    })


@require_department_head
def cm_academic_period_setup(request, dept_id):
    college = get_college_for_manager(request.user)
    college_depts = get_accessible_dept_ids(request.user)
    dept = get_object_or_404(Department, pk=dept_id, id__in=college_depts)
    years = AcademicYear.objects.all().order_by('year_number')
    existing_periods = DepartmentAcademicPeriod.objects.filter(department=dept).select_related('year')

    if request.method == 'POST':
        year_id = request.POST.get('year_id')
        semester_type = request.POST.get('semester_type')
        if year_id and semester_type:
            year = get_object_or_404(AcademicYear, pk=year_id)
            period, created = DepartmentAcademicPeriod.objects.get_or_create(
                department=dept, year=year, semester_type=semester_type
            )
            if created:
                messages.success(request, f'تم إضافة الفترة الأكاديمية بنجاح: {year.year_name} - فصل {semester_type}')
            else:
                messages.info(request, 'هذه الفترة موجودة بالفعل')
        return redirect('cm_academic_period_setup', dept_id=dept_id)

    completion_stats = {}
    for period in existing_periods:
        course_count = Course.objects.filter(period=period).count()
        lec_count = LectureSchedule.objects.filter(period=period).count()
        pct = min(100, int(lec_count * 100 / course_count)) if course_count > 0 else 0
        completion_stats[period.pk] = {'courses': course_count, 'lectures': lec_count, 'pct': pct}

    return render(request, 'timetable/cm_academic_period_setup.html', {
        'college': college, 'dept': dept, 'years': years,
        'dept_periods': existing_periods,
        'completion_stats': completion_stats,
    })


@require_department_head
def cm_period_delete(request, pk):
    period = get_object_or_404(DepartmentAcademicPeriod, pk=pk)
    if request.method == 'POST':
        period.delete()
        messages.success(request, 'تم حذف الفترة الأكاديمية')
        return redirect('cm_academic_periods')
    return render(request, 'timetable/confirm_delete.html', {'object': period, 'title': 'حذف الفترة الأكاديمية', 'back_url': 'cm_academic_periods'})


# College Manager - Courses
@require_department_head
def cm_course_list(request):
    college = get_college_for_manager(request.user)
    college_depts = get_accessible_dept_ids(request.user)
    dept_id = request.GET.get('dept_id')
    period_id = request.GET.get('period_id')

    courses = Course.objects.select_related('period', 'period__department', 'period__year', 'specialization')
    courses = courses.filter(period__department_id__in=college_depts)

    if dept_id:
        courses = courses.filter(period__department_id=dept_id)
    if period_id:
        courses = courses.filter(period_id=period_id)

    departments = Department.objects.filter(id__in=college_depts)
    return render(request, 'timetable/cm_courses.html', {
        'college': college, 'courses': courses, 'departments': departments,
        'selected_dept': dept_id, 'selected_period': period_id,
    })


@require_department_head
def cm_course_add(request):
    college = get_college_for_manager(request.user)
    college_depts = get_accessible_dept_ids(request.user)
    if request.method == 'POST':
        form = CourseForm(request.POST)
        if form.is_valid():
            form.save()
            messages.success(request, 'تم إضافة المادة بنجاح')
            return redirect('cm_course_list')
    else:
        form = CourseForm()
        form.fields['period'].queryset = DepartmentAcademicPeriod.objects.filter(
            department_id__in=college_depts
        ).select_related('department', 'year')
    return render(request, 'timetable/form.html', {'form': form, 'title': 'إضافة مادة', 'back_url': 'cm_course_list'})


@require_department_head
def cm_course_edit(request, pk):
    college = get_college_for_manager(request.user)
    college_depts = get_accessible_dept_ids(request.user)
    course = get_object_or_404(Course, pk=pk, period__department_id__in=college_depts)
    if request.method == 'POST':
        form = CourseForm(request.POST, instance=course)
        if form.is_valid():
            form.save()
            messages.success(request, 'تم تعديل المادة بنجاح')
            return redirect('cm_course_list')
    else:
        form = CourseForm(instance=course)
        form.fields['period'].queryset = DepartmentAcademicPeriod.objects.filter(
            department_id__in=college_depts
        ).select_related('department', 'year')
    return render(request, 'timetable/form.html', {'form': form, 'title': 'تعديل المادة', 'back_url': 'cm_course_list'})


@require_department_head
def cm_course_delete(request, pk):
    college_depts = get_accessible_dept_ids(request.user)
    course = get_object_or_404(Course, pk=pk, period__department_id__in=college_depts)
    if request.method == 'POST':
        course.delete()
        messages.success(request, 'تم حذف المادة بنجاح')
        return redirect('cm_course_list')
    return render(request, 'timetable/confirm_delete.html', {'object': course, 'title': 'حذف المادة', 'back_url': 'cm_course_list'})


# College Manager - Specializations
@require_department_head
def cm_specialization_list(request):
    college = get_college_for_manager(request.user)
    college_depts = get_accessible_dept_ids(request.user)
    specializations = Specialization.objects.filter(
        department_id__in=college_depts
    ).select_related('department', 'period', 'period__year')
    return render(request, 'timetable/cm_specializations.html', {
        'college': college, 'specializations': specializations
    })


@require_department_head
def cm_specialization_add(request):
    college = get_college_for_manager(request.user)
    college_depts = get_accessible_dept_ids(request.user)
    if request.method == 'POST':
        form = SpecializationForm(request.POST)
        if form.is_valid():
            form.save()
            messages.success(request, 'تم إضافة التخصص بنجاح')
            return redirect('cm_specialization_list')
    else:
        form = SpecializationForm()
        form.fields['department'].queryset = Department.objects.filter(id__in=college_depts)
        form.fields['period'].queryset = DepartmentAcademicPeriod.objects.filter(
            department_id__in=college_depts
        ).select_related('department', 'year')
    return render(request, 'timetable/form.html', {'form': form, 'title': 'إضافة تخصص', 'back_url': 'cm_specialization_list'})


@require_department_head
def cm_specialization_delete(request, pk):
    college_depts = get_accessible_dept_ids(request.user)
    spec = get_object_or_404(Specialization, pk=pk, department_id__in=college_depts)
    if request.method == 'POST':
        spec.delete()
        messages.success(request, 'تم حذف التخصص')
        return redirect('cm_specialization_list')
    return render(request, 'timetable/confirm_delete.html', {'object': spec, 'title': 'حذف التخصص', 'back_url': 'cm_specialization_list'})


# College Manager - Instructors
@require_department_head
def cm_instructor_list(request):
    college = get_college_for_manager(request.user)
    professors = Professor.objects.filter(
        Q(college=college) | Q(college_relations__college=college)
    ).distinct().order_by('name')
    return render(request, 'timetable/cm_instructors.html', {
        'college': college, 'professors': professors
    })


@require_department_head
def cm_instructor_add(request):
    college = get_college_for_manager(request.user)
    if request.method == 'POST':
        form = ProfessorForm(request.POST)
        if form.is_valid():
            try:
                with transaction.atomic():
                    professor = form.save(commit=False)
                    password = form.cleaned_data.get('password_plain') or 'password123'
                    hashed = bcrypt.hashpw(password.encode('utf-8'), bcrypt.gensalt()).decode('utf-8')
                    professor.password = hashed
                    professor.college = college
                    professor.save()
                    UnifiedUser.objects.create(
                        user_type='professor',
                        user_id=professor.id,
                        username=professor.username,
                        full_name=professor.name,
                        email=professor.email,
                        college=college,
                        password=hashed,
                        is_active=True,
                    )
                    ProfessorCollegeRelation.objects.create(
                        professor=professor, college=college, relation_type='primary'
                    )
                messages.success(request, 'تم إضافة الأستاذ بنجاح')
                return redirect('cm_instructor_list')
            except IntegrityError:
                form.add_error('username', 'اسم المستخدم هذا مستخدم بالفعل. الرجاء اختيار اسم آخر.')
    else:
        form = ProfessorForm(initial={'college': college})
    return render(request, 'timetable/form.html', {'form': form, 'title': 'إضافة أستاذ', 'back_url': 'cm_instructor_list'})


@require_department_head
def cm_instructor_edit(request, pk):
    college = get_college_for_manager(request.user)
    professor = get_object_or_404(Professor, pk=pk, college_relations__college=college)
    if request.method == 'POST':
        form = ProfessorForm(request.POST, instance=professor)
        if form.is_valid():
            form.save()
            # Update unified user
            UnifiedUser.objects.filter(user_type='professor', user_id=professor.id).update(
                username=professor.username,
                full_name=professor.name,
                email=professor.email,
            )
            messages.success(request, 'تم تعديل بيانات الأستاذ بنجاح')
            return redirect('cm_instructor_list')
    else:
        form = ProfessorForm(instance=professor)
    return render(request, 'timetable/form.html', {'form': form, 'title': 'تعديل الأستاذ', 'back_url': 'cm_instructor_list'})


@require_department_head
def cm_instructor_delete(request, pk):
    college = get_college_for_manager(request.user)
    professor = get_object_or_404(Professor, pk=pk, college_relations__college=college)
    if request.method == 'POST':
        UnifiedUser.objects.filter(user_type='professor', user_id=pk).delete()
        professor.delete()
        messages.success(request, 'تم حذف الأستاذ بنجاح')
        return redirect('cm_instructor_list')
    return render(request, 'timetable/confirm_delete.html', {'object': professor, 'title': 'حذف الأستاذ', 'back_url': 'cm_instructor_list'})


# College Manager - Rooms
@require_department_head
def cm_room_list(request):
    college = get_college_for_manager(request.user)
    college_rooms = CollegeRoom.objects.filter(college=college, is_active=True).select_related('room', 'room__college')
    available_rooms = Room.objects.exclude(
        id__in=CollegeRoom.objects.filter(college=college, is_active=True).values_list('room_id', flat=True)
    ).select_related('college')
    return render(request, 'timetable/cm_rooms.html', {
        'college': college, 'college_rooms': college_rooms, 'available_rooms': available_rooms
    })


@require_department_head
def cm_room_add(request):
    college = get_college_for_manager(request.user)
    if request.method == 'POST':
        form = RoomForm(request.POST)
        if form.is_valid():
            room = form.save(commit=False)
            room.college = college
            room.save()
            CollegeRoom.objects.create(college=college, room=room, relation_type='owner')
            messages.success(request, 'تم إضافة القاعة بنجاح')
            return redirect('cm_room_list')
    else:
        form = RoomForm(initial={'college': college})
        form.fields['college'].initial = college
    return render(request, 'timetable/form.html', {'form': form, 'title': 'إضافة قاعة', 'back_url': 'cm_room_list'})


@require_department_head
def cm_room_assign(request):
    college = get_college_for_manager(request.user)
    if request.method == 'POST':
        room_id = request.POST.get('room_id')
        if room_id:
            room = get_object_or_404(Room, pk=room_id)
            relation_type = 'owner' if room.college == college else 'shared'
            CollegeRoom.objects.update_or_create(
                college=college, room=room,
                defaults={'is_active': True, 'relation_type': relation_type}
            )
            messages.success(request, 'تم إضافة القاعة للكلية')
        return redirect('cm_room_list')
    return redirect('cm_room_list')


@require_department_head
def cm_room_remove(request, pk):
    college = get_college_for_manager(request.user)
    room = get_object_or_404(Room, pk=pk, collegeroom__college=college, collegeroom__is_active=True)
    if request.method == 'POST':
        CollegeRoom.objects.filter(college=college, room_id=pk).update(is_active=False)
        messages.success(request, 'تم إزالة القاعة')
        return redirect('cm_room_list')
    return render(request, 'timetable/confirm_delete.html', {'object': room, 'title': 'إزالة القاعة', 'back_url': 'cm_room_list'})


@require_department_head
def cm_room_edit(request, pk):
    college = get_college_for_manager(request.user)
    room = get_object_or_404(Room, pk=pk, collegeroom__college=college, collegeroom__is_active=True)
    if request.method == 'POST':
        form = RoomForm(request.POST, instance=room)
        if form.is_valid():
            form.save()
            messages.success(request, 'تم تعديل القاعة بنجاح')
            return redirect('cm_room_list')
    else:
        form = RoomForm(instance=room)
    return render(request, 'timetable/form.html', {'form': form, 'title': 'تعديل القاعة', 'back_url': 'cm_room_list'})


# College Manager - Halls
@require_department_head
def cm_hall_list(request):
    college = get_college_for_manager(request.user)
    college_halls = CollegeHall.objects.filter(college=college, is_active=True).select_related('hall', 'hall__college')
    available_halls = Hall.objects.exclude(
        id__in=CollegeHall.objects.filter(college=college, is_active=True).values_list('hall_id', flat=True)
    ).select_related('college')
    return render(request, 'timetable/cm_halls.html', {
        'college': college, 'college_halls': college_halls, 'available_halls': available_halls
    })


@require_department_head
def cm_hall_add(request):
    college = get_college_for_manager(request.user)
    if request.method == 'POST':
        form = HallForm(request.POST)
        if form.is_valid():
            hall = form.save(commit=False)
            hall.college = college
            hall.save()
            CollegeHall.objects.create(college=college, hall=hall, relation_type='owner')
            messages.success(request, 'تم إضافة المعمل بنجاح')
            return redirect('cm_hall_list')
    else:
        form = HallForm(initial={'college': college})
    return render(request, 'timetable/form.html', {'form': form, 'title': 'إضافة معمل', 'back_url': 'cm_hall_list'})


@require_department_head
def cm_hall_assign(request):
    college = get_college_for_manager(request.user)
    if request.method == 'POST':
        hall_id = request.POST.get('hall_id')
        if hall_id:
            hall = get_object_or_404(Hall, pk=hall_id)
            relation_type = 'owner' if hall.college == college else 'shared'
            CollegeHall.objects.update_or_create(
                college=college, hall=hall,
                defaults={'is_active': True, 'relation_type': relation_type}
            )
            messages.success(request, 'تم إضافة المعمل للكلية')
        return redirect('cm_hall_list')
    return redirect('cm_hall_list')


@require_department_head
def cm_hall_remove(request, pk):
    college = get_college_for_manager(request.user)
    hall = get_object_or_404(Hall, pk=pk, collegehall__college=college, collegehall__is_active=True)
    if request.method == 'POST':
        CollegeHall.objects.filter(college=college, hall_id=pk).update(is_active=False)
        messages.success(request, 'تم إزالة المعمل')
        return redirect('cm_hall_list')
    return render(request, 'timetable/confirm_delete.html', {'object': hall, 'title': 'إزالة المعمل', 'back_url': 'cm_hall_list'})


@require_department_head
def cm_hall_edit(request, pk):
    college = get_college_for_manager(request.user)
    hall = get_object_or_404(Hall, pk=pk, collegehall__college=college, collegehall__is_active=True)
    if request.method == 'POST':
        form = HallForm(request.POST, instance=hall)
        if form.is_valid():
            form.save()
            messages.success(request, 'تم تعديل المعمل بنجاح')
            return redirect('cm_hall_list')
    else:
        form = HallForm(instance=hall)
    return render(request, 'timetable/form.html', {'form': form, 'title': 'تعديل المعمل', 'back_url': 'cm_hall_list'})


# College Manager - Student Settings
@require_department_head
def cm_student_settings(request, period_id):
    college_depts = get_accessible_dept_ids(request.user)
    period = get_object_or_404(DepartmentAcademicPeriod, pk=period_id, department_id__in=college_depts)
    settings_obj, created = DepartmentStudentSettings.objects.get_or_create(
        period=period, department=period.department,
        defaults={'student_count': 0, 'groups_count': 1}
    )
    if request.method == 'POST':
        form = DepartmentStudentSettingsForm(request.POST, instance=settings_obj)
        if form.is_valid():
            form.save()
            messages.success(request, 'تم حفظ إعدادات الطلاب بنجاح')
            return redirect('cm_academic_periods')
    else:
        form = DepartmentStudentSettingsForm(instance=settings_obj)
    return render(request, 'timetable/form.html', {
        'form': form,
        'title': f'إعدادات الطلاب - {period.department.name} - {period.year.year_name}',
        'back_url': 'cm_academic_periods'
    })


# College Manager - Lecture Schedule
@require_department_head
def cm_lecture_schedule(request):
    college = get_college_for_manager(request.user)
    college_depts = get_accessible_dept_ids(request.user)
    dept_id = request.GET.get('dept_id')
    period_id = request.GET.get('period_id')

    schedules = LectureSchedule.objects.filter(
        department_id__in=college_depts
    ).select_related('course', 'department', 'professor', 'room', 'period', 'period__year')

    if dept_id:
        schedules = schedules.filter(department_id=dept_id)
    if period_id:
        schedules = schedules.filter(period_id=period_id)

    # Organize by day
    sched_list = list(schedules)
    schedule_by_day = {day: [] for day in DAY_ORDER}
    for s in sched_list:
        schedule_by_day[s.day_of_week].append(s)

    # Detect conflicts (same prof or same room at overlapping time)
    conflict_ids = set()
    for i, s1 in enumerate(sched_list):
        for s2 in sched_list[i+1:]:
            if s1.day_of_week != s2.day_of_week:
                continue
            if s1.start_time < s2.end_time and s1.end_time > s2.start_time:
                if s1.professor_id == s2.professor_id or s1.room_id == s2.room_id:
                    conflict_ids.add(s1.pk)
                    conflict_ids.add(s2.pk)

    departments = Department.objects.filter(id__in=college_depts)
    periods = DepartmentAcademicPeriod.objects.filter(
        department_id__in=college_depts
    ).select_related('department', 'year')

    return render(request, 'timetable/cm_lecture_schedule.html', {
        'college': college,
        'schedules': sched_list,
        'schedule_by_day': schedule_by_day,
        'departments': departments,
        'periods': periods,
        'selected_dept': dept_id,
        'selected_period': period_id,
        'day_order': DAY_ORDER,
        'day_names': DAY_NAMES,
        'conflict_ids': conflict_ids,
    })


@require_department_head
def cm_lecture_add(request):
    college = get_college_for_manager(request.user)
    college_depts = get_accessible_dept_ids(request.user)

    if request.method == 'POST':
        form = LectureScheduleForm(request.POST)
        # Restrict querysets
        form.fields['department'].queryset = Department.objects.filter(id__in=college_depts)
        form.fields['period'].queryset = DepartmentAcademicPeriod.objects.filter(department_id__in=college_depts)
        form.fields['course'].queryset = Course.objects.filter(period__department_id__in=college_depts)
        form.fields['professor'].queryset = Professor.objects.filter(
            Q(college=college) | Q(college_relations__college=college)
        ).distinct()
        form.fields['room'].queryset = Room.objects.filter(
            collegeroom__college=college, collegeroom__is_active=True
        )

        if form.is_valid():
            # Check conflicts
            data = form.cleaned_data
            conflicts = check_lecture_conflicts(
                data['department'].id, data['professor'].id, data['room'].id,
                data['day_of_week'], data['start_time'], data['end_time']
            )
            if conflicts:
                for c in conflicts:
                    messages.warning(request, c['message'])
            else:
                lecture = form.save()
                log_schedule_change('add', lecture, request.user, new_data=serialize_lecture(lecture))
                # Notify students and send alerts
                _notify_students_schedule_change(lecture, 'add')
                messages.success(request, 'تم إضافة المحاضرة بنجاح')
                return redirect('cm_lecture_schedule')
    else:
        form = LectureScheduleForm()
        dept_id = request.GET.get('dept_id')
        period_id = request.GET.get('period_id')
        form.fields['department'].queryset = Department.objects.filter(id__in=college_depts)
        form.fields['period'].queryset = DepartmentAcademicPeriod.objects.filter(department_id__in=college_depts)
        form.fields['course'].queryset = Course.objects.filter(period__department_id__in=college_depts)
        form.fields['professor'].queryset = Professor.objects.filter(
            Q(college=college) | Q(college_relations__college=college)
        ).distinct()
        form.fields['room'].queryset = Room.objects.filter(
            collegeroom__college=college, collegeroom__is_active=True
        )
        if dept_id:
            form.fields['department'].initial = dept_id
        if period_id:
            form.fields['period'].initial = period_id

    return render(request, 'timetable/cm_lecture_add.html', {
        'form': form, 'college': college, 'title': 'إضافة محاضرة', 'back_url': 'cm_lecture_schedule'
    })


@require_department_head
def cm_lecture_edit(request, pk):
    college = get_college_for_manager(request.user)
    college_depts = get_accessible_dept_ids(request.user)
    schedule = get_object_or_404(LectureSchedule, pk=pk, department_id__in=college_depts)

    if request.method == 'POST':
        form = LectureScheduleForm(request.POST, instance=schedule)
        form.fields['department'].queryset = Department.objects.filter(id__in=college_depts)
        form.fields['period'].queryset = DepartmentAcademicPeriod.objects.filter(department_id__in=college_depts)
        form.fields['course'].queryset = Course.objects.filter(period__department_id__in=college_depts)
        form.fields['professor'].queryset = Professor.objects.filter(
            Q(college=college) | Q(college_relations__college=college)
        ).distinct()
        form.fields['room'].queryset = Room.objects.filter(
            collegeroom__college=college, collegeroom__is_active=True
        )
        if form.is_valid():
            data = form.cleaned_data
            conflicts = check_lecture_conflicts(
                data['department'].id, data['professor'].id, data['room'].id,
                data['day_of_week'], data['start_time'], data['end_time'], exclude_id=pk
            )
            if conflicts:
                for c in conflicts:
                    messages.warning(request, c['message'])
            else:
                old_data = serialize_lecture(schedule)
                updated = form.save()
                new_data = serialize_lecture(updated)
                log_schedule_change('edit', updated, request.user, old_data=old_data, new_data=new_data)
                _notify_students_schedule_change(updated, 'edit')
                messages.success(request, 'تم تعديل المحاضرة بنجاح')
                return redirect('cm_lecture_schedule')
    else:
        form = LectureScheduleForm(instance=schedule)
        form.fields['department'].queryset = Department.objects.filter(id__in=college_depts)
        form.fields['period'].queryset = DepartmentAcademicPeriod.objects.filter(department_id__in=college_depts)
        form.fields['course'].queryset = Course.objects.filter(period__department_id__in=college_depts)
        form.fields['professor'].queryset = Professor.objects.filter(
            Q(college=college) | Q(college_relations__college=college)
        ).distinct()
        form.fields['room'].queryset = Room.objects.filter(
            collegeroom__college=college, collegeroom__is_active=True
        )

    return render(request, 'timetable/cm_lecture_add.html', {
        'form': form, 'college': college, 'title': 'تعديل المحاضرة', 'back_url': 'cm_lecture_schedule', 'edit': True
    })


@require_department_head
def cm_lecture_delete(request, pk):
    college_depts = get_accessible_dept_ids(request.user)
    schedule = get_object_or_404(LectureSchedule, pk=pk, department_id__in=college_depts)
    if request.method == 'POST':
        old_data = serialize_lecture(schedule)
        _notify_students_schedule_change(schedule, 'delete')
        log_schedule_change('delete', schedule, request.user, old_data=old_data)
        schedule.delete()
        messages.success(request, 'تم حذف المحاضرة بنجاح')
        return redirect('cm_lecture_schedule')
    return render(request, 'timetable/confirm_delete.html', {
        'object': schedule, 'title': 'حذف المحاضرة', 'back_url': 'cm_lecture_schedule'
    })


# College Manager - Lab Schedule
@require_department_head
def cm_lab_schedule(request):
    college = get_college_for_manager(request.user)
    college_depts = get_accessible_dept_ids(request.user)
    dept_id = request.GET.get('dept_id')
    period_id = request.GET.get('period_id')

    schedules = LabSchedule.objects.filter(
        department_id__in=college_depts
    ).select_related('course', 'department', 'professor', 'hall', 'period', 'period__year', 'assistant')

    if dept_id:
        schedules = schedules.filter(department_id=dept_id)
    if period_id:
        schedules = schedules.filter(period_id=period_id)

    departments = Department.objects.filter(id__in=college_depts)
    sched_list = list(schedules)
    conflict_ids = set()
    for i, s1 in enumerate(sched_list):
        for s2 in sched_list[i+1:]:
            if s1.day_of_week != s2.day_of_week:
                continue
            if s1.start_time < s2.end_time and s1.end_time > s2.start_time:
                if s1.professor_id == s2.professor_id or s1.hall_id == s2.hall_id:
                    conflict_ids.add(s1.pk)
                    conflict_ids.add(s2.pk)
    return render(request, 'timetable/cm_lab_schedule.html', {
        'college': college, 'schedules': sched_list,
        'departments': departments, 'day_names': DAY_NAMES,
        'selected_dept': dept_id, 'selected_period': period_id,
        'conflict_ids': conflict_ids,
    })


@require_department_head
def cm_lab_add(request):
    college = get_college_for_manager(request.user)
    college_depts = get_accessible_dept_ids(request.user)

    if request.method == 'POST':
        form = LabScheduleForm(request.POST)
        form.fields['department'].queryset = Department.objects.filter(id__in=college_depts)
        form.fields['period'].queryset = DepartmentAcademicPeriod.objects.filter(department_id__in=college_depts)
        form.fields['course'].queryset = Course.objects.filter(period__department_id__in=college_depts)
        form.fields['professor'].queryset = Professor.objects.filter(
            Q(college=college) | Q(college_relations__college=college)
        ).distinct()
        form.fields['assistant'].queryset = Professor.objects.filter(
            Q(college=college) | Q(college_relations__college=college)
        ).distinct()
        form.fields['hall'].queryset = Hall.objects.filter(
            collegehall__college=college, collegehall__is_active=True
        )
        if form.is_valid():
            data = form.cleaned_data
            conflicts = check_lab_conflicts(
                data['department'].id, data['professor'].id, data['hall'].id,
                data['day_of_week'], data['start_time'], data['end_time']
            )
            if conflicts:
                for c in conflicts:
                    messages.warning(request, c['message'])
            else:
                lab = form.save()
                log_schedule_change('add', lab, request.user, new_data=serialize_lab(lab))
                _notify_students_schedule_change(lab, 'add')
                messages.success(request, 'تم إضافة جدول المعمل بنجاح')
                return redirect('cm_lab_schedule')
    else:
        form = LabScheduleForm()
        form.fields['department'].queryset = Department.objects.filter(id__in=college_depts)
        form.fields['period'].queryset = DepartmentAcademicPeriod.objects.filter(department_id__in=college_depts)
        form.fields['course'].queryset = Course.objects.filter(period__department_id__in=college_depts)
        form.fields['professor'].queryset = Professor.objects.filter(
            Q(college=college) | Q(college_relations__college=college)
        ).distinct()
        form.fields['assistant'].queryset = Professor.objects.filter(
            Q(college=college) | Q(college_relations__college=college)
        ).distinct()
        form.fields['hall'].queryset = Hall.objects.filter(
            collegehall__college=college, collegehall__is_active=True
        )

    return render(request, 'timetable/cm_lab_add.html', {
        'form': form, 'college': college, 'title': 'إضافة جدول معمل', 'back_url': 'cm_lab_schedule'
    })


@require_department_head
def cm_lab_edit(request, pk):
    college = get_college_for_manager(request.user)
    college_depts = get_accessible_dept_ids(request.user)
    schedule = get_object_or_404(LabSchedule, pk=pk, department_id__in=college_depts)

    if request.method == 'POST':
        form = LabScheduleForm(request.POST, instance=schedule)
        form.fields['department'].queryset = Department.objects.filter(id__in=college_depts)
        form.fields['period'].queryset = DepartmentAcademicPeriod.objects.filter(department_id__in=college_depts)
        form.fields['course'].queryset = Course.objects.filter(period__department_id__in=college_depts)
        form.fields['professor'].queryset = Professor.objects.filter(
            Q(college=college) | Q(college_relations__college=college)
        ).distinct()
        form.fields['assistant'].queryset = Professor.objects.filter(
            Q(college=college) | Q(college_relations__college=college)
        ).distinct()
        form.fields['hall'].queryset = Hall.objects.filter(
            collegehall__college=college, collegehall__is_active=True
        )
        if form.is_valid():
            data = form.cleaned_data
            conflicts = check_lab_conflicts(
                data['department'].id, data['professor'].id, data['hall'].id,
                data['day_of_week'], data['start_time'], data['end_time'], exclude_id=schedule.pk
            )
            if conflicts:
                for c in conflicts:
                    messages.warning(request, c['message'])
            else:
                old_data = serialize_lab(schedule)
                updated_lab = form.save()
                log_schedule_change('edit', updated_lab, request.user, old_data=old_data, new_data=serialize_lab(updated_lab))
                _notify_students_schedule_change(updated_lab, 'edit')
                messages.success(request, 'تم تعديل جدول المعمل بنجاح')
                return redirect('cm_lab_schedule')
    else:
        form = LabScheduleForm(instance=schedule)
        form.fields['department'].queryset = Department.objects.filter(id__in=college_depts)
        form.fields['period'].queryset = DepartmentAcademicPeriod.objects.filter(department_id__in=college_depts)
        form.fields['course'].queryset = Course.objects.filter(period__department_id__in=college_depts)
        form.fields['professor'].queryset = Professor.objects.filter(
            Q(college=college) | Q(college_relations__college=college)
        ).distinct()
        form.fields['assistant'].queryset = Professor.objects.filter(
            Q(college=college) | Q(college_relations__college=college)
        ).distinct()
        form.fields['hall'].queryset = Hall.objects.filter(
            collegehall__college=college, collegehall__is_active=True
        )

    return render(request, 'timetable/cm_lab_add.html', {
        'form': form, 'college': college, 'title': 'تعديل جدول معمل', 'back_url': 'cm_lab_schedule',
        'edit': True, 'pk': schedule.pk,
    })


@require_department_head
def cm_lab_delete(request, pk):
    college_depts = get_accessible_dept_ids(request.user)
    schedule = get_object_or_404(LabSchedule, pk=pk, department_id__in=college_depts)
    if request.method == 'POST':
        old_data = serialize_lab(schedule)
        _notify_students_schedule_change(schedule, 'delete')
        log_schedule_change('delete', schedule, request.user, old_data=old_data)
        schedule.delete()
        messages.success(request, 'تم حذف جدول المعمل بنجاح')
        return redirect('cm_lab_schedule')
    return render(request, 'timetable/confirm_delete.html', {
        'object': schedule, 'title': 'حذف جدول المعمل', 'back_url': 'cm_lab_schedule'
    })


# College Manager - Students
@require_department_head
def cm_student_list(request):
    college = get_college_for_manager(request.user)
    college_depts = get_accessible_dept_ids(request.user)
    students = Student.objects.filter(department_id__in=college_depts).select_related('department', 'period', 'period__year').order_by('name')
    return render(request, 'timetable/cm_students.html', {'college': college, 'students': students})


@require_department_head
def cm_student_add(request):
    college = get_college_for_manager(request.user)
    college_depts = get_accessible_dept_ids(request.user)
    if request.method == 'POST':
        form = StudentForm(request.POST)
        form.fields['department'].queryset = Department.objects.filter(id__in=college_depts)
        form.fields['period'].queryset = DepartmentAcademicPeriod.objects.filter(department_id__in=college_depts)
        if form.is_valid():
            try:
                with transaction.atomic():
                    student = form.save()
                    password = form.cleaned_data.get('password_plain') or 'student123'
                    hashed = bcrypt.hashpw(password.encode('utf-8'), bcrypt.gensalt()).decode('utf-8')
                    UnifiedUser.objects.create(
                        user_type='student',
                        user_id=student.id,
                        username=student.username or str(student.id),
                        full_name=student.name or '',
                        email=student.email or '',
                        department=student.department,
                        password=hashed,
                        is_active=True,
                    )
                messages.success(request, 'تم إضافة الطالب بنجاح')
                return redirect('cm_student_list')
            except IntegrityError:
                form.add_error('username', 'اسم المستخدم هذا مستخدم بالفعل. الرجاء اختيار اسم آخر.')
    else:
        form = StudentForm()
        form.fields['department'].queryset = Department.objects.filter(id__in=college_depts)
        form.fields['period'].queryset = DepartmentAcademicPeriod.objects.filter(department_id__in=college_depts)
    return render(request, 'timetable/form.html', {'form': form, 'title': 'إضافة طالب', 'back_url': 'cm_student_list'})


@require_department_head
def cm_student_delete(request, pk):
    college_depts = get_accessible_dept_ids(request.user)
    student = get_object_or_404(Student, pk=pk, department_id__in=college_depts)
    if request.method == 'POST':
        UnifiedUser.objects.filter(user_type='student', user_id=pk).delete()
        student.delete()
        messages.success(request, 'تم حذف الطالب بنجاح')
        return redirect('cm_student_list')
    return render(request, 'timetable/confirm_delete.html', {'object': student, 'title': 'حذف الطالب', 'back_url': 'cm_student_list'})


# Department Head - Alternative Times (Change Requests)
@require_department_head
def cm_requests_list(request):
    college = get_college_for_manager(request.user)
    dept_ids = get_accessible_dept_ids(request.user)
    status_filter = request.GET.get('status', '')

    requests_qs = AlternativeTime.objects.filter(
        schedule__department_id__in=dept_ids
    ).select_related('professor', 'schedule', 'schedule__department', 'room').order_by('-created_at')

    if status_filter:
        requests_qs = requests_qs.filter(status=status_filter)

    if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
        from django.template.loader import render_to_string
        html = render_to_string('timetable/cm_requests_table.html', {
            'requests': requests_qs, 'status_filter': status_filter
        }, request=request)
        from django.http import JsonResponse
        return JsonResponse({'html': html, 'count': requests_qs.count()})

    return render(request, 'timetable/cm_requests.html', {
        'college': college, 'requests': requests_qs, 'status_filter': status_filter
    })


@require_department_head
def cm_request_approve(request, pk):
    dept_ids = get_accessible_dept_ids(request.user)
    alt_time = get_object_or_404(AlternativeTime, pk=pk, schedule__department_id__in=dept_ids)
    if request.method == 'POST':
        admin_notes = request.POST.get('admin_notes', '')
        alt_time.status = 'approved'
        alt_time.admin_notes = admin_notes
        alt_time.save()
        try:
            prof_user = UnifiedUser.objects.get(user_type='professor', user_id=alt_time.professor.id)
            Notification.objects.create(
                recipient=prof_user,
                recipient_type='professor',
                subject='تم الموافقة على طلب تغيير الموعد',
                message=f'تم الموافقة على طلب تغيير موعد مادة {alt_time.course_name}',
            )
        except UnifiedUser.DoesNotExist:
            pass
        if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            from django.http import JsonResponse
            return JsonResponse({'success': True, 'message': 'تمت الموافقة على الطلب'})
        messages.success(request, 'تمت الموافقة على الطلب')
        return redirect('cm_requests_list')
    return render(request, 'timetable/cm_request_review.html', {
        'request_obj': alt_time, 'action': 'approve', 'day_names': DAY_NAMES
    })


@require_department_head
def cm_request_reject(request, pk):
    dept_ids = get_accessible_dept_ids(request.user)
    alt_time = get_object_or_404(AlternativeTime, pk=pk, schedule__department_id__in=dept_ids)
    if request.method == 'POST':
        admin_notes = request.POST.get('admin_notes', '')
        alt_time.status = 'rejected'
        alt_time.admin_notes = admin_notes
        alt_time.save()
        try:
            prof_user = UnifiedUser.objects.get(user_type='professor', user_id=alt_time.professor.id)
            Notification.objects.create(
                recipient=prof_user,
                recipient_type='professor',
                subject='تم رفض طلب تغيير الموعد',
                message=f'تم رفض طلب تغيير موعد مادة {alt_time.course_name}. السبب: {admin_notes}',
            )
        except UnifiedUser.DoesNotExist:
            pass
        if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            from django.http import JsonResponse
            return JsonResponse({'success': True, 'message': 'تم رفض الطلب'})
        messages.success(request, 'تم رفض الطلب')
        return redirect('cm_requests_list')
    return render(request, 'timetable/cm_request_review.html', {
        'request_obj': alt_time, 'action': 'reject', 'day_names': DAY_NAMES
    })


# College Manager - Reports
@require_department_head
def cm_report_professor_schedule(request):
    college = get_college_for_manager(request.user)
    prof_id = request.GET.get('professor_id')
    professor = None
    lectures = []
    labs = []

    schedule_grid = {day: [] for day in DAY_ORDER}
    workload = None

    if prof_id:
        professor = get_object_or_404(Professor, pk=prof_id)
        lectures = LectureSchedule.objects.filter(professor=professor).select_related(
            'course', 'department', 'room', 'period', 'period__year'
        ).order_by('day_of_week', 'start_time')
        labs = LabSchedule.objects.filter(
            Q(professor=professor) | Q(assistant=professor)
        ).select_related('course', 'department', 'hall', 'period', 'period__year').order_by('day_of_week', 'start_time')

        for lec in lectures:
            schedule_grid[lec.day_of_week].append({'type': 'lecture', 'obj': lec})
        for lab in labs:
            schedule_grid[lab.day_of_week].append({'type': 'lab', 'obj': lab})
        for day in schedule_grid:
            schedule_grid[day].sort(key=lambda x: x['obj'].start_time)

        from datetime import datetime as _dt
        total_lec_mins = sum(
            (_dt.combine(_dt.today(), lec.end_time) - _dt.combine(_dt.today(), lec.start_time)).seconds // 60
            for lec in lectures
        )
        total_lab_mins = sum(
            (_dt.combine(_dt.today(), lab.end_time) - _dt.combine(_dt.today(), lab.start_time)).seconds // 60
            for lab in labs
        )
        workload = {
            'lectures': lectures.count(),
            'labs': labs.count(),
            'lec_hours': round(total_lec_mins / 60, 1),
            'lab_hours': round(total_lab_mins / 60, 1),
            'total_hours': round((total_lec_mins + total_lab_mins) / 60, 1),
        }

    professors = Professor.objects.filter(
        Q(college=college) | Q(college_relations__college=college)
    ).distinct().order_by('name')

    # Build workload summary for ALL professors
    from datetime import datetime as _dt2
    all_workloads = []
    for prof in professors:
        p_lecs = LectureSchedule.objects.filter(professor=prof)
        p_labs = LabSchedule.objects.filter(Q(professor=prof) | Q(assistant=prof))
        lec_mins = sum(
            (_dt2.combine(_dt2.today(), l.end_time) - _dt2.combine(_dt2.today(), l.start_time)).seconds // 60
            for l in p_lecs
        )
        lab_mins = sum(
            (_dt2.combine(_dt2.today(), l.end_time) - _dt2.combine(_dt2.today(), l.start_time)).seconds // 60
            for l in p_labs
        )
        total_hrs = round((lec_mins + lab_mins) / 60, 1)
        all_workloads.append({
            'professor': prof,
            'lec_count': p_lecs.count(),
            'lab_count': p_labs.count(),
            'lec_hours': round(lec_mins / 60, 1),
            'lab_hours': round(lab_mins / 60, 1),
            'total_hours': total_hrs,
            'status': 'overloaded' if total_hrs > 20 else ('underloaded' if total_hrs < 6 and (p_lecs.count() + p_labs.count()) == 0 else 'normal'),
        })

    return render(request, 'timetable/cm_report_professor.html', {
        'college': college,
        'professors': professors,
        'professor': professor,
        'lectures': lectures,
        'labs': labs,
        'schedule_grid': schedule_grid,
        'workload': workload,
        'day_names': DAY_NAMES,
        'day_order': DAY_ORDER,
        'all_workloads': all_workloads,
    })


@require_department_head
def cm_report_room_schedule(request):
    college = get_college_for_manager(request.user)
    room_id = request.GET.get('room_id')
    room = None
    lectures = []

    if room_id:
        room = get_object_or_404(Room, pk=room_id)
        lectures = LectureSchedule.objects.filter(room=room).select_related(
            'course', 'department', 'professor', 'period', 'period__year'
        ).order_by('day_of_week', 'start_time')

    rooms = Room.objects.filter(collegeroom__college=college, collegeroom__is_active=True)
    return render(request, 'timetable/cm_report_room.html', {
        'college': college, 'rooms': rooms, 'room': room, 'lectures': lectures,
        'day_names': DAY_NAMES, 'day_order': DAY_ORDER,
    })


@require_department_head
def cm_deadline_settings(request):
    college = get_college_for_manager(request.user)
    deadline = ScheduleDeadline.objects.order_by('-created_at').first()
    if request.method == 'POST':
        form = ScheduleDeadlineForm(request.POST, instance=deadline)
        if form.is_valid():
            form.save()
            messages.success(request, 'تم حفظ الموعد النهائي')
            return redirect('college_manager_dashboard')
    else:
        form = ScheduleDeadlineForm(instance=deadline)
    return render(request, 'timetable/form.html', {
        'form': form, 'title': 'تحديد الموعد النهائي للجداول', 'back_url': 'college_manager_dashboard'
    })


# College Manager - Notifications
@require_college_manager
def cm_notifications(request):
    college = get_college_for_manager(request.user)
    notifications = Notification.objects.filter(
        recipient=request.user
    ).order_by('-created_at')[:50]
    return render(request, 'timetable/cm_notifications.html', {
        'college': college, 'notifications': notifications
    })


# ─────────────────────────────────────────────
# Professor Views
# ─────────────────────────────────────────────

@require_professor
def professor_schedule(request):
    user = request.user
    try:
        professor = Professor.objects.get(id=user.user_id)
    except Professor.DoesNotExist:
        messages.error(request, 'لم يتم العثور على بيانات الأستاذ')
        return redirect('login')

    lectures = LectureSchedule.objects.filter(professor=professor).select_related(
        'course', 'department', 'room', 'period', 'period__year'
    ).order_by('day_of_week', 'start_time')

    labs = LabSchedule.objects.filter(
        Q(professor=professor) | Q(assistant=professor)
    ).select_related(
        'course', 'department', 'hall', 'period', 'period__year', 'assistant'
    ).order_by('day_of_week', 'start_time')

    # Build schedule grid
    schedule_grid = {day: [] for day in DAY_ORDER}
    for lec in lectures:
        schedule_grid[lec.day_of_week].append({'type': 'lecture', 'obj': lec})
    for lab in labs:
        schedule_grid[lab.day_of_week].append({'type': 'lab', 'obj': lab})

    for day in schedule_grid:
        schedule_grid[day].sort(key=lambda x: x['obj'].start_time)

    notifications = Notification.objects.filter(recipient=user).order_by('-created_at')[:10]

    return render(request, 'timetable/professor_schedule.html', {
        'professor': professor,
        'lectures': lectures,
        'labs': labs,
        'schedule_grid': schedule_grid,
        'day_order': DAY_ORDER,
        'day_names': DAY_NAMES,
        'notifications': notifications,
    })


@require_professor
def professor_requests(request):
    user = request.user
    try:
        professor = Professor.objects.get(id=user.user_id)
    except Professor.DoesNotExist:
        return redirect('login')

    requests_qs = AlternativeTime.objects.filter(professor=professor).select_related('room').order_by('-created_at')
    return render(request, 'timetable/professor_requests.html', {
        'professor': professor, 'requests': requests_qs, 'day_names': DAY_NAMES
    })


@require_professor
def professor_request_add(request):
    user = request.user
    try:
        professor = Professor.objects.get(id=user.user_id)
    except Professor.DoesNotExist:
        return redirect('login')

    if request.method == 'POST':
        schedule_id = request.POST.get('schedule_id')
        day = request.POST.get('day')
        time_start = request.POST.get('time_start')
        time_end = request.POST.get('time_end')
        room_id = request.POST.get('room_id')
        notes = request.POST.get('notes', '')

        try:
            schedule = LectureSchedule.objects.get(pk=schedule_id, professor=professor)
            alt = AlternativeTime.objects.create(
                professor=professor,
                schedule=schedule,
                course_name=schedule.course.course_name,
                original_day=schedule.day_of_week,
                original_time_start=schedule.start_time,
                original_time_end=schedule.end_time,
                original_room=schedule.room,
                day=day,
                time_start=time_start or None,
                time_end=time_end or None,
                room_id=room_id or None,
                notes=notes,
                status='pending',
            )
            # Notify the department_head responsible for this lecture's department
            try:
                dept_head_user = UnifiedUser.objects.filter(
                    user_type='department_head',
                    department=schedule.department,
                ).first()
                if dept_head_user:
                    Notification.objects.create(
                        recipient=dept_head_user,
                        recipient_type='department_head',
                        subject='طلب تغيير موعد محاضرة',
                        message=f'الأستاذ {professor.name} يطلب تغيير موعد مادة {schedule.course.course_name} في قسم {schedule.department.name}',
                    )
            except Exception:
                pass
            messages.success(request, 'تم إرسال الطلب بنجاح')
            return redirect('professor_requests')
        except LectureSchedule.DoesNotExist:
            messages.error(request, 'المحاضرة غير موجودة')

    lectures = LectureSchedule.objects.filter(professor=professor).select_related('course', 'room')
    rooms = Room.objects.filter(collegeroom__college=professor.college, collegeroom__is_active=True)
    return render(request, 'timetable/professor_request_add.html', {
        'professor': professor, 'lectures': lectures, 'rooms': rooms, 'day_names': DAY_NAMES, 'day_order': DAY_ORDER
    })


@require_professor
def professor_request_delete(request, pk):
    user = request.user
    try:
        professor = Professor.objects.get(id=user.user_id)
    except Professor.DoesNotExist:
        return redirect('login')
    alt = get_object_or_404(AlternativeTime, pk=pk, professor=professor)
    if request.method == 'POST':
        if alt.status == 'pending':
            alt.delete()
            messages.success(request, 'تم حذف الطلب')
        else:
            messages.error(request, 'لا يمكن حذف طلب تمت معالجته')
        return redirect('professor_requests')
    return render(request, 'timetable/confirm_delete.html', {
        'object': alt, 'title': 'حذف الطلب', 'back_url': 'professor_requests'
    })


@require_professor
def professor_taught_lecture(request, schedule_id):
    user = request.user
    try:
        professor = Professor.objects.get(id=user.user_id)
    except Professor.DoesNotExist:
        return redirect('login')

    schedule = get_object_or_404(LectureSchedule, pk=schedule_id, professor=professor)
    if request.method == 'POST':
        taught_date = request.POST.get('taught_date') or date.today()
        TaughtLecture.objects.create(
            schedule=schedule,
            professor=professor,
            taught_date=taught_date,
        )
        messages.success(request, 'تم تسجيل المحاضرة بنجاح')
        return redirect('professor_schedule')
    return render(request, 'timetable/professor_taught.html', {
        'schedule': schedule, 'today': date.today().isoformat()
    })


@require_professor
def professor_notifications(request):
    user = request.user
    notifications = Notification.objects.filter(recipient=user).order_by('-created_at')
    unread_count = notifications.filter(is_read=False).count()
    # Mark all as read when viewed
    notifications.filter(is_read=False).update(is_read=True)
    return render(request, 'timetable/professor_notifications.html', {
        'notifications': notifications,
        'unread_count': unread_count,
    })


@login_required
def notifications_center(request):
    user = request.user
    notifications = Notification.objects.filter(recipient=user).order_by('-created_at')[:100]
    unread_count = Notification.objects.filter(recipient=user, is_read=False).count()
    return render(request, 'timetable/notifications_center.html', {
        'notifications': notifications,
        'unread_count': unread_count,
    })


# ─────────────────────────────────────────────
# Student Views
# ─────────────────────────────────────────────

@require_student
def student_schedule(request):
    user = request.user
    try:
        student = Student.objects.get(id=user.user_id)
    except Student.DoesNotExist:
        messages.error(request, 'لم يتم العثور على بيانات الطالب')
        return redirect('login')

    period = student.period
    lectures = LectureSchedule.objects.filter(
        period=period
    ).select_related('course', 'professor', 'room', 'period__year').order_by('day_of_week', 'start_time')

    labs = LabSchedule.objects.filter(
        period=period
    ).select_related('course', 'professor', 'hall', 'period__year', 'assistant').order_by('day_of_week', 'start_time')

    # Build schedule grid
    schedule_grid = {day: [] for day in DAY_ORDER}
    for lec in lectures:
        schedule_grid[lec.day_of_week].append({'type': 'lecture', 'obj': lec})
    for lab in labs:
        schedule_grid[lab.day_of_week].append({'type': 'lab', 'obj': lab})

    for day in schedule_grid:
        schedule_grid[day].sort(key=lambda x: x['obj'].start_time)

    notifications = Notification.objects.filter(recipient=user).order_by('-created_at')[:10]

    return render(request, 'timetable/student_schedule.html', {
        'student': student,
        'period': period,
        'lectures': lectures,
        'labs': labs,
        'schedule_grid': schedule_grid,
        'day_order': DAY_ORDER,
        'day_names': DAY_NAMES,
        'notifications': notifications,
    })


# ─────────────────────────────────────────────
# Change Password (all roles)
# ─────────────────────────────────────────────

@login_required
def change_password_view(request):
    if request.method == 'POST':
        form = ChangePasswordForm(request.POST)
        if form.is_valid():
            user = request.user
            old_pass = form.cleaned_data['old_password']
            new_pass = form.cleaned_data['new_password']

            # Verify old password
            stored = user.password
            if stored.startswith('$2y$') or stored.startswith('$2b$'):
                python_hash = stored.replace('$2y$', '$2b$', 1)
                try:
                    if not bcrypt.checkpw(old_pass.encode('utf-8'), python_hash.encode('utf-8')):
                        messages.error(request, 'كلمة المرور الحالية غير صحيحة')
                        return render(request, 'timetable/change_password.html', {'form': form})
                except Exception:
                    messages.error(request, 'خطأ في التحقق من كلمة المرور')
                    return render(request, 'timetable/change_password.html', {'form': form})
            else:
                if old_pass != stored:
                    messages.error(request, 'كلمة المرور الحالية غير صحيحة')
                    return render(request, 'timetable/change_password.html', {'form': form})

            # Set new password
            new_hashed = bcrypt.hashpw(new_pass.encode('utf-8'), bcrypt.gensalt()).decode('utf-8')
            user.password = new_hashed
            user.save()
            messages.success(request, 'تم تغيير كلمة المرور بنجاح')
            return redirect('home')
    else:
        form = ChangePasswordForm()
    return render(request, 'timetable/change_password.html', {'form': form})


# ─────────────────────────────────────────────
# Edit Profile View
# ─────────────────────────────────────────────

@login_required
def edit_profile_view(request):
    return redirect('account_settings')


@login_required
def account_settings_view(request):
    user = request.user
    profile_errors = {}
    password_errors = {}
    active_tab = 'profile'

    if request.method == 'POST':
        action = request.POST.get('action', 'profile')

        if action == 'profile':
            active_tab = 'profile'
            full_name = request.POST.get('full_name', '').strip()
            email = request.POST.get('email', '').strip()
            if not full_name:
                profile_errors['full_name'] = 'الاسم الكامل مطلوب'
            if not email:
                profile_errors['email'] = 'البريد الإلكتروني مطلوب'
            elif '@' not in email:
                profile_errors['email'] = 'أدخل بريداً إلكترونياً صحيحاً'
            if not profile_errors:
                user.full_name = full_name
                user.email = email
                user.save(update_fields=['full_name', 'email'])
                messages.success(request, 'تم تحديث البيانات الشخصية بنجاح')
                return redirect('account_settings')
            return render(request, 'timetable/account_settings.html', {
                'profile_errors': profile_errors,
                'full_name': full_name,
                'email': email,
                'active_tab': active_tab,
            })

        elif action == 'password':
            active_tab = 'password'
            old_pass = request.POST.get('old_password', '')
            new_pass = request.POST.get('new_password', '')
            new_pass2 = request.POST.get('new_password2', '')
            if not old_pass:
                password_errors['old_password'] = 'كلمة المرور الحالية مطلوبة'
            if not new_pass:
                password_errors['new_password'] = 'كلمة المرور الجديدة مطلوبة'
            elif len(new_pass) < 6:
                password_errors['new_password'] = 'كلمة المرور يجب أن تكون 6 أحرف على الأقل'
            if new_pass and new_pass != new_pass2:
                password_errors['new_password2'] = 'كلمتا المرور غير متطابقتين'
            if not password_errors:
                stored = user.password
                python_hash = stored.replace('$2y$', '$2b$', 1)
                try:
                    if not bcrypt.checkpw(old_pass.encode('utf-8'), python_hash.encode('utf-8')):
                        password_errors['old_password'] = 'كلمة المرور الحالية غير صحيحة'
                except Exception:
                    if old_pass != stored:
                        password_errors['old_password'] = 'كلمة المرور الحالية غير صحيحة'
            if not password_errors:
                new_hashed = bcrypt.hashpw(new_pass.encode('utf-8'), bcrypt.gensalt()).decode('utf-8')
                user.password = new_hashed
                user.save()
                messages.success(request, 'تم تغيير كلمة المرور بنجاح')
                return redirect('account_settings')
            return render(request, 'timetable/account_settings.html', {
                'password_errors': password_errors,
                'active_tab': 'password',
            })

    return render(request, 'timetable/account_settings.html', {
        'active_tab': active_tab,
    })


# ─────────────────────────────────────────────
# Public Schedule View
# ─────────────────────────────────────────────

def public_schedule(request):
    college_id = request.GET.get('college_id')
    dept_id = request.GET.get('dept_id')
    period_id = request.GET.get('period_id')

    colleges = College.objects.all().order_by('name')
    departments = []
    periods = []
    lectures = []
    labs = []

    if college_id:
        departments = Department.objects.filter(
            collegedepartment__college_id=college_id
        ).distinct().order_by('name')

    if dept_id:
        periods = DepartmentAcademicPeriod.objects.filter(
            department_id=dept_id
        ).select_related('year').order_by('year__year_number', 'semester_type')

    if period_id:
        lectures = LectureSchedule.objects.filter(period_id=period_id).select_related(
            'course', 'professor', 'room', 'department'
        ).order_by('day_of_week', 'start_time')
        labs = LabSchedule.objects.filter(period_id=period_id).select_related(
            'course', 'professor', 'hall', 'department', 'assistant'
        ).order_by('day_of_week', 'start_time')

    schedule_grid = {day: [] for day in DAY_ORDER}
    for lec in lectures:
        schedule_grid[lec.day_of_week].append({'type': 'lecture', 'obj': lec})
    for lab in labs:
        schedule_grid[lab.day_of_week].append({'type': 'lab', 'obj': lab})
    for day in schedule_grid:
        schedule_grid[day].sort(key=lambda x: x['obj'].start_time)

    return render(request, 'timetable/public_schedule.html', {
        'colleges': colleges,
        'departments': departments,
        'periods': periods,
        'lectures': lectures,
        'labs': labs,
        'schedule_grid': schedule_grid,
        'day_order': DAY_ORDER,
        'day_names': DAY_NAMES,
        'selected_college': college_id,
        'selected_dept': dept_id,
        'selected_period': period_id,
    })


# ─────────────────────────────────────────────
# AJAX / API Views
# ─────────────────────────────────────────────

@login_required
def api_check_conflicts(request):
    if request.method != 'POST':
        return JsonResponse({'error': 'Method not allowed'}, status=405)
    try:
        data = json.loads(request.body)
        dept_id = data.get('department_id')
        prof_id = data.get('professor_id')
        room_id = data.get('room_id')
        day = data.get('day_of_week')
        start = data.get('start_time')
        end = data.get('end_time')
        exclude_id = data.get('exclude_id')

        from datetime import time as dtime
        start_t = dtime.fromisoformat(start) if start else None
        end_t = dtime.fromisoformat(end) if end else None

        conflicts = check_lecture_conflicts(dept_id, prof_id, room_id, day, start_t, end_t, exclude_id)
        return JsonResponse({'conflicts': conflicts, 'has_conflicts': len(conflicts) > 0})
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=400)


@login_required
def api_get_periods(request):
    dept_id = request.GET.get('dept_id')
    if not dept_id:
        return JsonResponse({'periods': []})
    periods = DepartmentAcademicPeriod.objects.filter(
        department_id=dept_id
    ).select_related('year').order_by('year__year_number', 'semester_type')
    data = [{'id': p.id, 'label': f'{p.year.year_name} - فصل {p.semester_type}'} for p in periods]
    return JsonResponse({'periods': data})


@login_required
def api_get_courses(request):
    period_id = request.GET.get('period_id')
    if not period_id:
        return JsonResponse({'courses': []})
    courses = Course.objects.filter(period_id=period_id).order_by('course_name')
    data = [{'id': c.id, 'label': f'{c.course_name} ({c.course_code})'} for c in courses]
    return JsonResponse({'courses': data})


@login_required
def api_get_rooms(request):
    college_id = request.GET.get('college_id')
    if college_id:
        rooms = Room.objects.filter(collegeroom__college_id=college_id, collegeroom__is_active=True)
    else:
        rooms = Room.objects.all()
    data = [{'id': r.id, 'label': f'{r.name} ({r.code}) - {r.capacity} مقعد'} for r in rooms]
    return JsonResponse({'rooms': data})


@login_required
def api_get_halls(request):
    college_id = request.GET.get('college_id')
    if college_id:
        halls = Hall.objects.filter(collegehall__college_id=college_id, collegehall__is_active=True)
    else:
        halls = Hall.objects.all()
    data = [{'id': h.id, 'label': f'{h.name} ({h.code}) - {h.capacity} مقعد'} for h in halls]
    return JsonResponse({'halls': data})


# ─────────────────────────────────────────────
# College Manager - Dept Head Management
# ─────────────────────────────────────────────

@require_college_manager_only
def cm_dept_head_list(request):
    college = get_college_for_manager(request.user)
    dept_heads = UnifiedUser.objects.filter(
        user_type='department_head', college=college
    ).select_related('department').order_by('full_name')
    dept_ids = get_accessible_dept_ids(request.user)
    departments = Department.objects.filter(id__in=dept_ids)
    return render(request, 'timetable/cm_dept_heads.html', {
        'college': college,
        'dept_heads': dept_heads,
        'departments': departments,
    })


@require_college_manager_only
def cm_dept_head_add(request):
    college = get_college_for_manager(request.user)
    dept_ids = get_accessible_dept_ids(request.user)
    departments = Department.objects.filter(id__in=dept_ids)
    if request.method == 'POST':
        username = request.POST.get('username', '').strip()
        full_name = request.POST.get('full_name', '').strip()
        email = request.POST.get('email', '').strip()
        password = request.POST.get('password', '').strip()
        dept_id = request.POST.get('department_id')
        errors = []
        if not username:
            errors.append('اسم المستخدم مطلوب')
        if not full_name:
            errors.append('الاسم الكامل مطلوب')
        if not password:
            errors.append('كلمة المرور مطلوبة')
        if not dept_id:
            errors.append('يجب تحديد القسم')
        if username and UnifiedUser.objects.filter(username=username).exists():
            errors.append('اسم المستخدم موجود بالفعل')
        if errors:
            for e in errors:
                messages.error(request, e)
        else:
            dept = get_object_or_404(Department, pk=dept_id)
            hashed = bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode()
            UnifiedUser.objects.create(
                username=username,
                full_name=full_name,
                email=email or f'{username}@tms.local',
                user_type='department_head',
                college=college,
                department=dept,
                is_active=True,
                is_staff=False,
                password=hashed,
                user_id=0,
            )
            messages.success(request, f'تم إضافة رئيس القسم {full_name} بنجاح')
            return redirect('cm_dept_head_list')
    return render(request, 'timetable/cm_dept_head_add.html', {
        'college': college,
        'departments': departments,
    })


@require_college_manager_only
def cm_dept_head_delete(request, pk):
    college = get_college_for_manager(request.user)
    user_to_delete = get_object_or_404(UnifiedUser, pk=pk, user_type='department_head')
    if user_to_delete.college != college:
        messages.error(request, 'لا يمكنك حذف هذا المستخدم')
        return redirect('cm_dept_head_list')
    if request.method == 'POST':
        user_to_delete.delete()
        messages.success(request, 'تم حذف رئيس القسم بنجاح')
        return redirect('cm_dept_head_list')
    return render(request, 'timetable/confirm_delete.html', {
        'object': user_to_delete,
        'title': 'حذف رئيس القسم',
        'back_url': 'cm_dept_head_list',
    })


# ─────────────────────────────────────────────
# Public AJAX APIs (no login required)
# ─────────────────────────────────────────────

def api_public_departments(request):
    """Return departments for a college — public, no login needed."""
    college_id = request.GET.get('college_id')
    if not college_id:
        return JsonResponse({'departments': []})
    depts = Department.objects.filter(
        collegedepartment__college_id=college_id
    ).distinct().order_by('name')
    return JsonResponse({'departments': [{'id': d.id, 'name': d.name} for d in depts]})


def api_public_periods(request):
    """Return academic periods for a department — public, no login needed."""
    dept_id = request.GET.get('dept_id')
    if not dept_id:
        return JsonResponse({'periods': []})
    periods = DepartmentAcademicPeriod.objects.filter(
        department_id=dept_id
    ).select_related('year').order_by('year__year_number', 'semester_type')
    return JsonResponse({'periods': [
        {'id': p.id, 'label': f'{p.year.year_name} - فصل {p.semester_type}'}
        for p in periods
    ]})


def api_public_schedule_data(request):
    """Return schedule data for a period — public, no login needed."""
    period_id = request.GET.get('period_id')
    if not period_id:
        return JsonResponse({'lectures': [], 'labs': [], 'has_data': False})
    lectures = LectureSchedule.objects.filter(period_id=period_id).select_related(
        'course', 'professor', 'room', 'department'
    ).order_by('day_of_week', 'start_time')
    labs = LabSchedule.objects.filter(period_id=period_id).select_related(
        'course', 'professor', 'hall', 'department', 'assistant'
    ).order_by('day_of_week', 'start_time')
    lecture_data = [
        {
            'id': l.id, 'type': 'lecture',
            'course_name': l.course.course_name,
            'course_code': l.course.course_code,
            'professor': l.professor.name,
            'room': l.room.name,
            'day': l.day_of_week,
            'day_name': DAY_NAMES.get(l.day_of_week, l.day_of_week),
            'start_time': str(l.start_time)[:5],
            'end_time': str(l.end_time)[:5],
            'lecture_type': l.lecture_type,
        } for l in lectures
    ]
    lab_data = [
        {
            'id': l.id, 'type': 'lab',
            'course_name': l.course.course_name,
            'course_code': l.course.course_code,
            'professor': l.professor.name,
            'assistant': l.assistant.name if l.assistant else '',
            'hall': l.hall.name,
            'day': l.day_of_week,
            'day_name': DAY_NAMES.get(l.day_of_week, l.day_of_week),
            'start_time': str(l.start_time)[:5],
            'end_time': str(l.end_time)[:5],
            'group_number': l.group_number or '',
        } for l in labs
    ]
    return JsonResponse({
        'lectures': lecture_data,
        'labs': lab_data,
        'has_data': len(lecture_data) + len(lab_data) > 0,
        'day_order': DAY_ORDER,
        'day_names': DAY_NAMES,
    })


# ──────────────────────────────────────────────────────────────────────────────
# BULK DELETE VIEWS
# ──────────────────────────────────────────────────────────────────────────────

@require_department_head
@require_POST
def cm_lecture_bulk_delete(request):
    ids = request.POST.getlist('ids[]')
    if not ids:
        return JsonResponse({'success': False, 'error': 'لم يتم تحديد محاضرات'})
    college_depts = get_accessible_dept_ids(request.user)
    deleted = 0
    for pk in ids:
        try:
            schedule = LectureSchedule.objects.get(pk=pk, department_id__in=college_depts)
            old_data = serialize_lecture(schedule)
            log_schedule_change('delete', schedule, request.user, old_data=old_data)
            schedule.delete()
            deleted += 1
        except LectureSchedule.DoesNotExist:
            pass
    return JsonResponse({'success': True, 'deleted': deleted})


@require_department_head
@require_POST
def cm_lab_bulk_delete(request):
    ids = request.POST.getlist('ids[]')
    if not ids:
        return JsonResponse({'success': False, 'error': 'لم يتم تحديد معامل'})
    college_depts = get_accessible_dept_ids(request.user)
    deleted = 0
    for pk in ids:
        try:
            schedule = LabSchedule.objects.get(pk=pk, department_id__in=college_depts)
            old_data = serialize_lab(schedule)
            log_schedule_change('delete', schedule, request.user, old_data=old_data)
            schedule.delete()
            deleted += 1
        except LabSchedule.DoesNotExist:
            pass
    return JsonResponse({'success': True, 'deleted': deleted})


# ──────────────────────────────────────────────────────────────────────────────
# INLINE QUICK-EDIT VIEWS
# ──────────────────────────────────────────────────────────────────────────────

@require_department_head
def cm_lecture_inline_edit(request, pk):
    college_depts = get_accessible_dept_ids(request.user)
    schedule = get_object_or_404(LectureSchedule, pk=pk, department_id__in=college_depts)
    if request.method == 'POST':
        day = request.POST.get('day_of_week')
        start_time = request.POST.get('start_time')
        end_time = request.POST.get('end_time')
        try:
            old_data = serialize_lecture(schedule)
            if day:
                schedule.day_of_week = day
            if start_time:
                schedule.start_time = start_time
            if end_time:
                schedule.end_time = end_time
            schedule.save()
            new_data = serialize_lecture(schedule)
            log_schedule_change('edit', schedule, request.user, old_data=old_data, new_data=new_data)
            return JsonResponse({'success': True})
        except Exception as e:
            return JsonResponse({'success': False, 'error': str(e)})
    return JsonResponse({
        'pk': schedule.pk,
        'day_of_week': schedule.day_of_week,
        'start_time': schedule.start_time.strftime('%H:%M'),
        'end_time': schedule.end_time.strftime('%H:%M'),
        'course_name': schedule.course.course_name,
    })


@require_department_head
def cm_lab_inline_edit(request, pk):
    college_depts = get_accessible_dept_ids(request.user)
    schedule = get_object_or_404(LabSchedule, pk=pk, department_id__in=college_depts)
    if request.method == 'POST':
        day = request.POST.get('day_of_week')
        start_time = request.POST.get('start_time')
        end_time = request.POST.get('end_time')
        try:
            old_data = serialize_lab(schedule)
            if day:
                schedule.day_of_week = day
            if start_time:
                schedule.start_time = start_time
            if end_time:
                schedule.end_time = end_time
            schedule.save()
            new_data = serialize_lab(schedule)
            log_schedule_change('edit', schedule, request.user, old_data=old_data, new_data=new_data)
            return JsonResponse({'success': True})
        except Exception as e:
            return JsonResponse({'success': False, 'error': str(e)})
    return JsonResponse({
        'pk': schedule.pk,
        'day_of_week': schedule.day_of_week,
        'start_time': schedule.start_time.strftime('%H:%M'),
        'end_time': schedule.end_time.strftime('%H:%M'),
        'course_name': schedule.course.course_name,
    })
