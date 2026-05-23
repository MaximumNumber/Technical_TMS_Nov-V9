"""
Comprehensive seed command for TMS test data.
Run: python manage.py seed_data
"""
from django.core.management.base import BaseCommand
from django.db import transaction
from datetime import date, time, timedelta
import bcrypt


def make_hash(password: str) -> str:
    return bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode()


class Command(BaseCommand):
    help = 'Seed the database with diverse test data for all features'

    def handle(self, *args, **options):
        self.stdout.write(self.style.WARNING('⏳  Seeding test data...'))
        with transaction.atomic():
            self._seed_all()
        self.stdout.write(self.style.SUCCESS('✅  Seeding complete!'))
        self._print_credentials()

    # ─────────────────────────────────────────────
    def _seed_all(self):
        from timetable.models import (
            University, Branch, College, Department, CollegeDepartment,
            AcademicYear, DepartmentAcademicPeriod, DepartmentStudentSettings,
            Specialization, Course, Room, Hall, CollegeRoom, CollegeHall,
            Professor, ProfessorCollegeRelation, Student, Role,
            LectureSchedule, LabSchedule, AlternativeTime, TaughtLecture,
            Notification, ScheduleDeadline, ScheduleChangeLog, UnifiedUser,
        )

        # ── 1. University & Branches ─────────────────
        uni, _ = University.objects.get_or_create(
            name='جامعة السودان للعلوم والتكنولوجيا',
            defaults={'code': 'SUST', 'established_year': 1975}
        )
        branch_main, _ = Branch.objects.get_or_create(
            university=uni, name='الفرع الرئيسي - الخرطوم', defaults={'is_main': True}
        )
        branch_north, _ = Branch.objects.get_or_create(
            university=uni, name='فرع بحري', defaults={'is_main': False}
        )

        # ── 2. Colleges ──────────────────────────────
        col_eng, _ = College.objects.get_or_create(
            name='كلية الهندسة', defaults={'branch': branch_main, 'code': 'ENG'}
        )
        col_cs, _ = College.objects.get_or_create(
            name='كلية علوم الحاسوب والتقنية', defaults={'branch': branch_main, 'code': 'CS'}
        )
        col_sci, _ = College.objects.get_or_create(
            name='كلية العلوم', defaults={'branch': branch_north, 'code': 'SCI'}
        )
        colleges = [col_eng, col_cs, col_sci]

        # ── 3. Departments ───────────────────────────
        dept_civil, _ = Department.objects.get_or_create(
            name='قسم الهندسة المدنية',
            defaults={'program_type': 'بكالوريوس', 'academic_program': 'هندسة مدنية', 'total_semesters': 8}
        )
        dept_elec, _ = Department.objects.get_or_create(
            name='قسم الهندسة الكهربائية',
            defaults={'program_type': 'بكالوريوس', 'academic_program': 'هندسة كهربائية', 'total_semesters': 8}
        )
        dept_cs, _ = Department.objects.get_or_create(
            name='قسم علوم الحاسوب',
            defaults={'program_type': 'بكالوريوس', 'academic_program': 'علوم حاسوب', 'total_semesters': 8}
        )
        dept_it, _ = Department.objects.get_or_create(
            name='قسم تقنية المعلومات',
            defaults={'program_type': 'بكالوريوس', 'academic_program': 'تقنية معلومات', 'total_semesters': 8}
        )
        dept_math, _ = Department.objects.get_or_create(
            name='قسم الرياضيات',
            defaults={'program_type': 'بكالوريوس', 'academic_program': 'رياضيات', 'total_semesters': 8}
        )
        dept_phys, _ = Department.objects.get_or_create(
            name='قسم الفيزياء',
            defaults={'program_type': 'بكالوريوس', 'academic_program': 'فيزياء', 'total_semesters': 8}
        )

        # Assign departments to colleges
        for dept in [dept_civil, dept_elec]:
            CollegeDepartment.objects.get_or_create(college=col_eng, department=dept)
        for dept in [dept_cs, dept_it]:
            CollegeDepartment.objects.get_or_create(college=col_cs, department=dept)
        for dept in [dept_math, dept_phys]:
            CollegeDepartment.objects.get_or_create(college=col_sci, department=dept)

        all_depts = [dept_civil, dept_elec, dept_cs, dept_it, dept_math, dept_phys]

        # ── 4. Academic Years ────────────────────────
        year_names = ['السنة الأولى', 'السنة الثانية', 'السنة الثالثة', 'السنة الرابعة']
        years = []
        for i, yn in enumerate(year_names, 1):
            y, _ = AcademicYear.objects.get_or_create(year_number=i, defaults={'year_name': yn})
            years.append(y)

        # ── 5. Rooms & Halls ─────────────────────────
        rooms = []
        room_defs = [
            (col_eng, 'قاعة أ-101', 'A101', 120),
            (col_eng, 'قاعة أ-102', 'A102', 80),
            (col_eng, 'قاعة ب-201', 'B201', 60),
            (col_cs,  'قاعة ت-101', 'C101', 100),
            (col_cs,  'قاعة ت-102', 'C102', 80),
            (col_sci, 'قاعة د-101', 'D101', 90),
            (col_sci, 'قاعة د-102', 'D102', 60),
        ]
        for col, name, code, cap in room_defs:
            r, _ = Room.objects.get_or_create(code=code, defaults={'name': name, 'capacity': cap, 'college': col})
            CollegeRoom.objects.get_or_create(college=col, room=r, defaults={'relation_type': 'owner'})
            rooms.append(r)

        halls = []
        hall_defs = [
            (col_eng, 'معمل الحاسوب 1', 'COMP-LAB-1', 40),
            (col_eng, 'معمل الفيزياء',  'PHYS-LAB-1', 30),
            (col_cs,  'معمل البرمجة 1', 'PROG-LAB-1', 35),
            (col_cs,  'معمل الشبكات',   'NET-LAB-1',  25),
            (col_sci, 'معمل الكيمياء',  'CHEM-LAB-1', 28),
            (col_sci, 'معمل الأحياء',   'BIO-LAB-1',  28),
        ]
        for col, name, code, cap in hall_defs:
            h, _ = Hall.objects.get_or_create(code=code, defaults={'name': name, 'capacity': cap, 'college': col})
            CollegeHall.objects.get_or_create(college=col, hall=h, defaults={'relation_type': 'owner'})
            halls.append(h)

        # ── 6. Professors ────────────────────────────
        prof_data = [
            # (name, username, email, position, college)
            ('د. أحمد محمد علي',      'prof_ahmed',   'ahmed@sust.edu',   'دكتور',          col_eng),
            ('أ.د. سارة عبدالله',     'prof_sara',    'sara@sust.edu',    'بروفيسور',       col_eng),
            ('م. خالد إبراهيم',       'prof_khalid',  'khalid@sust.edu',  'محاضر',          col_eng),
            ('د. فاطمة النور',         'prof_fatima',  'fatima@sust.edu',  'دكتور',          col_cs),
            ('أ.د. عمر حسن',          'prof_omar',    'omar@sust.edu',    'أستاذ',          col_cs),
            ('م. رنا الطيب',           'prof_rana',    'rana@sust.edu',    'مساعد تدريس',    col_cs),
            ('د. يوسف عيسى',          'prof_yousuf',  'yousuf@sust.edu',  'دكتور',          col_sci),
            ('أ. نجلاء مصطفى',        'prof_najla',   'najla@sust.edu',   'أستاذ مشارك',   col_sci),
            ('م. بكر الأمين',          'prof_bakr',    'bakr@sust.edu',    'مساعد تدريس',    col_sci),
            ('د. هدى عثمان',          'prof_huda',    'huda@sust.edu',    'محاضر',          col_eng),
        ]
        prof_password = 'prof123'
        prof_hash = make_hash(prof_password)
        professors = []
        for name, uname, email, pos, col in prof_data:
            p, created = Professor.objects.get_or_create(
                username=uname,
                defaults={'name': name, 'email': email, 'position': pos, 'college': col, 'password': prof_hash}
            )
            professors.append(p)
            if created:
                ProfessorCollegeRelation.objects.get_or_create(
                    professor=p, college=col, defaults={'relation_type': 'primary'}
                )
                UnifiedUser.objects.get_or_create(
                    username=uname,
                    defaults={
                        'user_type': 'professor', 'user_id': p.id,
                        'full_name': name, 'email': email,
                        'college': col, 'password': prof_hash, 'is_active': True,
                    }
                )
            else:
                UnifiedUser.objects.get_or_create(
                    username=uname,
                    defaults={
                        'user_type': 'professor', 'user_id': p.id,
                        'full_name': name, 'email': email,
                        'college': col, 'password': prof_hash, 'is_active': True,
                    }
                )

        (p_ahmed, p_sara, p_khalid, p_fatima, p_omar,
         p_rana, p_yousuf, p_najla, p_bakr, p_huda) = professors

        # ── 7. College Managers ──────────────────────
        mgr_password = 'mgr123'
        mgr_hash = make_hash(mgr_password)
        mgr_data = [
            ('mgr_eng', 'مدير_كلية', col_eng, 'م. عصام الدين', 'mgr_eng@sust.edu'),
            ('mgr_cs',  'مدير_كلية', col_cs,  'أ. منى حسين',   'mgr_cs@sust.edu'),
            ('mgr_sci', 'مدير_كلية', col_sci, 'د. ماجد سليمان', 'mgr_sci@sust.edu'),
        ]
        for uname, role_name, col, full_name, email in mgr_data:
            role, created = Role.objects.get_or_create(
                username=uname,
                defaults={
                    'college': col, 'full_name': full_name,
                    'email': email, 'role': role_name, 'password': mgr_hash,
                }
            )
            UnifiedUser.objects.get_or_create(
                username=uname,
                defaults={
                    'user_type': 'college_manager', 'user_id': role.id,
                    'full_name': full_name, 'email': email,
                    'college': col, 'password': mgr_hash, 'is_active': True,
                }
            )

        # ── 7b. Department Heads ─────────────────────
        dh_password = 'dh123'
        dh_hash = make_hash(dh_password)
        dh_data = [
            ('dh_cs',   col_cs,  dept_cs,   'أ. هشام النور',   'dh_cs@sust.edu'),
            ('dh_it',   col_cs,  dept_it,   'أ. سلمى بشير',    'dh_it@sust.edu'),
            ('dh_elec', col_eng, dept_elec, 'م. طارق عثمان',   'dh_elec@sust.edu'),
        ]
        for uname, col, dept, full_name, email in dh_data:
            UnifiedUser.objects.get_or_create(
                username=uname,
                defaults={
                    'user_type': 'department_head', 'user_id': 0,
                    'full_name': full_name, 'email': email,
                    'college': col, 'department': dept,
                    'password': dh_hash, 'is_active': True,
                }
            )

        # ── 8. Academic Periods ──────────────────────
        periods = {}
        for dept in all_depts:
            periods[dept.id] = {}
            for yr in years:
                periods[dept.id][yr.id] = {}
                for sem in ['1', '2']:
                    p, _ = DepartmentAcademicPeriod.objects.get_or_create(
                        department=dept, year=yr, semester_type=sem
                    )
                    periods[dept.id][yr.id][sem] = p
                    DepartmentStudentSettings.objects.get_or_create(
                        period=p, department=dept,
                        defaults={'student_count': 60 + (yr.year_number * 5), 'groups_count': 3}
                    )

        # ── 9. Specializations ───────────────────────
        specs = {}
        spec_defs = {
            dept_cs.id: [('تخصص الذكاء الاصطناعي', years[2]), ('تخصص قواعد البيانات', years[2])],
            dept_it.id: [('تخصص أمن المعلومات', years[2]), ('تخصص الشبكات', years[2])],
            dept_elec.id: [('تخصص القوى', years[2]), ('تخصص الاتصالات', years[2])],
        }
        for dept_id, defs in spec_defs.items():
            specs[dept_id] = []
            for sname, yr in defs:
                p = periods[dept_id][yr.id]['1']
                s, _ = Specialization.objects.get_or_create(
                    department_id=dept_id, name=sname, defaults={'period': p}
                )
                specs[dept_id].append(s)

        # ── 10. Courses ──────────────────────────────
        # We'll create courses for year 1 sem 1 and year 2 sem 1 for each dept
        course_templates = {
            dept_civil.id: [
                ('CIVIL101', 'الرياضيات الهندسية', 3, 1, 2),
                ('CIVIL102', 'ميكانيكا الموائع',   3, 0, 3),
                ('CIVIL103', 'مقاومة المواد',       3, 1, 0),
                ('CIVIL201', 'تصميم الخرسانة',     3, 0, 2),
                ('CIVIL202', 'الجيوتقنية',          3, 1, 2),
            ],
            dept_elec.id: [
                ('ELEC101', 'دوائر كهربائية 1',    3, 1, 3),
                ('ELEC102', 'إلكترونيات أساسية',   3, 0, 3),
                ('ELEC103', 'رياضيات هندسية',      3, 1, 0),
                ('ELEC201', 'دوائر كهربائية 2',    3, 1, 3),
                ('ELEC202', 'نظرية التحكم',         3, 0, 2),
            ],
            dept_cs.id: [
                ('CS101', 'برمجة 1',               3, 0, 3),
                ('CS102', 'هياكل البيانات',         3, 1, 2),
                ('CS103', 'الرياضيات المتقطعة',    3, 1, 0),
                ('CS201', 'خوارزميات',              3, 1, 2),
                ('CS202', 'قواعد البيانات',         3, 0, 3),
            ],
            dept_it.id: [
                ('IT101', 'مقدمة في تقنية المعلومات', 3, 0, 2),
                ('IT102', 'برمجة ويب',              3, 0, 3),
                ('IT103', 'شبكات الحاسوب',          3, 1, 2),
                ('IT201', 'أمن المعلومات',          3, 1, 2),
                ('IT202', 'إدارة النظم',            3, 0, 2),
            ],
            dept_math.id: [
                ('MATH101', 'حساب التفاضل والتكامل 1', 4, 1, 0),
                ('MATH102', 'الجبر الخطي',          3, 1, 0),
                ('MATH103', 'الإحصاء والاحتمالات', 3, 1, 0),
                ('MATH201', 'حساب التفاضل والتكامل 2', 4, 1, 0),
                ('MATH202', 'المعادلات التفاضلية',  3, 1, 0),
            ],
            dept_phys.id: [
                ('PHYS101', 'فيزياء عامة 1',        3, 1, 2),
                ('PHYS102', 'فيزياء كهرومغناطيسية', 3, 0, 2),
                ('PHYS103', 'ميكانيكا',             3, 1, 0),
                ('PHYS201', 'فيزياء عامة 2',        3, 1, 2),
                ('PHYS202', 'بصريات',               3, 0, 2),
            ],
        }

        courses = {}
        for dept_id, cdefs in course_templates.items():
            courses[dept_id] = {}
            yr1_s1 = periods[dept_id][years[0].id]['1']
            yr1_s2 = periods[dept_id][years[0].id]['2']
            yr2_s1 = periods[dept_id][years[1].id]['1']
            # first 3 courses → year1 sem1; last 2 → year2 sem1
            for i, (code, name, lh, eh, labh) in enumerate(cdefs):
                if i < 3:
                    period = yr1_s1
                else:
                    period = yr2_s1
                c, _ = Course.objects.get_or_create(
                    course_code=code,
                    defaults={
                        'period': period, 'course_name': name,
                        'lecture_hours': lh, 'exercise_hours': eh, 'lab_hours': labh,
                        'total_lectures': lh * 14,
                    }
                )
                courses[dept_id][code] = c

        # ── 11. Students ─────────────────────────────
        std_password = 'std123'
        std_hash = make_hash(std_password)
        student_defs = [
            # (name, username, email, dept, year_idx, sem)
            ('علي عمر محمد',    'std_ali',    'ali@student.sust.edu',    dept_cs,   0, '1'),
            ('مريم خالد',       'std_maryam', 'maryam@student.sust.edu', dept_cs,   0, '1'),
            ('إبراهيم سعد',     'std_ibrahim','ibrahim@student.sust.edu',dept_it,   0, '1'),
            ('سلمى حسن',        'std_salma',  'salma@student.sust.edu',  dept_it,   1, '1'),
            ('أسامة بشير',      'std_osama',  'osama@student.sust.edu',  dept_civil,0, '1'),
            ('منال أحمد',       'std_manal',  'manal@student.sust.edu',  dept_elec, 0, '1'),
            ('كريم عبدالرحمن', 'std_karim',  'karim@student.sust.edu',  dept_math, 1, '2'),
            ('نورا الفاضل',     'std_nora',   'nora@student.sust.edu',   dept_phys, 0, '1'),
        ]
        students = []
        for sname, uname, email, dept, yr_idx, sem in student_defs:
            period = periods[dept.id][years[yr_idx].id][sem]
            std, created = Student.objects.get_or_create(
                username=uname,
                defaults={'name': sname, 'email': email, 'department': dept, 'period': period, 'password': std_hash}
            )
            students.append(std)
            if created:
                UnifiedUser.objects.get_or_create(
                    username=uname,
                    defaults={
                        'user_type': 'student', 'user_id': std.id,
                        'full_name': sname, 'email': email,
                        'department': dept, 'password': std_hash, 'is_active': True,
                    }
                )

        # ── 12. Lecture Schedules ────────────────────
        # Helper: (dept, period, course_code, professor, room, day, start, end, type)
        DAYS = ['Saturday', 'Sunday', 'Monday', 'Tuesday', 'Wednesday', 'Thursday']

        def make_time(h, m=0):
            return time(h, m)

        # Rooms by college
        r_eng = [r for r in rooms if r.college == col_eng]
        r_cs  = [r for r in rooms if r.college == col_cs]
        r_sci = [r for r in rooms if r.college == col_sci]

        lecture_defs = [
            # CS dept, Year1 Sem1
            (dept_cs, periods[dept_cs.id][years[0].id]['1'], 'CS101', p_fatima, r_cs[0], 'Saturday',  8, 0,  10, 0, 'lecture'),
            (dept_cs, periods[dept_cs.id][years[0].id]['1'], 'CS101', p_fatima, r_cs[0], 'Tuesday',   8, 0,  10, 0, 'lecture'),
            (dept_cs, periods[dept_cs.id][years[0].id]['1'], 'CS102', p_omar,   r_cs[1], 'Sunday',   10, 0,  12, 0, 'lecture'),
            (dept_cs, periods[dept_cs.id][years[0].id]['1'], 'CS102', p_omar,   r_cs[1], 'Wednesday',10, 0,  12, 0, 'lecture'),
            (dept_cs, periods[dept_cs.id][years[0].id]['1'], 'CS103', p_rana,   r_cs[0], 'Monday',   12, 0,  14, 0, 'lecture'),
            (dept_cs, periods[dept_cs.id][years[0].id]['1'], 'CS103', p_rana,   r_cs[0], 'Thursday', 12, 0,  14, 0, 'lecture'),

            # CS dept, Year2 Sem1
            (dept_cs, periods[dept_cs.id][years[1].id]['1'], 'CS201', p_fatima, r_cs[0], 'Saturday',  10, 0, 12, 0, 'lecture'),
            (dept_cs, periods[dept_cs.id][years[1].id]['1'], 'CS201', p_fatima, r_cs[0], 'Wednesday', 10, 0, 12, 0, 'lecture'),
            (dept_cs, periods[dept_cs.id][years[1].id]['1'], 'CS202', p_omar,   r_cs[1], 'Sunday',    8, 0,  10, 0, 'lecture'),
            (dept_cs, periods[dept_cs.id][years[1].id]['1'], 'CS202', p_omar,   r_cs[1], 'Thursday',  8, 0,  10, 0, 'lecture'),

            # IT dept, Year1 Sem1
            (dept_it, periods[dept_it.id][years[0].id]['1'], 'IT101', p_rana,   r_cs[0], 'Saturday',  14, 0, 16, 0, 'lecture'),
            (dept_it, periods[dept_it.id][years[0].id]['1'], 'IT101', p_rana,   r_cs[0], 'Tuesday',   14, 0, 16, 0, 'lecture'),
            (dept_it, periods[dept_it.id][years[0].id]['1'], 'IT102', p_fatima, r_cs[1], 'Sunday',    12, 0, 14, 0, 'lecture'),
            (dept_it, periods[dept_it.id][years[0].id]['1'], 'IT103', p_omar,   r_cs[0], 'Monday',    8,  0, 10, 0, 'lecture'),

            # Civil dept, Year1 Sem1
            (dept_civil, periods[dept_civil.id][years[0].id]['1'], 'CIVIL101', p_ahmed,  r_eng[0], 'Saturday',  8, 0,  10, 0, 'lecture'),
            (dept_civil, periods[dept_civil.id][years[0].id]['1'], 'CIVIL101', p_ahmed,  r_eng[0], 'Monday',    8, 0,  10, 0, 'lecture'),
            (dept_civil, periods[dept_civil.id][years[0].id]['1'], 'CIVIL102', p_sara,   r_eng[1], 'Sunday',    10, 0, 12, 0, 'lecture'),
            (dept_civil, periods[dept_civil.id][years[0].id]['1'], 'CIVIL102', p_sara,   r_eng[1], 'Wednesday', 10, 0, 12, 0, 'lecture'),
            (dept_civil, periods[dept_civil.id][years[0].id]['1'], 'CIVIL103', p_khalid, r_eng[2], 'Tuesday',   12, 0, 14, 0, 'lecture'),
            (dept_civil, periods[dept_civil.id][years[0].id]['1'], 'CIVIL103', p_khalid, r_eng[2], 'Thursday',  12, 0, 14, 0, 'lecture'),

            # Elec dept, Year1 Sem1
            (dept_elec, periods[dept_elec.id][years[0].id]['1'], 'ELEC101', p_huda,   r_eng[0], 'Saturday',  10, 0, 12, 0, 'lecture'),
            (dept_elec, periods[dept_elec.id][years[0].id]['1'], 'ELEC101', p_huda,   r_eng[0], 'Wednesday', 10, 0, 12, 0, 'lecture'),
            (dept_elec, periods[dept_elec.id][years[0].id]['1'], 'ELEC102', p_ahmed,  r_eng[1], 'Sunday',    8,  0, 10, 0, 'lecture'),
            (dept_elec, periods[dept_elec.id][years[0].id]['1'], 'ELEC102', p_ahmed,  r_eng[1], 'Tuesday',   8,  0, 10, 0, 'lecture'),
            (dept_elec, periods[dept_elec.id][years[0].id]['1'], 'ELEC103', p_sara,   r_eng[2], 'Monday',    14, 0, 16, 0, 'lecture'),

            # Math dept, Year1 Sem1
            (dept_math, periods[dept_math.id][years[0].id]['1'], 'MATH101', p_yousuf, r_sci[0], 'Saturday',  8,  0, 10, 0, 'lecture'),
            (dept_math, periods[dept_math.id][years[0].id]['1'], 'MATH101', p_yousuf, r_sci[0], 'Tuesday',   8,  0, 10, 0, 'lecture'),
            (dept_math, periods[dept_math.id][years[0].id]['1'], 'MATH102', p_najla,  r_sci[1], 'Sunday',    10, 0, 12, 0, 'lecture'),
            (dept_math, periods[dept_math.id][years[0].id]['1'], 'MATH102', p_najla,  r_sci[1], 'Thursday',  10, 0, 12, 0, 'lecture'),
            (dept_math, periods[dept_math.id][years[0].id]['1'], 'MATH103', p_bakr,   r_sci[0], 'Monday',    12, 0, 14, 0, 'lecture'),

            # Physics dept, Year1 Sem1
            (dept_phys, periods[dept_phys.id][years[0].id]['1'], 'PHYS101', p_najla,  r_sci[0], 'Saturday',  12, 0, 14, 0, 'lecture'),
            (dept_phys, periods[dept_phys.id][years[0].id]['1'], 'PHYS101', p_najla,  r_sci[0], 'Wednesday', 12, 0, 14, 0, 'lecture'),
            (dept_phys, periods[dept_phys.id][years[0].id]['1'], 'PHYS102', p_yousuf, r_sci[1], 'Sunday',    8,  0, 10, 0, 'lecture'),
            (dept_phys, periods[dept_phys.id][years[0].id]['1'], 'PHYS103', p_bakr,   r_sci[0], 'Monday',    10, 0, 12, 0, 'lecture'),
        ]

        lecture_objs = []
        for dept, period, code, prof, room, day, sh, sm, eh, em, ltype in lecture_defs:
            dept_id = dept.id
            c = courses[dept_id].get(code)
            if not c:
                continue
            lec, _ = LectureSchedule.objects.get_or_create(
                department=dept, period=period, course=c,
                professor=prof, room=room, day_of_week=day,
                start_time=make_time(sh, sm), end_time=make_time(eh, em),
                defaults={'lecture_type': ltype}
            )
            lecture_objs.append(lec)

        # ── 13. Lab Schedules ────────────────────────
        h_eng = [h for h in halls if h.college == col_eng]
        h_cs  = [h for h in halls if h.college == col_cs]
        h_sci = [h for h in halls if h.college == col_sci]

        lab_defs = [
            (dept_cs,    periods[dept_cs.id][years[0].id]['1'],    'CS101', p_fatima, p_rana,   h_cs[0],  'Monday',    10, 0, 12, 0, 1),
            (dept_cs,    periods[dept_cs.id][years[0].id]['1'],    'CS101', p_fatima, p_rana,   h_cs[0],  'Thursday',  10, 0, 12, 0, 2),
            (dept_cs,    periods[dept_cs.id][years[0].id]['1'],    'CS102', p_omar,   p_rana,   h_cs[1],  'Tuesday',   14, 0, 16, 0, 1),
            (dept_cs,    periods[dept_cs.id][years[1].id]['1'],    'CS202', p_omar,   None,     h_cs[0],  'Monday',    8,  0, 10, 0, 1),
            (dept_it,    periods[dept_it.id][years[0].id]['1'],    'IT101', p_rana,   None,     h_cs[1],  'Saturday',  12, 0, 14, 0, 1),
            (dept_it,    periods[dept_it.id][years[0].id]['1'],    'IT103', p_omar,   p_fatima, h_cs[0],  'Wednesday', 14, 0, 16, 0, 1),
            (dept_civil, periods[dept_civil.id][years[0].id]['1'], 'CIVIL102', p_sara, p_khalid, h_eng[0], 'Saturday', 12, 0, 14, 0, 1),
            (dept_civil, periods[dept_civil.id][years[0].id]['1'], 'CIVIL102', p_sara, p_khalid, h_eng[0], 'Tuesday',  12, 0, 14, 0, 2),
            (dept_elec,  periods[dept_elec.id][years[0].id]['1'], 'ELEC101', p_huda,  p_ahmed,  h_eng[1], 'Sunday',   14, 0, 16, 0, 1),
            (dept_elec,  periods[dept_elec.id][years[0].id]['1'], 'ELEC102', p_ahmed, None,     h_eng[0], 'Thursday', 8,  0, 10, 0, 1),
            (dept_math,  periods[dept_math.id][years[0].id]['1'], 'MATH101', p_yousuf, p_bakr,  h_sci[0], 'Saturday', 14, 0, 16, 0, 1),
            (dept_phys,  periods[dept_phys.id][years[0].id]['1'], 'PHYS101', p_najla, p_bakr,   h_sci[1], 'Monday',   14, 0, 16, 0, 1),
            (dept_phys,  periods[dept_phys.id][years[0].id]['1'], 'PHYS102', p_yousuf, None,    h_sci[0], 'Wednesday', 8, 0, 10, 0, 1),
        ]

        for dept, period, code, prof, asst, hall, day, sh, sm, eh, em, grp in lab_defs:
            c = courses[dept.id].get(code)
            if not c:
                continue
            LabSchedule.objects.get_or_create(
                department=dept, period=period, course=c,
                professor=prof, hall=hall, day_of_week=day,
                start_time=make_time(sh, sm), end_time=make_time(eh, em),
                group_number=grp,
                defaults={'assistant': asst}
            )

        # ── 14. AlternativeTime Requests ─────────────
        lec_sample = lecture_objs[:6] if len(lecture_objs) >= 6 else lecture_objs
        request_defs = [
            # (professor, schedule, status, notes)
            (p_fatima, lec_sample[0] if lec_sample else None, 'pending',
             'سفر خارجي للمشاركة في مؤتمر علمي', 'Monday', 14, 0, 16, 0),
            (p_omar,   lec_sample[2] if len(lec_sample) > 2 else None, 'approved',
             'ظروف صحية طارئة', 'Wednesday', 8, 0, 10, 0),
            (p_ahmed,  lec_sample[4] if len(lec_sample) > 4 else None, 'rejected',
             'ارتباطات خارجية', 'Tuesday', 12, 0, 14, 0),
            (p_sara,   None, 'pending',
             'اجتماع مجلس القسم', 'Thursday', 10, 0, 12, 0),
            (p_khalid, lec_sample[1] if len(lec_sample) > 1 else None, 'approved',
             'انقطاع كهربائي في القسم', 'Sunday', 8, 0, 10, 0),
            (p_huda,   None, 'pending',
             'حضور ورشة تدريبية', 'Saturday', 14, 0, 16, 0),
        ]
        for prof, sched, status, notes, day, sh, sm, eh, em in request_defs:
            AlternativeTime.objects.get_or_create(
                professor=prof,
                day=day,
                time_start=make_time(sh, sm),
                defaults={
                    'schedule': sched,
                    'course_name': sched.course.course_name if sched else 'مادة عامة',
                    'original_day': sched.day_of_week if sched else day,
                    'original_time_start': sched.start_time if sched else make_time(sh, sm),
                    'original_time_end': sched.end_time if sched else make_time(eh, em),
                    'time_start': make_time(sh, sm),
                    'time_end': make_time(eh, em),
                    'notes': notes,
                    'status': status,
                    'admin_notes': 'تمت الموافقة على الطلب' if status == 'approved' else ('تم الرفض لعدم توفر بديل' if status == 'rejected' else ''),
                }
            )

        # ── 15. Taught Lectures ──────────────────────
        today = date.today()
        for i, lec in enumerate(lecture_objs[:10]):
            for delta in [7, 14, 21]:
                TaughtLecture.objects.get_or_create(
                    schedule=lec,
                    taught_date=today - timedelta(days=delta),
                    defaults={'professor': lec.professor, 'notification_sent': True}
                )

        # ── 16. Notifications ────────────────────────
        admin_user = UnifiedUser.objects.filter(user_type='system_manager').first()
        prof_users = UnifiedUser.objects.filter(user_type='professor')[:5]
        std_users  = UnifiedUser.objects.filter(user_type='student')[:4]

        notif_defs = []
        if admin_user:
            notif_defs += [
                (admin_user, 'طلب تغيير موعد جديد', 'قدّم الدكتور أحمد محمد طلب تغيير موعد المحاضرة', False),
                (admin_user, 'تقرير أسبوعي', 'تم إنشاء التقرير الأسبوعي للجداول الدراسية', True),
            ]
        for pu in prof_users:
            notif_defs.append((pu, 'تحديث في الجدول', 'تم تعديل موعد إحدى محاضراتك', False))
        for su in std_users:
            notif_defs.append((su, 'إشعار جدول', 'تم تحديث جدولك الدراسي لهذا الفصل', False))

        for recipient, subj, msg, is_read in notif_defs:
            Notification.objects.get_or_create(
                recipient=recipient, subject=subj,
                defaults={'message': msg, 'status': 'sent', 'is_read': is_read}
            )

        # ── 17. Schedule Deadline ────────────────────
        ScheduleDeadline.objects.get_or_create(
            deadline_date=today + timedelta(days=30)
        )

        # ── 18. Schedule Change Log ──────────────────
        if admin_user and lecture_objs:
            log_defs = [
                (lecture_objs[0], 'add', {'day': 'Saturday', 'start': '08:00'}, None),
                (lecture_objs[1], 'edit', {'day': 'Tuesday', 'start': '08:00'}, {'day': 'Monday', 'start': '10:00'}),
                (lecture_objs[2], 'add', {'day': 'Sunday', 'start': '10:00'}, None),
            ]
            for lec, action, new_data, old_data in log_defs:
                ScheduleChangeLog.objects.get_or_create(
                    schedule_type='lecture', schedule_id=lec.id, action=action,
                    defaults={
                        'changed_by': admin_user,
                        'old_data': old_data,
                        'new_data': new_data,
                        'department_name': lec.department.name,
                        'course_name': lec.course.course_name,
                        'change_reason': 'إضافة بيانات تجريبية',
                    }
                )

    def _print_credentials(self):
        self.stdout.write('')
        self.stdout.write(self.style.SUCCESS('═' * 55))
        self.stdout.write(self.style.SUCCESS('  بيانات الدخول للاختبار'))
        self.stdout.write(self.style.SUCCESS('═' * 55))
        rows = [
            ('مدير النظام',         'admin',      'admin123'),
            ('مدير كلية الهندسة',   'mgr_eng',    'mgr123'),
            ('مدير كلية الحاسوب',   'mgr_cs',     'mgr123'),
            ('مدير كلية العلوم',    'mgr_sci',    'mgr123'),
            ('أستاذ (فاطمة)',       'prof_fatima','prof123'),
            ('أستاذ (أحمد)',        'prof_ahmed', 'prof123'),
            ('أستاذ (عمر)',         'prof_omar',  'prof123'),
            ('طالب (علي)',          'std_ali',    'std123'),
            ('طالب (مريم)',         'std_maryam', 'std123'),
            ('طالب (أسامة)',        'std_osama',  'std123'),
        ]
        for role, uname, pw in rows:
            self.stdout.write(f'  {role:<28} {uname:<16} {pw}')
        self.stdout.write(self.style.SUCCESS('═' * 55))
