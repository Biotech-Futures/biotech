from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


def seed_default_views(apps, schema_editor):
    AdminView = apps.get_model('custom_admin', 'AdminView')

    defaults = [
        {
            'name': 'All Users',
            'description': 'Complete directory of all registered accounts',
            'visibility': 'system',
            'is_default': True,
            'target_roles': ['all'],
            'account_status': 'all',
            'engagement_status': 'all',
            'advanced_conditions': [],
            'visible_columns': ['name', 'email', 'role', 'school', 'state', 'status'],
        },
        {
            'name': 'All Mentors',
            'description': 'Active certified mentors across all domains',
            'visibility': 'system',
            'is_default': True,
            'target_roles': ['mentor'],
            'account_status': 'active',
            'engagement_status': 'all',
            'advanced_conditions': [],
            'visible_columns': ['name', 'email', 'role', 'institution', 'state', 'status'],
        },
        {
            'name': 'All Supervisors',
            'description': 'Institution and academic supervisors',
            'visibility': 'system',
            'is_default': True,
            'target_roles': ['supervisor'],
            'account_status': 'active',
            'engagement_status': 'all',
            'advanced_conditions': [],
            'visible_columns': ['name', 'email', 'role', 'school', 'state', 'status'],
        },
        {
            'name': 'All Admins',
            'description': 'Platform administrators with elevated management permissions',
            'visibility': 'system',
            'is_default': True,
            'target_roles': ['admin'],
            'account_status': 'active',
            'engagement_status': 'all',
            'advanced_conditions': [],
            'visible_columns': ['name', 'email', 'role', 'last_login', 'status'],
        },
    ]

    for item in defaults:
        AdminView.objects.update_or_create(
            name=item['name'],
            defaults=item
        )


def reverse_default_views(apps, schema_editor):
    AdminView = apps.get_model('custom_admin', 'AdminView')
    AdminView.objects.filter(is_default=True).delete()


class Migration(migrations.Migration):

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ('custom_admin', '0001_initial'),
    ]

    operations = [
        migrations.CreateModel(
            name='AdminView',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('name', models.CharField(max_length=255)),
                ('description', models.TextField(blank=True, default='')),
                ('visibility', models.CharField(choices=[('system', 'System Default'), ('shared', 'Admin Shared'), ('private', 'Private')], default='shared', max_length=32)),
                ('is_default', models.BooleanField(default=False)),
                ('target_roles', models.JSONField(default=list)),
                ('account_status', models.CharField(default='all', max_length=32)),
                ('engagement_status', models.CharField(default='all', max_length=32)),
                ('advanced_conditions', models.JSONField(default=list)),
                ('visible_columns', models.JSONField(default=list)),
                ('last_run_at', models.DateTimeField(blank=True, null=True)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('created_by', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='admin_custom_views', to=settings.AUTH_USER_MODEL)),
            ],
            options={
                'db_table': 'admin_user_views',
                'ordering': ['-is_default', 'name'],
            },
        ),
        migrations.RunPython(seed_default_views, reverse_default_views),
    ]
