from django.db import models
from django.contrib.auth.models import AbstractBaseUser, BaseUserManager, PermissionsMixin


class UnifiedUserManager(BaseUserManager):
    def create_user(self, username, password=None, **extra_fields):
        if not username:
            raise ValueError('يجب تحديد اسم المستخدم')
        user = self.model(username=username, **extra_fields)
        user.set_password(password)
        user.save(using=self._db)
        return user

    def create_superuser(self, username, password=None, **extra_fields):
        extra_fields.setdefault('user_type', 'system_manager')
        extra_fields.setdefault('is_staff', True)
        extra_fields.setdefault('is_superuser', True)
        extra_fields.setdefault('full_name', username)
        extra_fields.setdefault('email', f'{username}@tms.local')
        return self.create_user(username, password, **extra_fields)


class UnifiedUser(AbstractBaseUser, PermissionsMixin):
    USER_TYPES = [
        ('student', 'طالب'),
        ('professor', 'أستاذ'),
        ('college_manager', 'مدير كلية'),
        ('department_head', 'رئيس قسم'),
        ('system_manager', 'مدير النظام'),
    ]

    user_type = models.CharField(max_length=20, choices=USER_TYPES, db_index=True)
    user_id = models.IntegerField(default=0)
    username = models.CharField(max_length=50, unique=True)
    full_name = models.CharField(max_length=100)
    email = models.EmailField(max_length=100)
    department = models.ForeignKey('Department', null=True, blank=True, on_delete=models.SET_NULL, db_column='department_id')
    college = models.ForeignKey('College', null=True, blank=True, on_delete=models.SET_NULL, db_column='college_id')
    is_active = models.BooleanField(default=True, db_index=True)
    is_staff = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    objects = UnifiedUserManager()

    USERNAME_FIELD = 'username'
    REQUIRED_FIELDS = ['full_name', 'email', 'user_type']

    class Meta:
        db_table = 'users_with_email'
        verbose_name = 'مستخدم'
        verbose_name_plural = 'المستخدمون'

    def __str__(self):
        return f'{self.full_name} ({self.get_user_type_display()})'

    @property
    def is_system_manager(self):
        return self.user_type == 'system_manager'

    @property
    def is_college_manager(self):
        return self.user_type == 'college_manager'

    @property
    def is_professor(self):
        return self.user_type == 'professor'

    @property
    def is_department_head(self):
        return self.user_type == 'department_head'

    @property
    def is_student(self):
        return self.user_type == 'student'


class University(models.Model):
    name = models.CharField(max_length=255)
    code = models.CharField(max_length=50)
    established_year = models.IntegerField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'universities'
        verbose_name = 'جامعة'
        verbose_name_plural = 'الجامعات'

    def __str__(self):
        return self.name


class Branch(models.Model):
    university = models.ForeignKey(University, on_delete=models.CASCADE, related_name='branches')
    name = models.CharField(max_length=255)
    is_main = models.BooleanField(default=False)

    class Meta:
        db_table = 'branches'
        verbose_name = 'فرع'
        verbose_name_plural = 'الفروع'

    def __str__(self):
        return f'{self.name} - {self.university.name}'


class College(models.Model):
    branch = models.ForeignKey(Branch, on_delete=models.CASCADE, related_name='colleges')
    name = models.CharField(max_length=255)
    code = models.CharField(max_length=50)

    class Meta:
        db_table = 'colleges'
        verbose_name = 'كلية'
        verbose_name_plural = 'الكليات'

    def __str__(self):
        return self.name


class Department(models.Model):
    name = models.CharField(max_length=255)
    program_type = models.CharField(max_length=50)
    academic_program = models.CharField(max_length=255, blank=True)
    total_semesters = models.IntegerField()

    class Meta:
        db_table = 'departments'
        verbose_name = 'قسم'
        verbose_name_plural = 'الأقسام'

    def __str__(self):
        return f'{self.name} ({self.program_type})'


class CollegeDepartment(models.Model):
    college = models.ForeignKey(College, on_delete=models.CASCADE)
    department = models.ForeignKey(Department, on_delete=models.CASCADE)

    class Meta:
        db_table = 'college_departments'
        unique_together = ('college', 'department')
        verbose_name = 'قسم الكلية'
        verbose_name_plural = 'أقسام الكلية'


class AcademicYear(models.Model):
    year_number = models.IntegerField()
    year_name = models.CharField(max_length=50)

    class Meta:
        db_table = 'academicyears'
        ordering = ['year_number']
        verbose_name = 'سنة دراسية'
        verbose_name_plural = 'السنوات الدراسية'

    def __str__(self):
        return self.year_name


