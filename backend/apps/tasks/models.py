# TASKS MODELS

from django.db import models

class Milestone(models.Model):
    milestone_id = models.IntegerField(primary_key=True)
    # Field name made lowercase. Field renamed to remove unsuitable characters. Field renamed because it ended with '_'.
    group_id_fk_field = models.ForeignKey(
        Groups, models.DO_NOTHING, db_column='group_id (FK)')
    milestone_name = models.CharField(max_length=255)
    completed = models.BooleanField()
    deleted_flag = models.BooleanField()

    class Meta:
        # managed = False
        db_table = 'milestone'

class TaskAssignees(models.Model):
    pk = models.CompositePrimaryKey('task_id', 'user_id')
    task = models.ForeignKey('Tasks', models.DO_NOTHING)
    user_id = models.IntegerField(unique=True)
    assigned_datetime = models.DateTimeField()
    deleted_flag = models.BooleanField()

    class Meta:
        # managed = False
        db_table = 'task_assignees'


class Tasks(models.Model):
    task_id = models.IntegerField(primary_key=True)
    task_name = models.CharField(max_length=255)
    due_date = models.DateTimeField()
    deleted_flag = models.BooleanField()
    # Field name made lowercase. Field renamed to remove unsuitable characters. Field renamed because it ended with '_'.
    milestone_id_fk_field = models.ForeignKey(
        Milestone, models.DO_NOTHING, db_column='milestone_id (FK)')
    task_description = models.CharField(max_length=255, blank=True, null=True)

    class Meta:
        # managed = False
        db_table = 'tasks'
