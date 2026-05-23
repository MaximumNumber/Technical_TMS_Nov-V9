from django import forms
from django.contrib.auth.hashers import make_password
import bcrypt
from .models import (
    UnifiedUser, University, Branch, College, Department,
    AcademicYear, DepartmentAcademicPeriod, DepartmentStudentSettings,
    Specialization, Course, Room, Hall, Professor, Student, Role,
    LectureSchedule, LabSchedule, AlternativeTime, CollegeDepartment,
    CollegeRoom, CollegeHall, EmailSettings, ScheduleDeadline
)


class LoginForm(forms.Form):
    username = forms.CharField(
        label='اسم المستخدم أو البريد الإلكتروني',
        max_length=255,
        widget=forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'اسم المستخدم أو البريد الإلكتروني', 'autofocus': True})
    )
    password = forms.CharField(
        label='كلمة المرور',
        widget=forms.PasswordInput(attrs={'class': 'form-control', 'placeholder': 'كلمة المرور'})
    )


class UniversityForm(forms.ModelForm):
    class Meta:
        model = University
        fields = ['name', 'code', 'established_year']
        labels = {'name': 'اسم الجامعة', 'code': 'الرمز', 'established_year': 'سنة التأسيس'}
        widgets = {
            'name': forms.TextInput(attrs={'class': 'form-control'}),
            'code': forms.TextInput(attrs={'class': 'form-control'}),
            'established_year': forms.NumberInput(attrs={'class': 'form-control'}),
        }


class BranchForm(forms.ModelForm):
    class Meta:
        model = Branch
        fields = ['university', 'name', 'is_main']
        labels = {'university': 'الجامعة', 'name': 'اسم الفرع', 'is_main': 'الفرع الرئيسي'}
        widgets = {
            'university': forms.Select(attrs={'class': 'form-select'}),
            'name': forms.TextInput(attrs={'class': 'form-control'}),
            'is_main': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
        }


class CollegeForm(forms.ModelForm):
    class Meta:
        model = College
        fields = ['branch', 'name', 'code']
        labels = {'branch': 'الفرع', 'name': 'اسم الكلية', 'code': 'الرمز'}
        widgets = {
            'branch': forms.Select(attrs={'class': 'form-select'}),
            'name': forms.TextInput(attrs={'class': 'form-control'}),
            'code': forms.TextInput(attrs={'class': 'form-control'}),
        }


class DepartmentForm(forms.ModelForm):
    class Meta:
        model = Department
        fields = ['name', 'program_type', 'academic_program', 'total_semesters']
        labels = {
            'name': 'اسم القسم',
            'program_type': 'نوع البرنامج',
            'academic_program': 'البرنامج الأكاديمي',
            'total_semesters': 'عدد الفصول الدراسية'
        }
        widgets = {
            'name': forms.TextInput(attrs={'class': 'form-control'}),
            'program_type': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'بكالوريوس / ماجستير'}),
            'academic_program': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'شرف / انتظام'}),
            'total_semesters': forms.NumberInput(attrs={'class': 'form-control'}),
        }


class AcademicYearForm(forms.ModelForm):
    class Meta:
        model = AcademicYear
        fields = ['year_number', 'year_name']
        labels = {'year_number': 'رقم السنة', 'year_name': 'اسم السنة'}
        widgets = {
            'year_number': forms.NumberInput(attrs={'class': 'form-control'}),
            'year_name': forms.TextInput(attrs={'class': 'form-control'}),
        }


class DepartmentAcademicPeriodForm(forms.ModelForm):
    class Meta:
        model = DepartmentAcademicPeriod
        fields = ['department', 'year', 'semester_type']
        labels = {'department': 'القسم', 'year': 'السنة الدراسية', 'semester_type': 'الفصل الدراسي'}
        widgets = {
            'department': forms.Select(attrs={'class': 'form-select'}),
            'year': forms.Select(attrs={'class': 'form-select'}),
            'semester_type': forms.Select(attrs={'class': 'form-select'}),
        }


class DepartmentStudentSettingsForm(forms.ModelForm):
    class Meta:
        model = DepartmentStudentSettings
        fields = ['student_count', 'groups_count']
        labels = {'student_count': 'عدد الطلاب', 'groups_count': 'عدد المجموعات'}
        widgets = {
            'student_count': forms.NumberInput(attrs={'class': 'form-control', 'min': 0}),
            'groups_count': forms.NumberInput(attrs={'class': 'form-control', 'min': 0}),
        }


class SpecializationForm(forms.ModelForm):
    class Meta:
        model = Specialization
        fields = ['department', 'period', 'name']
        labels = {'department': 'القسم', 'period': 'الفترة الأكاديمية', 'name': 'اسم التخصص'}
        widgets = {
            'department': forms.Select(attrs={'class': 'form-select'}),
            'period': forms.Select(attrs={'class': 'form-select'}),
            'name': forms.TextInput(attrs={'class': 'form-control'}),
        }


