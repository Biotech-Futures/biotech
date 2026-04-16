from django.db import models

class Background(models.Model):
    background_desc_unique_field = models.TextField() 
    class Meta:
        db_table = 'background'
        verbose_name = "Background"
        verbose_name_plural = "Backgrounds"

    def __str__(self):
        return self.background_desc_unique_field
