"""Persistence capability floor. Domain/resource checks remain in services.

Uses the canonical capability registry; unknown tables fail closed. Aggregate
side-effect tables accept the initiating aggregate's write capability.
"""
from centermanager.core.capabilities import Capability


def mutation_permissions(table, action, column=None):
    verb = {18: 'create', 23: 'update', 9: 'delete'}.get(action, 'update')
    groups = {
        'students': ('student.' + verb, 'student.archive') if verb == 'update' else ('student.' + verb,),
        'incomes': ('finance.income.' + verb,),
        'expenses': ('finance.expense.' + verb,),
        'expense_timeline_events': ('finance.expense.create', 'finance.expense.update', 'finance.expense.delete'),
        'finance_periods': ('finance.period.manage',),
        'financial_settlements': ('finance.settlement.create', 'finance.settlement.update', 'finance.settlement.confirm', 'finance.settlement.reopen'),
        'tuition_adjustments': ('finance.income.create', 'finance.income.update', 'finance.income.delete'),
        'users': ('user.' + verb, 'user.manage', 'user.reset_password'),
        'roles': ('role.manage',), 'role_permissions': ('role.manage',),
        'permissions': ('role.manage',),
        'classes': ('class.' + verb,),
        'class_fee_history': ('class.create', 'class.update'),
        'teacher_assignments': ('class.teacher_assignment.manage', 'class.create', 'class.update'),
        'teachers': ('teacher.' + verb,),
        'employees': ('employee.' + verb, 'employee.update.self', 'employee.archive', 'user.create', 'user.update'),
        'employee_documents': ('employee.update', 'employee.update.self'),
        'employee_working_time_entries': ('working_time.create.self', 'working_time.manage', 'working_time.lock'),
        'employee_work_registration_periods': ('work_registration.manage', 'work_registration.period.admin_override'),
        'attendances': ('attendance.create', 'attendance.update', 'lesson.cancel'),
        'sessions': ('lesson.' + verb, 'lesson.cancel', 'class.create', 'class.update'),
        'reports': ('student.update',), 'report_cache': ('student.update',),
    }
    for name in ('parents', 'assessments', 'progress', 'student_products', 'attachments',
                 'notes', 'session_notes', 'student_highlights', 'documents'):
        groups[name] = ('student.create', 'student.update', 'student.delete', 'attendance.create', 'attendance.update')
    for name in ('enrollments', 'enrollment_freezes', 'enrollment_transfers'):
        groups[name] = ('student.update', 'class.create', 'class.update', 'class.delete', 'tuition.enrollment.override')
    for name in ('employee_schedule_rules', 'employee_schedule_exceptions',
                 'employee_schedule_weeks', 'employee_schedule_assignments'):
        groups[name] = ('schedule.manage',)
    for name in ('employee_work_registrations', 'employee_work_registration_blocks'):
        groups[name] = ('work_registration.self', 'work_registration.manage', 'work_registration.delete', 'work_registration.period.admin_override')
    groups['teacher_documents'] = ('teacher.create', 'teacher.update', 'teacher.delete')
    groups['teacher_timeline_events'] = groups['teacher_documents']
    groups['class_timeline_events'] = ('class.create', 'class.update', 'class.delete', 'lesson.create', 'lesson.update', 'lesson.cancel', 'attendance.create', 'attendance.update', 'student.update')
    groups['timeline_events'] = tuple(c.value for c in Capability if c.value.startswith(('student.', 'attendance.', 'class.', 'finance.income.')) and not c.value.endswith(('.view', '.read', '.export')))
    groups['audit_logs'] = tuple(c.value for c in Capability if not c.value.endswith(('.view', '.read', '.export', '.view.self', '.view.all')))
    if action == 23:
        lifecycle = {
            'students': {'deleted_at': ('student.delete', 'student.update'),
                         'status': ('student.update', 'student.archive'),
                         'updated_at': ('student.update', 'student.archive', 'student.delete')},
            'classes': {'deleted_at': ('class.delete', 'class.update'),
                        'updated_at': ('class.update', 'class.delete')},
            'teachers': {'deleted_at': ('teacher.delete', 'teacher.update'),
                         'updated_at': ('teacher.update', 'teacher.delete')},
            'incomes': {name: ('finance.income.update', 'finance.income.delete')
                        for name in ('deleted_at', 'updated_at', 'status', 'voided_at', 'voided_by', 'void_reason')},
            'expenses': {name: ('finance.expense.update', 'finance.expense.delete')
                         for name in ('deleted_at', 'updated_at')},
        }
        if column in lifecycle.get(table, {}):
            return lifecycle[table][column]
        if table == 'students':
            return ('student.update',)
    return groups.get(table, ())
