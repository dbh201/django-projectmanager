from django.urls import path

from . import views

app_name = "project_manager"
urlpatterns = (
    path('', views.IndexView.as_view(), name="index"),
    path('update_status/<int:ipk>/', views.update_task_status, name='update_status'),
    path('rollback_status/<int:ipk>/', views.rollback_task_status, name='rollback_status'),
    path('add_task/', views.AddTaskView.as_view(), name="add_task"),
    path('add_task/submit/', views.add_task_submit, name="add_task_submit"),
    path('details/<int:ipk>/', views.TaskDetailsView.as_view(), name="details"),
    path('edit_task/<int:ipk>/', views.EditTaskView.as_view(), name="edit_task"),
    path('edit_task/submit/<int:ipk>', views.edit_task_submit, name="edit_task_submit"),
)
