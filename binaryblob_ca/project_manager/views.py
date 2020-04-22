from django.contrib import messages
from django.contrib.auth.mixins import PermissionRequiredMixin
from django.contrib.auth.models import User
from django.db.models import F, Q
from django.http import HttpResponseRedirect
from django.utils.timezone import now
from django.urls import reverse
from django.views import generic

from .forms import AddTaskForm
from .models import TaskModel, StatusModel, TaskNoteModel, EventModel, TaskDependencyModel, TaskPermissionModel, \
    Permissions


# views need to do this stuff:
# - Index (summary of tasks) - done
# - Details (specific task) - done
# - Add task - done
# - Edit task - done
# - Update task status - done

# TODO: we're only using TemplateView. There are better options.
class IndexView(generic.ListView):
    template_name = "project_manager/index.html"
    model = TaskModel
    allow_empty = True

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.user = None

    def setup(self, request, *args, **kwargs):
        self.user = request.user
        return super().setup(request, *args, **kwargs)

    def get_queryset(self):
        return self.model.objects.filter(Q(owner=self.user) | Q(owner=None))

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)

        # I've no idea. Don't ask, it just works.
        ctx['most_pressing'] = self.model.get_most_pressing(self.model)
        ctx['highest_priority'] = self.model.get_highest_priority(self.model)
        ctx['needs_polish'] = self.model.get_needs_polish(self.model)
        ctx['incomplete_tasks'] = self.model.get_incomplete_tasks(self.model)
        ctx['complete_tasks'] = self.model.get_complete_tasks(self.model)

        return ctx


class TaskDetailsView(PermissionRequiredMixin, generic.DetailView):
    permission_required = "project_manager.view_taskmodel"
    model = TaskModel
    notes_model = TaskNoteModel

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx['notes'] = self.notes_model.objects.filter(task=self.object)
        ctx['dependencies'] = self.model.objects.filter(task_depends_on__task=self.object)
        return ctx


class AddTaskView(PermissionRequiredMixin, generic.CreateView):
    permission_required = 'project_manager.add_taskmodel'
    form_class = AddTaskForm
    model = TaskModel
    # url = reverse("project_manager:index")

    def __init__(self):
        super().__init__()
        self.object = self.model()

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx['disabled'] = ""
        ctx['all_tasks'] = self.model.objects.all()
        ctx['edit_mode'] = "add"
        return ctx

    def post(self, request, *args, **kwargs):
        resp = super().post(request, *args, **kwargs)
        log_new_task(request, self.object)
        return resp

    def add_task_submit(self, request):
        update_task(task, request)
        messages.success(request, "Added successfully.")
        return HttpResponseRedirect(reverse('project_manager:details', args=[task.pk]))


class EditTaskView(PermissionRequiredMixin, generic.edit.UpdateView):
    permission_required = 'project_manager.update_taskmodel'
    fields = [x.name for x in TaskModel._meta.fields]
    model = TaskModel
    notes_model = TaskNoteModel
    template_name_suffix = "_update_form"

    def get_context_data(self, **kwargs):
        print(self.fields)
        ctx = super().get_context_data(**kwargs)
        ctx['notes'] = self.notes_model.objects.filter(task=self.object)
        return ctx


def log_event(obj, owner, field, old_value, new_value):
    event = EventModel()
    if obj.pk:
        event.r_id = obj.pk
    elif obj.task.pk:
        event.r_id = obj.task.pk
    event.table = obj._meta.db_table
    event.field = field
    event.old_data = old_value
    event.new_data = new_value
    event.date = now()
    event.owner = owner
    event.save()


def log_event_post(request, obj, field, req_field):
    log_event(obj, request.user, field, obj.__dict__[field], request.POST[req_field])


def log_status_update(request, task, status):
    log_event(task, request.user, "status", task.status, status)


def log_changed_fields(request, obj, changed_fields):
    for f in changed_fields:
        log_event(obj, request.user, f[0], f[1], f[2])