class CourseForm(forms.ModelForm):
    exercise_hours = forms.IntegerField(
        label='ساعات التمرين', required=False, initial=0,
        widget=forms.NumberInput(attrs={'class': 'form-control', 'min': 0})
    )
    lab_hours = forms.IntegerField(
        label='ساعات المعمل', required=False, initial=0,
        widget=forms.NumberInput(attrs={'class': 'form-control', 'min': 0})
    )

    class Meta:
        model = Course
        fields = ['period', 'specialization', 'course_code', 'course_name', 'lecture_hours', 'exercise_hours', 'lab_hours', 'total_lectures', 'is_shared_across_departments', 'is_shared_across_colleges']
        labels = {
            'period': 'الفترة الأكاديمية',
            'specialization': 'التخصص',
            'course_code': 'رمز المادة',
            'course_name': 'اسم المادة',
            'lecture_hours': 'ساعات المحاضرة',
            'total_lectures': 'إجمالي المحاضرات',
            'is_shared_across_departments': 'مشتركة بين الأقسام',
            'is_shared_across_colleges': 'مشتركة بين الكليات',
        }
        widgets = {
            'period': forms.Select(attrs={'class': 'form-select'}),
            'specialization': forms.Select(attrs={'class': 'form-select'}),
            'course_code': forms.TextInput(attrs={'class': 'form-control'}),
            'course_name': forms.TextInput(attrs={'class': 'form-control'}),
            'lecture_hours': forms.NumberInput(attrs={'class': 'form-control', 'min': 0}),
            'total_lectures': forms.NumberInput(attrs={'class': 'form-control', 'min': 0}),
            'is_shared_across_departments': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
            'is_shared_across_colleges': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
        }

    def clean_exercise_hours(self):
        return self.cleaned_data.get('exercise_hours') or 0

    def clean_lab_hours(self):
        return self.cleaned_data.get('lab_hours') or 0


class RoomForm(forms.ModelForm):
    class Meta:
        model = Room
        fields = ['name', 'code', 'capacity', 'college']
        labels = {'name': 'اسم القاعة', 'code': 'الرمز', 'capacity': 'السعة', 'college': 'الكلية'}
        widgets = {
            'name': forms.TextInput(attrs={'class': 'form-control'}),
            'code': forms.TextInput(attrs={'class': 'form-control'}),
            'capacity': forms.NumberInput(attrs={'class': 'form-control', 'min': 1}),
            'college': forms.Select(attrs={'class': 'form-select'}),
        }


class HallForm(forms.ModelForm):
    class Meta:
        model = Hall
        fields = ['name', 'code', 'capacity', 'college']
        labels = {'name': 'اسم المعمل', 'code': 'الرمز', 'capacity': 'السعة', 'college': 'الكلية'}
        widgets = {
            'name': forms.TextInput(attrs={'class': 'form-control'}),
            'code': forms.TextInput(attrs={'class': 'form-control'}),
            'capacity': forms.NumberInput(attrs={'class': 'form-control', 'min': 1}),
            'college': forms.Select(attrs={'class': 'form-select'}),
        }


class ProfessorForm(forms.ModelForm):
    password_plain = forms.CharField(
        label='كلمة المرور',
        required=False,
        widget=forms.PasswordInput(attrs={'class': 'form-control', 'placeholder': 'اتركه فارغاً للإبقاء على كلمة المرور الحالية'})
    )

    class Meta:
        model = Professor
        fields = ['name', 'username', 'email', 'position', 'college']
        labels = {
            'name': 'الاسم الكامل',
            'username': 'اسم المستخدم',
            'email': 'البريد الإلكتروني',
            'position': 'الرتبة الأكاديمية',
            'college': 'الكلية',
        }
        widgets = {
            'name': forms.TextInput(attrs={'class': 'form-control'}),
            'username': forms.TextInput(attrs={'class': 'form-control'}),
            'email': forms.EmailInput(attrs={'class': 'form-control'}),
            'position': forms.Select(attrs={'class': 'form-select'}),
            'college': forms.Select(attrs={'class': 'form-select'}),
        }

    def save(self, commit=True):
        professor = super().save(commit=False)
        password = self.cleaned_data.get('password_plain')
        if password:
            hashed = bcrypt.hashpw(password.encode('utf-8'), bcrypt.gensalt()).decode('utf-8')
            professor.password = hashed
        if commit:
            professor.save()
        return professor


