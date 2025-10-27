from rest_framework import serializers
from .models import NewsletterSubscription
from django.utils import timezone
from typing import Optional, List
try:
	from apps.resources.models import RoleAssignmentHistory
except Exception:  # pragma: no cover - import-time safety if app not loaded in some contexts
	RoleAssignmentHistory = None


class SubscribeRequestSerializer(serializers.Serializer):
	# Optional: if authenticated and omitted, we'll use request.user.email in the view
	email = serializers.EmailField(required=False, allow_blank=False)


class UnsubscribeRequestSerializer(serializers.Serializer):
	# One of email or token is required
	email = serializers.EmailField(required=False)
	token = serializers.CharField(required=False, allow_blank=False)

	def validate(self, attrs):
		email = attrs.get("email")
		token = attrs.get("token")
		if not email and not token:
			raise serializers.ValidationError("Provide either email or token.")
		return attrs


class ResubscribeRequestSerializer(serializers.Serializer):
	email = serializers.EmailField(required=False, allow_blank=False)


class NewsletterSubscriptionSerializer(serializers.ModelSerializer):
	user_id = serializers.IntegerField(source="user.id", read_only=True)
	first_name = serializers.SerializerMethodField()
	school = serializers.SerializerMethodField()
	region = serializers.SerializerMethodField()
	roles = serializers.SerializerMethodField()

	class Meta:
		model = NewsletterSubscription
		fields = [
			"id",
			"email",
			"user_id",
			"first_name",
			"school",
			"region",
			"roles",
			"is_subscribed",
			"subscribed_at",
			"unsubscribed_at",
			"created_at",
			"updated_at",
		]

	def _safe_o2o(self, user, attr: str):
		if not user:
			return None
		try:
			return getattr(user, attr)
		except Exception:
			return None

	def get_first_name(self, obj: NewsletterSubscription) -> Optional[str]:
		return getattr(obj.user, "first_name", None) if obj.user else None

	def get_school(self, obj: NewsletterSubscription) -> Optional[str]:
		user = obj.user
		if not user:
			return None
		# Prefer StudentProfile.school_name, else MentorProfile.institution, else SupervisorProfile.school_name
		sp = self._safe_o2o(user, "studentprofile")
		if sp and getattr(sp, "school_name", None):
			return sp.school_name
		mp = self._safe_o2o(user, "mentorprofile")
		if mp and getattr(mp, "institution", None):
			return mp.institution
		sup = self._safe_o2o(user, "supervisorprofile")
		if sup and getattr(sup, "school_name", None):
			return sup.school_name
		return None

	def get_region(self, obj: NewsletterSubscription) -> Optional[str]:
		user = obj.user
		if not user:
			return None
		# Primary: user.state.state_name; optional fallback via track.state
		state = getattr(user, "state", None)
		if state and getattr(state, "state_name", None):
			return state.state_name
		track = getattr(user, "track", None)
		if track and getattr(track, "state", None) and getattr(track.state, "state_name", None):
			return track.state.state_name
		return None

	def get_roles(self, obj: NewsletterSubscription) -> List[str]:
		user = obj.user
		if not user:
			return []
		# Prefer prefetched active roles on the user
		active_roles = getattr(user, "active_roles", None)
		if active_roles is not None:
			return [ar.role.role_name for ar in active_roles if getattr(ar, "role", None)]
		# Fallback query if not prefetched
		if RoleAssignmentHistory is None:
			return []
		now = timezone.now()
		qs = (RoleAssignmentHistory.objects
			  .filter(user=user, valid_from__lte=now, valid_to__isnull=True)
			  .select_related("role"))
		return [ra.role.role_name for ra in qs if getattr(ra, "role", None)]
