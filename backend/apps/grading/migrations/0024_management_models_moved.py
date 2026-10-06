"""Management's models moved to apps.management (its 0001). Their tables
stay as they are, so only Django's record of them changes here."""
import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('grading', '0023_presentation_availability_one_per_team'),
        ('management', '0001_initial'),
    ]

    operations = [
        migrations.SeparateDatabaseAndState(
            state_operations=[
                migrations.AlterField(
                    model_name='finalistflag',
                    name='presentation_slot',
                    field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='allocated_flags', to='management.presentationslot'),
                ),
                migrations.DeleteModel(name='CertificatesRelease'),
                migrations.DeleteModel(name='EmailSendRun'),
                migrations.DeleteModel(name='FinalistEmailSettings'),
                migrations.DeleteModel(name='FinalistSlides'),
                migrations.DeleteModel(name='GradingSettings'),
                migrations.DeleteModel(name='MarksRelease'),
                migrations.DeleteModel(name='NonFinalistEmail'),
                migrations.DeleteModel(name='NonSubmissionEmail'),
                migrations.DeleteModel(name='ResultsEmailSettings'),
                migrations.DeleteModel(name='ResultsSupervisorEmail'),
                migrations.DeleteModel(name='ResultsTeamEmail'),
                migrations.DeleteModel(name='PresentationAvailability'),
                migrations.DeleteModel(name='PresentationSlot'),
            ],
            database_operations=[],
        ),
    ]