class DepartmentAcademicPeriod(models.Model):
    SEMESTER_CHOICES = [('1', 'الفصل الأول'), ('2', 'الفصل الثاني')]
    department = models.ForeignKey(Department, on_delete=models.CASCADE, related_name='periods')
    year = models.ForeignKey(AcademicYear, on_delete=models.CASCADE, db_column='year_id')
    semester_type = models.CharField(max_length=1, choices=SEMESTER_CHOICES)

    class Meta:
        db_table = 'department_academic_periods'
        verbose_name = 'الفترة الأكاديمية'
        verbose_name_plural = 'الفترات الأكاديمية'

    def __str__(self):
        return f'{self.department.name} - {self.year.year_name} - فصل {self.semester_type}'


class DepartmentStudentSettings(models.Model):
    period = models.ForeignKey(DepartmentAcademicPeriod, on_delete=models.CASCADE, related_name='student_settings')
    department = models.ForeignKey(Department, on_delete=models.CASCADE, null=True, blank=True)
    student_count = models.IntegerField(default=0)
    groups_count = models.IntegerField(default=1)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'department_student_settings'
        verbose_name = 'إعدادات طلاب القسم'
        verbose_name_plural = 'إعدادات طلاب الأقسام'


class Specialization(models.Model):
    department = models.ForeignKey(Department, on_delete=models.CASCADE, related_name='specializations')
    period = models.ForeignKey(DepartmentAcademicPeriod, on_delete=models.SET_NULL, null=True, blank=True)
    name = models.CharField(max_length=255)

    class Meta:
        db_table = 'specializations'
        verbose_name = 'تخصص'
        verbose_name_plural = 'التخصصات'

    def __str__(self):
        return self.name


class Course(models.Model):
    period = models.ForeignKey(DepartmentAcademicPeriod, on_delete=models.CASCADE, related_name='courses')
    specialization = models.ForeignKey(Specialization, on_delete=models.SET_NULL, null=True, blank=True)
    course_code = models.CharField(max_length=20)
    course_name = models.CharField(max_length=255)
    lecture_hours = models.IntegerField(default=0)
    exercise_hours = models.IntegerField(default=0)
    lab_hours = models.IntegerField(default=0)
    total_lectures = models.IntegerField(default=0)
    is_shared_across_departments = models.BooleanField(default=False)
    is_shared_across_colleges = models.BooleanField(default=False)

    class Meta:
        db_table = 'courses'
        verbose_name = 'مادة'
        verbose_name_plural = 'المواد'

    def __str__(self):
        return f'{self.course_name} ({self.course_code})'


class Room(models.Model):
    name = models.CharField(max_length=255)
    capacity = models.IntegerField()
    code = models.CharField(max_length=50)
    college = models.ForeignKey(College, on_delete=models.CASCADE, related_name='owned_rooms')

    class Meta:
        db_table = 'rooms'
        verbose_name = 'قاعة دراسية'
        verbose_name_plural = 'القاعات الدراسية'

    def __str__(self):
        return f'{self.name} ({self.code})'


class Hall(models.Model):
    college = models.ForeignKey(College, on_delete=models.CASCADE, related_name='owned_halls')
    name = models.CharField(max_length=100)
    code = models.CharField(max_length=50)
    capacity = models.IntegerField()

    class Meta:
        db_table = 'halls'
        verbose_name = 'معمل'
        verbose_name_plural = 'المعامل'

    def __str__(self):
        return f'{self.name} ({self.code})'


class CollegeRoom(models.Model):
    RELATION_TYPES = [('owner', 'مالك'), ('shared', 'مشارك')]
    college = models.ForeignKey(College, on_delete=models.CASCADE)
    room = models.ForeignKey(Room, on_delete=models.CASCADE)
    relation_type = models.CharField(max_length=10, choices=RELATION_TYPES, default='owner')
    added_by = models.IntegerField(null=True, blank=True)
    added_at = models.DateTimeField(auto_now_add=True)
    is_active = models.BooleanField(default=True)

    class Meta:
        db_table = 'college_rooms'
        unique_together = ('college', 'room')


class CollegeHall(models.Model):
    RELATION_TYPES = [('owner', 'مالك'), ('shared', 'مشارك')]
    college = models.ForeignKey(College, on_delete=models.CASCADE)
    hall = models.ForeignKey(Hall, on_delete=models.CASCADE)
    relation_type = models.CharField(max_length=10, choices=RELATION_TYPES, default='owner')
    added_by = models.IntegerField(null=True, blank=True)
    added_at = models.DateTimeField(auto_now_add=True)
    is_active = models.BooleanField(default=True)

    class Meta:
        db_table = 'college_halls'
        unique_together = ('college', 'hall')


