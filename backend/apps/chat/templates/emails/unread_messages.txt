Hi {{ First_Name|default:"there" }},

You have {{ TOTAL_UNREAD }} unread message{{ TOTAL_UNREAD|pluralize }} across {{ GROUP_COUNT }} group{{ GROUP_COUNT|pluralize }} on {{ BRAND_CONNECT }}:
{% for g in GROUPS %}
  - {{ g.name }}: {{ g.count }} unread{% endfor %}

Open {{ BRAND_CONNECT }} to catch up:
{{ PLATFORM_URL }}

You're receiving this because you're a member of a {{ BRAND_CONNECT }} mentoring group. We send at most one reminder a day, and only when you have unread messages.

{{ BRAND_NAME }}
{{ CONTACT_EMAIL }}