class StudentForm(forms.ModelForm):
    password_plain = forms.CharField(
        label='كلمة المرور',
        required=False,
        widget=forms.PasswordInput(attrs={'class': 'form-control'})
    )
    specialization_id = forms.IntegerField(
        label='التخصص', required=False, initial=0,
        widget=forms.NumberInput(attrs={'class': 'form-control', 'min': 0})
    )

    class Meta:
        model = Student
        fields = ['name', 'username', 'email', 'department', 'period', 'specialization_id']
        labels = {
            'name': 'الاسم الكامل',
            'username': 'اسم المستخدم',
            'email': 'البريد الإلكتروني',
            'department': 'القسم',
            'period': 'الفترة الأكاديمية',
        }
        widgets = {
            'name': forms.TextInput(attrs={'class': 'form-control'}),
            'username': forms.TextInput(attrs={'class': 'form-control'}),
            'email': forms.EmailInput(attrs={'class': 'form-control'}),
            'department': forms.Select(attrs={'class': 'form-select'}),
            'period': forms.Select(attrs={'class': 'form-select'}),
        }

    def clean_specialization_id(self):
        return self.cleaned_data.get('specialization_id') or 0

    def save(self, commit=True):
        student = super().save(commit=False)
        password = self.cleaned_data.get('password_plain')
        if password:
            hashed = bcrypt.hashpw(password.encode('utf-8'), bcrypt.gensalt()).decode('utf-8')
            student.password = hashed
        if commit:
            student.save()
        return student


class CollegeManagerForm(forms.ModelForm):
    password_plain = forms.CharField(
        label='كلمة المرور',
        required=False,
        widget=forms.PasswordInput(attrs={'class': 'form-control'})
    )

    class Meta:
        model = Role
        fields = ['full_name', 'username', 'email', 'college']
        labels = {
            'full_name': 'الاسم الكامل',
            'username': 'اسم المستخدم',
            'email': 'البريد الإلكتروني',
            'college': 'الكلية',
        }
        widgets = {
            'full_name': forms.TextInput(attrs={'class': 'form-control'}),
            'username': forms.TextInput(attrs={'class': 'form-control'}),
            'email': forms.EmailInput(attrs={'class': 'form-control'}),
            'college': forms.Select(attrs={'class': 'form-select'}),
        }

    def save(self, commit=True):
        role = super().save(commit=False)
        role.role = 'مدير_كلية'
        password = self.cleaned_data.get('password_plain')
        if password:
            hashed = bcrypt.hashpw(password.encode('utf-8'), bcrypt.gensalt()).decode('utf-8')
            role.password = hashed
        if commit:
            role.save()
        return role


class LectureScheduleForm(forms.ModelForm):
    class Meta:
        model = LectureSchedule
        fields = ['department', 'period', 'course', 'professor', 'room', 'day_of_week', 'start_time', 'end_time', 'lecture_type']
        labels = {
            'department': 'القسم',
            'period': 'الفترة الأكاديمية',
            'course': 'المادة',
            'professor': 'الأستاذ',
            'room': 'القاعة',
            'day_of_week': 'اليوم',
            'start_time': 'وقت البداية',
            'end_time': 'وقت النهاية',
            'lecture_type': 'نوع المحاضرة',
        }
        widgets = {
            'department': forms.Select(attrs={'class': 'form-select'}),
            'period': forms.Select(attrs={'class': 'form-select'}),
            'course': forms.Select(attrs={'class': 'form-select'}),
            'professor': forms.Select(attrs={'class': 'form-select'}),
            'room': forms.Select(attrs={'class': 'form-select'}),
            'day_of_week': forms.Select(attrs={'class': 'form-select'}),
            'start_time': forms.TimeInput(attrs={'class': 'form-control', 'type': 'time'}),
            'end_time': forms.TimeInput(attrs={'class': 'form-control', 'type': 'time'}),
            'lecture_type': forms.Select(attrs={'class': 'form-select'}),
        }

    def clean(self):
        cleaned_data = super().clean()
        start = cleaned_data.get('start_time')
        end = cleaned_data.get('end_time')
        if start and end and start >= end:
            raise forms.ValidationError('وقت البداية يجب أن يكون قبل وقت النهاية')
        return cleaned_data


class LabScheduleForm(forms.ModelForm):
    class Meta:
        model = LabSchedule
        fields = ['department', 'period', 'course', 'professor', 'hall', 'day_of_week', 'start_time', 'end_time', 'assistant', 'group_number']
        labels = {
            'department': 'القسم',
            'period': 'الفترة الأكاديمية',
            'course': 'المادة',
            'professor': 'الأستاذ',
            'hall': 'المعمل',
            'day_of_week': 'اليوم',
            'start_time': 'وقت البداية',
            'end_time': 'وقت النهاية',
            'assistant': 'المساعد',
            'group_number': 'رقم المجموعة',
        }
        widgets = {
            'department': forms.Select(attrs={'class': 'form-select'}),
            'period': forms.Select(attrs={'class': 'form-select'}),
            'course': forms.Select(attrs={'class': 'form-select'}),
            'professor': forms.Select(attrs={'class': 'form-select'}),
            'hall': forms.Select(attrs={'class': 'form-select'}),
            'day_of_week': forms.Select(attrs={'class': 'form-select'}),
            'start_time': forms.TimeInput(attrs={'class': 'form-control', 'type': 'time'}),
            'end_time': forms.TimeInput(attrs={'class': 'form-control', 'type': 'time'}),
            'assistant': forms.Select(attrs={'class': 'form-select'}),
            'group_number': forms.NumberInput(attrs={'class': 'form-control', 'min': 1}),
        }