class Professor(models.Model):
    POSITIONS = [
        ('أستاذ', 'أستاذ'),
        ('أستاذ مشارك', 'أستاذ مشارك'),
        ('محاضر', 'محاضر'),
        ('مساعد تدريس', 'مساعد تدريس'),
        ('دكتور', 'دكتور'),
        ('بروفيسور', 'بروفيسور'),
    ]
    name = models.CharField(max_length=255)
    username = models.CharField(max_length=100, unique=True)
    password = models.CharField(max_length=255)
    email = models.EmailField(max_length=255)
    position = models.CharField(max_length=50, choices=POSITIONS)
    college = models.ForeignKey(College, on_delete=models.CASCADE, db_column='college_id')

    class Meta:
        db_table = 'users'
        verbose_name = 'أستاذ'
        verbose_name_plural = 'الأساتذة'

    def __str__(self):
        return f'{self.name} - {self.position}'


class ProfessorCollegeRelation(models.Model):
    RELATION_TYPES = [('primary', 'أساسي'), ('collaboration', 'تعاون')]
    professor = models.ForeignKey(Professor, on_delete=models.CASCADE, related_name='college_relations')
    college = models.ForeignKey(College, on_delete=models.CASCADE)
    relation_type = models.CharField(max_length=20, choices=RELATION_TYPES, default='collaboration')
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'professor_college_relations'