def log_new_task(request, task):
    log_event(task, request.user, "", "", "Created object")


def update_task_status(request, ipk):
    task = TaskModel.objects.get(pk=ipk)
    current = TaskModel.objects.get(pk=ipk).status

    if current.progress_id == 0:
        s = now()
        log_event(task, request.user, "started_on", task.started_on, s)
        task.started_on = s

    next_status = StatusModel.objects.filter(progress_id__gt=current.progress_id).order_by('progress_id')
    if next_status:
        log_status_update(request, task, next_status[0])
        task.status = next_status[0]
        task.save()
    return HttpResponseRedirect(reverse('project_manager:index'))


def rollback_task_status(request, ipk):
    task = TaskModel.objects.get(pk=ipk)
    current = TaskModel.objects.get(pk=ipk).status
    last = StatusModel.objects.filter(progress_id__lt=current.progress_id).order_by(F('progress_id').desc())[0]
    if last.progress_id == 0:
        log_event(task, request.user, "started_on", task.started_on, None)
        task.started_on = None
    if last:
        log_status_update(request, task, last)
        task.status = last
        task.save()
    return HttpResponseRedirect(reverse('project_manager:index'))





def edit_task_submit(request, ipk):
    task = TaskModel.objects.get(pk=ipk)
    update_task(task, request)
    messages.success(request, 'Updated successfully.')
    return HttpResponseRedirect(reverse('project_manager:details', args=[ipk]))


def update_task(task, request):
    post_fields = (
        'task_status',
        'task_title',
        'task_desc',
        'task_priority',
    )
    # these fields make errors if they're blank and not null...
    datetime_fields = (
        'task_scheduled_start',
        'task_started_on',
        'task_deadline',
        'task_completed_on',
    )
    changed_fields = []
    for field in post_fields:
        if field in request.POST:
            if not task.__dict__[field[5:]] == request.POST[field]:
                changed_fields.append((field[5:], task.__dict__[field[5:]], request.POST[field],))
                task.__dict__[field[5:]] = request.POST[field]
    for field in datetime_fields:
        if field in request.POST and not request.POST[field] == '':
            if not task.__dict__[field[5:]] == request.POST[field]:
                changed_fields.append((field, task.__dict__[field[5:]], request.POST[field],))
                task.__dict__[field[5:]] = request.POST[field]
    next_status = None
    if task.status is None:
        next_status = StatusModel.objects.get(progress_id=0)
        task.status = next_status
    log_changed_fields(request, task, changed_fields)
    if next_status:
        log_status_update(request, task, next_status)
    parent_task = request.POST.get("task_parent", None)
    if parent_task:
        log_event(task, request.user, "parent_task", task.parent_task, parent_task)
        task.parent_task = TaskModel.objects.get(pk=parent_task)
    task.save()

    # TODO: task dependencies can only be added or removed one at a time...
    cur_deps = TaskDependencyModel.objects.filter(task=task)
    task_dep_add = request.POST.get('task_deps', None)
    task_dep_remove = request.POST.get('task_deps_remove', None)
    task_new_owner = request.POST.get('task_owner', None)
    if task_dep_remove:
        cur_deps.filter(depends_on=dep_tasks).delete()
        cur_deps.save()
    if task_dep_add:
        b = TaskDependencyModel()
        b.task = task
        b.depends_on = TaskModel.objects.get(pk=task_dep_add)
        b.save()
    if task_new_owner:
        try:
            a = task.owner
            task.owner = User.objects.get(username=task_new_owner)
            log_event(task, request.user, "owner", a, task_new_owner)
            task.save()
        except User.DoesNotExist:
            messages.error(request, "Owner was not updated: No such user!")


def add_note_submit(request, ipk):
    note = TaskNoteModel()
    note.task = TaskModel.objects.get(pk=ipk)
    note.date = now()
    note.text = request.POST['task_note']
    note.owner = request.user
    note.save()

    return HttpResponseRedirect(reverse('project_manager:details', args=[ipk]))
