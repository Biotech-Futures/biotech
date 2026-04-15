from django.db import models

class RelationshipType(models.Model):
    relationship_type_id = models.BigAutoField(primary_key=True)
    relationship_type = models.CharField(unique=True, max_length=255)

    class Meta:
        db_table = 'relationship_type'
        verbose_name = "Relationship Type"
        verbose_name_plural = "Relationship Types"

    def __str__(self):
        return self.relationship_type
