# Generated by Django 3.0.5 on 2020-04-21 16:31

from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('project_manager', '0004_eventmodel'),
    ]

    operations = [
        migrations.AddField(
            model_name='taskmodel',
            name='parent_task',
            field=models.ForeignKey(null=True, on_delete=django.db.models.deletion.CASCADE, to='project_manager.TaskModel'),
        ),
    ]
