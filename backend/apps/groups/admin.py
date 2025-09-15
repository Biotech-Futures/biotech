from django.contrib import admin
from .models import Groups, GroupMembers, Countries, CountryStates, Tracks

# Register your models here.
admin.site.register(Groups)
admin.site.register(GroupMembers)
admin.site.register(Countries)
admin.site.register(CountryStates)
admin.site.register(Tracks)
