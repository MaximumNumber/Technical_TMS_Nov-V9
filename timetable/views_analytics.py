from django.shortcuts import render
from django.contrib.auth.decorators import login_required
from django.http import JsonResponse
from django.db.models import Count, Q
from .models import (
    LectureSchedule, LabSchedule, Room, Hall, Professor, Department,
    CollegeDepartment, CollegeRoom, CollegeHall, DepartmentAcademicPeriod, College
)

DAY_ORDER = ['Saturday', 'Sunday', 'Monday', 'Tuesday', 'Wednesday', 'Thursday']
DAY_NAMES = {
    'Saturday': 'السبت', 'Sunday': 'الأحد', 'Monday': 'الاثنين',
    'Tuesday': 'الثلاثاء', 'Wednesday': 'الأربعاء', 'Thursday': 'الخميس',
}


def build_analytics_data(college=None):
    lectures_qs = LectureSchedule.objects.select_related('course', 'department', 'professor', 'room', 'period')
    labs_qs = LabSchedule.objects.select_related('course', 'department', 'professor', 'hall', 'period')
    rooms_qs = Room.objects.all()
    halls_qs = Hall.objects.all()
    professors_qs = Professor.objects.all()
    departments_qs = Department.objects.all()

    if college:
        dept_ids = list(CollegeDepartment.objects.filter(college=college).values_list('department_id', flat=True))
        lectures_qs = lectures_qs.filter(department_id__in=dept_ids)
        labs_qs = labs_qs.filter(department_id__in=dept_ids)
        room_ids = list(CollegeRoom.objects.filter(college=college, is_active=True).values_list('room_id', flat=True))
        hall_ids = list(CollegeHall.objects.filter(college=college, is_active=True).values_list('hall_id', flat=True))
        rooms_qs = rooms_qs.filter(id__in=room_ids)
        halls_qs = halls_qs.filter(id__in=hall_ids)
        professors_qs = professors_qs.filter(Q(college=college) | Q(college_relations__college=college)).distinct()
        departments_qs = departments_qs.filter(id__in=dept_ids)

    total_lectures = lectures_qs.count()
    total_labs = labs_qs.count()
    total_rooms = rooms_qs.count()
    total_halls = halls_qs.count()
    total_professors = professors_qs.count()

    # Schedule distribution by day
    day_lecture_counts = {}
    day_lab_counts = {}
    for day in DAY_ORDER:
        day_lecture_counts[DAY_NAMES[day]] = lectures_qs.filter(day_of_week=day).count()
        day_lab_counts[DAY_NAMES[day]] = labs_qs.filter(day_of_week=day).count()

    # Busiest days (combined)
    day_totals = {day: day_lecture_counts[DAY_NAMES[day]] + day_lab_counts[DAY_NAMES[day]] for day in DAY_ORDER}
    busiest_day = max(day_totals, key=day_totals.get) if day_totals else None
    busiest_day_name = DAY_NAMES.get(busiest_day, '') if busiest_day else ''
    busiest_day_count = day_totals.get(busiest_day, 0) if busiest_day else 0

    # Room occupancy (lectures per room)
    room_usage = []
    for room in rooms_qs:
        count = lectures_qs.filter(room=room).count()
        # Total available slots = 6 days * max time slots (assume 8 slots/day)
        max_slots = 6 * 8
        occupancy_pct = round((count / max_slots) * 100, 1) if max_slots > 0 else 0
        room_usage.append({
            'name': room.name,
            'code': room.code,
            'count': count,
            'capacity': room.capacity,
            'occupancy_pct': occupancy_pct,
        })
    room_usage.sort(key=lambda x: x['count'], reverse=True)
    for r in room_usage:
        r['sessions'] = r['count']
        r['utilization_pct'] = r['occupancy_pct']

    # Lab utilization
    hall_usage = []
    for hall in halls_qs:
        count = labs_qs.filter(hall=hall).count()
        max_slots = 6 * 8
        utilization_pct = round((count / max_slots) * 100, 1) if max_slots > 0 else 0
        hall_usage.append({
            'name': hall.name,
            'code': hall.code,
            'count': count,
            'sessions': count,
            'capacity': hall.capacity,
            'utilization_pct': utilization_pct,
        })
    hall_usage.sort(key=lambda x: x['count'], reverse=True)

    # Professor teaching load
    prof_load = []
    for prof in professors_qs[:20]:
        lec_count = lectures_qs.filter(professor=prof).count()
        lab_count = labs_qs.filter(Q(professor=prof) | Q(assistant=prof)).count()
        total = lec_count + lab_count
        if total > 0:
            prof_load.append({
                'name': prof.name,
                'position': prof.position,
                'lectures': lec_count,
                'labs': lab_count,
                'total': total,
            })
    prof_load.sort(key=lambda x: x['total'], reverse=True)
    top_professors = prof_load[:10]

    # Department pressure
    dept_pressure = []
    for dept in departments_qs:
        lec_count = lectures_qs.filter(department=dept).count()
        lab_count = labs_qs.filter(department=dept).count()
        total = lec_count + lab_count
        if total > 0:
            dept_pressure.append({
                'name': dept.name,
                'lectures': lec_count,
                'labs': lab_count,
                'total': total,
            })
    dept_pressure.sort(key=lambda x: x['total'], reverse=True)
    top_departments = dept_pressure[:10]

    # Unused rooms (rooms with 0 lectures this period)
    used_room_ids = set(lectures_qs.values_list('room_id', flat=True))
    unused_rooms = rooms_qs.exclude(id__in=used_room_ids).count()
    used_hall_ids = set(labs_qs.values_list('hall_id', flat=True))
    unused_halls = halls_qs.exclude(id__in=used_hall_ids).count()

    # Average hours per professor
    avg_hours = round(total_lectures / total_professors, 1) if total_professors > 0 else 0

    # Total sessions
    total_sessions = total_lectures + total_labs

    # Average rooms utilization
    rooms_util_avg = round(sum(r['occupancy_pct'] for r in room_usage) / len(room_usage), 1) if room_usage else 0
    halls_util_avg = round(sum(h['utilization_pct'] for h in hall_usage) / len(hall_usage), 1) if hall_usage else 0

    # Lecture type distribution
    lecture_type_dist = {}
    for lt in lectures_qs.values('lecture_type').annotate(cnt=Count('id')):
        label = 'محاضرة' if lt['lecture_type'] == 'lecture' else 'تمرين'
        lecture_type_dist[label] = lt['cnt']

    # Conflicts count: schedules where professor/room has overlapping times
    conflicts_count = 0
    try:
        from django.db.models import Count as _Count
        # Count professor conflicts (same professor, same day, overlapping time)
        profs_with_conflicts = set()
        for lec in lectures_qs:
            overlaps = lectures_qs.filter(
                professor=lec.professor,
                day_of_week=lec.day_of_week,
                start_time__lt=lec.end_time,
                end_time__gt=lec.start_time,
            ).exclude(id=lec.id)
            if overlaps.exists():
                profs_with_conflicts.add(lec.id)
        conflicts_count = len(profs_with_conflicts)
    except Exception:
        conflicts_count = 0

    # Total departments
    total_departments = departments_qs.count()

    return {
        'total_lectures': total_lectures,
        'total_labs': total_labs,
        'total_sessions': total_sessions,
        'total_rooms': total_rooms,
        'total_halls': total_halls,
        'total_professors': total_professors,
        'active_professors': total_professors,
        'total_departments': total_departments,
        'conflicts_count': conflicts_count,
        'unused_rooms': unused_rooms,
        'unused_halls': unused_halls,
        'avg_hours_per_professor': avg_hours,
        'rooms_util_avg': rooms_util_avg,
        'halls_util_avg': halls_util_avg,
        'busiest_day': busiest_day_name,
        'busiest_day_count': busiest_day_count,
        'day_names': list(DAY_NAMES.values()),
        'day_lecture_counts': [day_lecture_counts[DAY_NAMES[d]] for d in DAY_ORDER],
        'day_lab_counts': [day_lab_counts[DAY_NAMES[d]] for d in DAY_ORDER],
        'day_totals': [day_totals[d] for d in DAY_ORDER],
        'room_usage': room_usage[:10],
        'hall_usage': hall_usage[:10],
        'room_utilization': room_usage[:10],
        'hall_utilization': hall_usage[:10],
        'top_professors': top_professors,
        'top_departments': top_departments,
        'lecture_type_dist_labels': list(lecture_type_dist.keys()),
        'lecture_type_dist_values': list(lecture_type_dist.values()),
    }
