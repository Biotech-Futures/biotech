# TASKS MODELS

from django.db import models

class Milestone(models.Model):
    milestone_id = models.IntegerField(primary_key=True)
    group = models.ForeignKey(Groups, models.DO_NOTHING)
    milestone_name = models.CharField(max_length=255)
    completed = models.BooleanField()
    deleted_flag = models.BooleanField()

    class Meta:
        managed = False
        db_table = 'milestone'

class TaskAssignees(models.Model):
    pk = models.CompositePrimaryKey('task_id', 'user_id')
    task = models.ForeignKey('Tasks', models.DO_NOTHING)
    user = models.ForeignKey('Users', models.DO_NOTHING)
    assigned_datetime = models.DateTimeField()
    deleted_flag = models.BooleanField()

    class Meta:
        managed = False
        db_table = 'task_assignees'

class Tasks(models.Model):
    task_id = models.IntegerField(primary_key=True)
    task_name = models.CharField(max_length=255)
    due_date = models.DateTimeField()
    deleted_flag = models.BooleanField()
    milestone = models.ForeignKey(Milestone, models.DO_NOTHING)
    task_description = models.CharField(max_length=255, blank=True, null=True)

    class Meta:
        managed = False
        db_table = 'tasks'