class AlternativeTimeForm(forms.ModelForm):
    class Meta:
        model = AlternativeTime
        fields = ['schedule', 'course_name', 'original_day', 'original_time_start', 'original_time_end', 'original_room', 'day', 'time_start', 'time_end', 'room', 'notes']
        labels = {
            'schedule': 'المحاضرة',
            'course_name': 'اسم المادة',
            'original_day': 'اليوم الأصلي',
            'original_time_start': 'وقت البداية الأصلي',
            'original_time_end': 'وقت النهاية الأصلي',
            'original_room': 'القاعة الأصلية',
            'day': 'اليوم الجديد',
            'time_start': 'وقت البداية الجديد',
            'time_end': 'وقت النهاية الجديد',
            'room': 'القاعة الجديدة',
            'notes': 'ملاحظات / سبب التغيير',
        }
        widgets = {
            'schedule': forms.Select(attrs={'class': 'form-select'}),
            'course_name': forms.TextInput(attrs={'class': 'form-control'}),
            'original_day': forms.Select(attrs={'class': 'form-select'}),
            'original_time_start': forms.TimeInput(attrs={'class': 'form-control', 'type': 'time'}),
            'original_time_end': forms.TimeInput(attrs={'class': 'form-control', 'type': 'time'}),
            'original_room': forms.Select(attrs={'class': 'form-select'}),
            'day': forms.Select(attrs={'class': 'form-select'}),
            'time_start': forms.TimeInput(attrs={'class': 'form-control', 'type': 'time'}),
            'time_end': forms.TimeInput(attrs={'class': 'form-control', 'type': 'time'}),
            'room': forms.Select(attrs={'class': 'form-select'}),
            'notes': forms.Textarea(attrs={'class': 'form-control', 'rows': 3}),
        }


class ChangePasswordForm(forms.Form):
    old_password = forms.CharField(
        label='كلمة المرور الحالية',
        widget=forms.PasswordInput(attrs={'class': 'form-control'})
    )
    new_password = forms.CharField(
        label='كلمة المرور الجديدة',
        min_length=6,
        widget=forms.PasswordInput(attrs={'class': 'form-control'})
    )
    confirm_password = forms.CharField(
        label='تأكيد كلمة المرور الجديدة',
        widget=forms.PasswordInput(attrs={'class': 'form-control'})
    )

    def clean(self):
        cleaned_data = super().clean()
        new_pass = cleaned_data.get('new_password')
        confirm = cleaned_data.get('confirm_password')
        if new_pass and confirm and new_pass != confirm:
            raise forms.ValidationError('كلمتا المرور غير متطابقتين')
        return cleaned_data


class ScheduleDeadlineForm(forms.ModelForm):
    class Meta:
        model = ScheduleDeadline
        fields = ['deadline_date']
        labels = {'deadline_date': 'الموعد النهائي'}
        widgets = {
            'deadline_date': forms.DateInput(attrs={'class': 'form-control', 'type': 'date'}),
        }


class EmailSettingsForm(forms.ModelForm):
    class Meta:
        model = EmailSettings
        fields = ['smtp_host', 'smtp_port', 'smtp_username', 'smtp_password', 'from_email', 'from_name', 'is_active']
        labels = {
            'smtp_host': 'خادم SMTP',
            'smtp_port': 'المنفذ',
            'smtp_username': 'اسم المستخدم',
            'smtp_password': 'كلمة المرور',
            'from_email': 'البريد المُرسِل',
            'from_name': 'اسم المُرسِل',
            'is_active': 'تفعيل البريد',
        }
        widgets = {
            'smtp_host': forms.TextInput(attrs={'class': 'form-control'}),
            'smtp_port': forms.NumberInput(attrs={'class': 'form-control'}),
            'smtp_username': forms.TextInput(attrs={'class': 'form-control'}),
            'smtp_password': forms.PasswordInput(attrs={'class': 'form-control'}),
            'from_email': forms.EmailInput(attrs={'class': 'form-control'}),
            'from_name': forms.TextInput(attrs={'class': 'form-control'}),
            'is_active': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
        }