class ExternalCollaborator(models.Model):
    professor = models.OneToOneField(Professor, on_delete=models.CASCADE, related_name='external_info', db_column='user_id')
    external_university = models.CharField(max_length=255)
    external_college = models.CharField(max_length=255)
    external_department = models.CharField(max_length=255, null=True, blank=True)
    specialization = models.CharField(max_length=255, null=True, blank=True)
    academic_degree = models.CharField(max_length=100, null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'external_collaborators'


class Student(models.Model):
    name = models.CharField(max_length=255, null=True, blank=True)
    username = models.CharField(max_length=100, null=True, blank=True)
    password = models.CharField(max_length=255, null=True, blank=True)
    email = models.EmailField(max_length=255, null=True, blank=True)
    department = models.ForeignKey(Department, on_delete=models.SET_NULL, null=True, blank=True)
    period = models.ForeignKey(DepartmentAcademicPeriod, on_delete=models.CASCADE)
    specialization_id = models.IntegerField(default=0)

    class Meta:
        db_table = 'students'
        verbose_name = 'طالب'
        verbose_name_plural = 'الطلاب'

    def __str__(self):
        return self.name or self.username or ''


class Role(models.Model):
    ROLES = [
        ('مدير_نظام', 'مدير النظام'),
        ('مدير_كلية', 'مدير الكلية'),
        ('مساعد_مدير', 'مساعد المدير'),
    ]
    college = models.ForeignKey(College, on_delete=models.SET_NULL, null=True, blank=True)
    username = models.CharField(max_length=50, unique=True)
    password = models.CharField(max_length=255)
    email = models.EmailField(max_length=255, null=True, blank=True)
    full_name = models.CharField(max_length=255)
    role = models.CharField(max_length=20, choices=ROLES)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'roles'
        verbose_name = 'صلاحية'
        verbose_name_plural = 'الصلاحيات'

    def __str__(self):
        return f'{self.full_name} ({self.role})'


class LectureSchedule(models.Model):
    DAYS = [
        ('Saturday', 'السبت'),
        ('Sunday', 'الأحد'),
        ('Monday', 'الاثنين'),
        ('Tuesday', 'الثلاثاء'),
        ('Wednesday', 'الأربعاء'),
        ('Thursday', 'الخميس'),
    ]
    LECTURE_TYPES = [('lecture', 'محاضرة'), ('exercise', 'تمرين')]

    department = models.ForeignKey(Department, on_delete=models.CASCADE)
    period = models.ForeignKey(DepartmentAcademicPeriod, on_delete=models.CASCADE)
    course = models.ForeignKey(Course, on_delete=models.CASCADE)
    professor = models.ForeignKey(Professor, on_delete=models.CASCADE, db_column='user_id')
    room = models.ForeignKey(Room, on_delete=models.CASCADE)
    day_of_week = models.CharField(max_length=15, choices=DAYS, db_index=True)
    start_time = models.TimeField()
    end_time = models.TimeField()
    lecture_type = models.CharField(max_length=10, choices=LECTURE_TYPES, default='lecture')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'lecture_schedule'
        indexes = [
            models.Index(fields=['day_of_week', 'start_time', 'end_time'], name='lec_day_time_idx'),
            models.Index(fields=['professor', 'day_of_week'], name='lec_prof_day_idx'),
            models.Index(fields=['department', 'period'], name='lec_dept_period_idx'),
        ]
        verbose_name = 'جدول محاضرة'
        verbose_name_plural = 'جداول المحاضرات'

    def __str__(self):
        return f'{self.course.course_name} - {self.get_day_of_week_display()} {self.start_time}'


class LabSchedule(models.Model):
    DAYS = [
        ('Saturday', 'السبت'),
        ('Sunday', 'الأحد'),
        ('Monday', 'الاثنين'),
        ('Tuesday', 'الثلاثاء'),
        ('Wednesday', 'الأربعاء'),
        ('Thursday', 'الخميس'),
    ]

    department = models.ForeignKey(Department, on_delete=models.CASCADE)
    period = models.ForeignKey(DepartmentAcademicPeriod, on_delete=models.CASCADE)
    course = models.ForeignKey(Course, on_delete=models.CASCADE)
    professor = models.ForeignKey(Professor, on_delete=models.CASCADE, db_column='user_id', related_name='lab_schedules')
    hall = models.ForeignKey(Hall, on_delete=models.CASCADE)
    day_of_week = models.CharField(max_length=15, choices=DAYS, db_index=True)
    start_time = models.TimeField()
    end_time = models.TimeField()
    assistant = models.ForeignKey(Professor, on_delete=models.SET_NULL, null=True, blank=True, related_name='lab_assistant_schedules', db_column='assistant_id')
    group_number = models.IntegerField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'lab_schedule'
        indexes = [
            models.Index(fields=['day_of_week', 'start_time', 'end_time'], name='lab_day_time_idx'),
            models.Index(fields=['professor', 'day_of_week'], name='lab_prof_day_idx'),
            models.Index(fields=['department', 'period'], name='lab_dept_period_idx'),
        ]
        verbose_name = 'جدول معمل'
        verbose_name_plural = 'جداول المعامل'


class AlternativeTime(models.Model):
    STATUS_CHOICES = [('pending', 'قيد الانتظار'), ('approved', 'موافق'), ('rejected', 'مرفوض')]
    DAYS = [
        ('Saturday', 'السبت'), ('Sunday', 'الأحد'), ('Monday', 'الاثنين'),
        ('Tuesday', 'الثلاثاء'), ('Wednesday', 'الأربعاء'), ('Thursday', 'الخميس'),
    ]

    professor = models.ForeignKey(Professor, on_delete=models.CASCADE, db_column='professor_id')
    schedule = models.ForeignKey(LectureSchedule, on_delete=models.SET_NULL, null=True, blank=True)
    course_name = models.CharField(max_length=255, null=True, blank=True)
    original_day = models.CharField(max_length=20, null=True, blank=True, choices=DAYS)
    original_time_start = models.TimeField(null=True, blank=True)
    original_time_end = models.TimeField(null=True, blank=True)
    original_room = models.ForeignKey(Room, on_delete=models.SET_NULL, null=True, blank=True, related_name='original_requests', db_column='original_room_id')
    day = models.CharField(max_length=20, choices=DAYS)
    time_start = models.TimeField(null=True, blank=True)
    time_end = models.TimeField(null=True, blank=True)
    room = models.ForeignKey(Room, on_delete=models.SET_NULL, null=True, blank=True, related_name='alternative_requests', db_column='room_id')
    notes = models.TextField(null=True, blank=True)
    admin_notes = models.TextField(null=True, blank=True)
    status = models.CharField(max_length=10, choices=STATUS_CHOICES, default='pending', db_index=True)
    is_expired = models.BooleanField(default=False, db_index=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'alternative_times'
        verbose_name = 'طلب تغيير موعد'
        verbose_name_plural = 'طلبات تغيير المواعيد'
        ordering = ['-created_at']


class TaughtLecture(models.Model):
    schedule = models.ForeignKey(LectureSchedule, on_delete=models.CASCADE)
    professor = models.ForeignKey(Professor, on_delete=models.CASCADE, db_column='professor_id')
    taught_date = models.DateField()
    created_at = models.DateTimeField(auto_now_add=True)
    notification_sent = models.BooleanField(default=False)

    class Meta:
        db_table = 'taught_lectures'
        verbose_name = 'محاضرة مُدَرَّسة'
        verbose_name_plural = 'المحاضرات المُدَرَّسة'


class LectureChangeNotification(models.Model):
    TYPES = [
        ('request_approval', 'طلب موافقة'),
        ('approval_notification', 'إشعار موافقة'),
        ('rejection_notification', 'إشعار رفض'),
    ]
    alternative_time = models.ForeignKey(AlternativeTime, on_delete=models.CASCADE)
    notification_type = models.CharField(max_length=30, choices=TYPES)
    sent_to_manager = models.BooleanField(default=False)
    sent_to_professor = models.BooleanField(default=False)
    sent_to_students = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'lecture_change_notifications'


class Notification(models.Model):
    STATUS_CHOICES = [('pending', 'قيد الانتظار'), ('sent', 'مُرسَل'), ('failed', 'فشل')]
    recipient = models.ForeignKey(UnifiedUser, on_delete=models.CASCADE, null=True, blank=True, db_column='recipient_id')
    recipient_type = models.CharField(max_length=20, null=True, blank=True)
    subject = models.CharField(max_length=255)
    message = models.TextField()
    status = models.CharField(max_length=10, choices=STATUS_CHOICES, default='pending')
    is_read = models.BooleanField(default=False, db_index=True)
    sent_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'notifications'
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['recipient', 'is_read'], name='notif_recipient_read_idx'),
            models.Index(fields=['recipient', '-created_at'], name='notif_recipient_date_idx'),
        ]
        verbose_name = 'إشعار'
        verbose_name_plural = 'الإشعارات'


