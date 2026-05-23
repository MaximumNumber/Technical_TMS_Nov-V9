from django.contrib import admin
from django.contrib.auth.admin import UserAdmin
from .models import (
    UnifiedUser, University, Branch, College, Department,
    CollegeDepartment, AcademicYear, DepartmentAcademicPeriod,
    Course, Room, Hall, CollegeRoom, CollegeHall, Professor,
    Student, Role, LectureSchedule, LabSchedule, AlternativeTime,
    Notification, Semester, ScheduleDeadline, EmailSettings, EmailTemplate
)


@admin.register(UnifiedUser)
class UnifiedUserAdmin(UserAdmin):
    list_display = ('username', 'full_name', 'user_type', 'email', 'is_active')
    list_filter = ('user_type', 'is_active')
    search_fields = ('username', 'full_name', 'email')
    fieldsets = (
        (None, {'fields': ('username', 'password')}),
        ('المعلومات الشخصية', {'fields': ('full_name', 'email', 'user_type', 'user_id', 'department', 'college')}),
        ('الصلاحيات', {'fields': ('is_active', 'is_staff', 'is_superuser', 'groups', 'user_permissions')}),
    )
    add_fieldsets = (
        (None, {
            'classes': ('wide',),
            'fields': ('username', 'full_name', 'email', 'user_type', 'password1', 'password2'),
        }),
    )
    ordering = ('username',)


admin.site.register(University)
admin.site.register(Branch)
admin.site.register(College)
admin.site.register(Department)
admin.site.register(AcademicYear)
admin.site.register(DepartmentAcademicPeriod)
admin.site.register(Course)
admin.site.register(Room)
admin.site.register(Hall)
admin.site.register(Professor)
admin.site.register(Student)
admin.site.register(LectureSchedule)
admin.site.register(LabSchedule)
admin.site.register(AlternativeTime)
admin.site.register(Notification)
admin.site.register(EmailSettings)
admin.site.register(EmailTemplate)

admin.site.site_header = 'نظام إدارة الجداول الدراسية'
admin.site.site_title = 'TMS'
admin.site.index_title = 'لوحة تحكم المدير'
