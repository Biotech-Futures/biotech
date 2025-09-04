# GROUPS MODELS

from django.db import models

class Groups(models.Model):
    group_id = models.BigAutoField(primary_key=True) # Auto-incrementing primary key
    group_name = models.CharField(max_length=255)
    track = models.ForeignKey('Tracks', on_delete=models.PROTECT) # Protect to prevent deletion when referenced track is gone 
    # I thought this might be good just in case tracks are deleted but groups should persist in the instance tracks are moved or removed
    creation_datetime = models.DateTimeField()
    deleted_flag = models.BooleanField(default=False) # Default to False for better data integrity
    deleted_datetime = models.DateTimeField(null=True, blank=True) # Allow null/blank for groups that aren't deleted

    class Meta:
        db_table = 'groups'
        indexes = [
        models.Index(fields=['track']),
        models.Index(fields=['deleted_flag']),
        models.Index(fields=['creation_datetime']),
    ]
    
    def __str__(self):
        return self.group_name

class GroupMembers(models.Model):
    group = models.ForeignKey('Groups', models.DO_NOTHING)
    user = models.ForeignKey('users.Users', models.DO_NOTHING) # Changed to users.Users just cs it wont resolve from Users since it's not imported

    class Meta:
        db_table = 'group_members'
        constraints = [
            models.UniqueConstraint(
                fields=['group', 'user'],
                name='unique_group_user'
            )
        ] # Composite unique constraint to ensure each user is unique per group, as composite keys aren't natively supported
        indexes = [
            models.Index(fields=['group']),
            models.Index(fields=['user']),
        ]
    
    def __str__(self):
        return f"{self.user} in {self.group}"
    

class Countries(models.Model):
    country_id = models.BigAutoField(primary_key=True) # Auto-incrementing primary key
    country_name = models.CharField(max_length=255)

    class Meta:
        db_table = 'countries'
        indexes = [
            models.Index(fields=['country_name']),
        ]

    def __str__(self):
        return self.country_name


class CountryStates(models.Model):
    state_id = models.BigAutoField(primary_key=True) # Auto-incrementing primary key
    country = models.ForeignKey('Countries', on_delete=models.PROTECT) # Protect to prevent deletion if referenced by country
    state_name = models.CharField(max_length=255)

    class Meta:
        db_table = 'country_states'
        indexes = [
            models.Index(fields=['country']),
            models.Index(fields=['state_name']),
        ]  

    def __str__(self):
        return f"{self.state_name}, {self.country.country_name}"

class Tracks(models.Model):
    track_id = models.BigAutoField(primary_key=True) # Auto-incrementing primary key
    track_name = models.CharField(unique=True, max_length=255)
    state = models.ForeignKey('CountryStates', on_delete=models.PROTECT) # Protect to prevent deletion if referenced by groups

    class Meta:
        db_table = 'tracks'
        indexes = [
            models.Index(fields=['state']),
            models.Index(fields=['track_name']),
        ]

    def __str__(self):
        return self.track_name
    
    #  COMMENTS
    #  Still a bit unsrure about the structure here, tracks and states are almost the same thing?
    #  Maybe we could have tracks as the 'countries' or region as 'state' or something similar like how CountryStates is structured 
    #   - this would remove the double up in similar tables and make it a bit clearer