class Semester(models.Model):
    year = models.ForeignKey(AcademicYear, on_delete=models.CASCADE, db_column='year_id')
    semester_number = models.IntegerField()
    semester_name = models.CharField(max_length=50)
    start_date = models.DateField(null=True, blank=True)
    end_date = models.DateField(null=True, blank=True)

    class Meta:
        db_table = 'semesters'
        verbose_name = 'فصل دراسي'
        verbose_name_plural = 'الفصول الدراسية'

    def __str__(self):
        return self.semester_name


class ScheduleDeadline(models.Model):
    deadline_date = models.DateField()
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'schedule_deadlines'
        verbose_name = 'موعد نهائي'
        verbose_name_plural = 'المواعيد النهائية'


class EmailSettings(models.Model):
    smtp_host = models.CharField(max_length=255)
    smtp_port = models.IntegerField(default=587)
    smtp_username = models.CharField(max_length=255)
    smtp_password = models.CharField(max_length=255)
    from_email = models.EmailField(max_length=255)
    from_name = models.CharField(max_length=255)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'email_settings'
        verbose_name = 'إعدادات البريد'
        verbose_name_plural = 'إعدادات البريد'


class EmailTemplate(models.Model):
    template_name = models.CharField(max_length=100, unique=True)
    subject = models.CharField(max_length=255)
    body_html = models.TextField()
    body_text = models.TextField()
    variables = models.TextField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'email_templates'
        verbose_name = 'قالب بريد'
        verbose_name_plural = 'قوالب البريد'

    def __str__(self):
        return self.template_name


class PasswordReset(models.Model):
    email = models.EmailField(max_length=255)
    token = models.CharField(max_length=255)
    user_type = models.CharField(max_length=20)
    created_at = models.DateTimeField(auto_now_add=True)
    expires_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        db_table = 'password_resets'


class ScheduleChangeLog(models.Model):
    SCHEDULE_TYPES = [('lecture', 'محاضرة'), ('lab', 'معمل')]
    ACTIONS = [('add', 'إضافة'), ('edit', 'تعديل'), ('delete', 'حذف')]

    schedule_type = models.CharField(max_length=10, choices=SCHEDULE_TYPES)
    schedule_id = models.IntegerField()
    action = models.CharField(max_length=10, choices=ACTIONS)
    changed_by = models.ForeignKey(
        UnifiedUser, on_delete=models.SET_NULL, null=True, blank=True,
        related_name='change_logs', db_column='changed_by_id'
    )
    changed_at = models.DateTimeField(auto_now_add=True)
    old_data = models.JSONField(null=True, blank=True)
    new_data = models.JSONField(null=True, blank=True)
    change_reason = models.TextField(null=True, blank=True)
    department_name = models.CharField(max_length=255, null=True, blank=True)
    course_name = models.CharField(max_length=255, null=True, blank=True)

    class Meta:
        db_table = 'schedule_change_log'
        ordering = ['-changed_at']
        verbose_name = 'سجل التغييرات'
        verbose_name_plural = 'سجلات التغييرات'

    def __str__(self):
        return f'{self.get_action_display()} - {self.course_name} - {self.changed_at}'
