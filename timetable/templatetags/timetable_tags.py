from django import template

register = template.Library()

DAY_NAMES = {
    'Saturday': 'السبت',
    'Sunday': 'الأحد',
    'Monday': 'الاثنين',
    'Tuesday': 'الثلاثاء',
    'Wednesday': 'الأربعاء',
    'Thursday': 'الخميس',
}

DAY_ORDER = ['Saturday', 'Sunday', 'Monday', 'Tuesday', 'Wednesday', 'Thursday']


@register.filter
def day_arabic(value):
    return DAY_NAMES.get(value, value)


@register.filter
def semester_label(value):
    return 'الفصل الأول' if str(value) == '1' else 'الفصل الثاني'


@register.filter
def get_item(dictionary, key):
    if isinstance(dictionary, dict):
        return dictionary.get(key, '')
    return ''


@register.filter
def lecture_type_arabic(value):
    types = {'lecture': 'محاضرة', 'exercise': 'تمرين'}
    return types.get(value, value)


@register.simple_tag
def get_day_order():
    return DAY_ORDER
