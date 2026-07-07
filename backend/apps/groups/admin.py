from django.contrib import admin
from .models import Groups, GroupMembership, Countries, CountryStates

# Register your models here.
admin.site.register(Groups)
admin.site.register(GroupMembership)
admin.site.register(Countries)
admin.site.register(CountryStates)
