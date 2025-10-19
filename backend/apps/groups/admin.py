from django.contrib import admin
from django import forms
from .models import Groups, GroupMembers, Countries, CountryStates, Tracks


class CountryStatesInline(admin.TabularInline):
	model = CountryStates
	extra = 1
	show_change_link = True


@admin.register(Countries)
class CountryAdmin(admin.ModelAdmin):
	list_display = ("id", "country_name", "country_name_SHORT_FORM")
	search_fields = ("country_name", "country_name_SHORT_FORM")
	inlines = [CountryStatesInline]


@admin.register(CountryStates)
class CountryStateAdmin(admin.ModelAdmin):
	list_display = ("id", "state_name", "state_name_SHORT_FORM", "country")
	list_filter = ("country__country_name",)
	search_fields = ("state_name", "country__country_name", "state_name_SHORT_FORM")


class TrackAdminForm(forms.ModelForm):
	class Meta:
		model = Tracks
		fields = "__all__"

	def clean(self):
		cleaned = super().clean()
		state = cleaned.get("state")
		name = (cleaned.get("track_name") or "").strip()
		if not state or not state.country:
			return cleaned

		country = state.country.country_name
		# Compute expected name based on current platform rules
		if country == "Australia":
			expected = f"AUS-{state.state_name.upper()}"
		elif country == "Brazil":
			expected = "BRA"
		else:
			expected = "GLO"

		# If name is empty, auto-fill; if provided but different, raise a gentle error
		if not name:
			cleaned["track_name"] = expected
		elif name != expected:
			raise forms.ValidationError({
				"track_name": [f"Expected '{expected}' for country '{country}'. Leave blank to auto-fill."]
			})
		return cleaned


@admin.register(Tracks)
class TrackAdmin(admin.ModelAdmin):
	form = TrackAdminForm
	list_display = ("id", "track_name", "state", "state_country")
	list_filter = ("state__country__country_name", "state__state_name")
	search_fields = ("track_name", "state__state_name", "state__country__country_name")

	def state_country(self, obj):
		return obj.state.country.country_name if obj.state_id else ""
	state_country.short_description = "Country"


@admin.register(Groups)
class GroupAdmin(admin.ModelAdmin):
	list_display = ("id", "group_number", "group_name", "track", "cohort_year", "deleted_flag")
	list_filter = ("deleted_flag", "track", "cohort_year")
	search_fields = ("group_number", "group_name", "track__track_name")


@admin.register(GroupMembers)
class GroupMemberAdmin(admin.ModelAdmin):
	list_display = ("id", "group", "user")
	list_filter = ("group",)
	search_fields = ("group__group_name", "user__email")
