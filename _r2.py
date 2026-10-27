"""The last two conflicts: the admin message list, and the new-message path."""
from pathlib import Path


def rep(path, old, new):
    p = Path(path)
    s = p.read_text()
    assert s.count(old) == 1, "NOT FOUND (or ambiguous) in %s: %r" % (path, old[:70])
    p.write_text(s.replace(old, new, 1))


# --- admin group messages: keep removed ones, drop suppressed ones -------
rep(
    "backend/apps/admin/services/group.py",
    '''<<<<<<< HEAD

    # Soft-deleted messages are included: this endpoint is admin-only, and
    # moderation needs to see what was removed, by whom, and put it back.
    # Participants read chat through apps.chat, which filters them out.
    total = Messages.objects.filter(group_id=gid).count()

    message_records = (
        Messages.objects
        .filter(group_id=gid)
        .select_related(
            "sender_user",
            "sender_user__mentorprofile",
            "sender_user__studentprofile",
            "deleted_by",
=======

    # Get total count
    total = Messages.objects.filter(
        group_id=gid,
        deleted_at__isnull=True,
        is_suppressed=False,
    ).count()

    # Fetch paginated messages
    message_records = (
        Messages.objects
        .filter(
            group_id=gid,
            deleted_at__isnull=True,
            is_suppressed=False,
>>>>>>> main
''',
    '''
    # Soft-deleted messages are included: this endpoint is admin-only, and
    # moderation needs to see what was removed, by whom, and put it back.
    # Participants read chat through apps.chat, which filters them out.
    #
    # Suppressed rows are not: screening treats those as evidence rather than
    # group content and routes them to a support ticket, which is where they
    # are reviewed (see MessageViewSet._message_queryset).
    total = Messages.objects.filter(group_id=gid, is_suppressed=False).count()

    message_records = (
        Messages.objects
        .filter(group_id=gid, is_suppressed=False)
        .select_related(
            "sender_user",
            "sender_user__mentorprofile",
            "sender_user__studentprofile",
            "deleted_by",
''',
)

V = "backend/apps/chat/views.py"

# --- publish_new_message already does mentions; screening is the new step -
rep(
    V,
    '''<<<<<<< HEAD
        publish_new_message(msg, context=self.get_serializer_context(), viewer_id=self.request.user.id)
=======
        apply_mentions(msg)
        _broadcast(gid, "message.created", self._serialize_broadcast_message(msg))
        self._dispatch_link_previews(msg)
        schedule_message_screening(msg)
>>>>>>> main
''',
    '''        # Mentions, the broadcast and link previews all live in the helper,
        # so the chat API and the admin send path stay in step.
        publish_new_message(msg, context=self.get_serializer_context(), viewer_id=self.request.user.id)
        schedule_message_screening(msg)
''',
)

rep(
    V,
    '''<<<<<<< HEAD
                # The broadcast and link previews are both on_commit, so a
                # rollback of this atomic block discards them automatically.
                # Attachment captions can carry URLs too, hence the same path
                # as plain-text posts.
                publish_new_message(message, context=self.get_serializer_context(), viewer_id=request.user.id)
=======
                apply_mentions(message)
                # _broadcast itself wraps in transaction.on_commit, so a rollback
                # of this atomic block discards the WS event automatically.
                _broadcast(gid, "message.created", self._serialize_broadcast_message(message))
                # Attachment captions can carry URLs too — keep unfurl behavior
                # uniform with the plain-text POST path. Dispatch is on_commit,
                # so a failed transaction still cleans up cleanly.
                self._dispatch_link_previews(message)
                schedule_message_screening(message)
>>>>>>> main
''',
    '''                # The broadcast and link previews are both on_commit, so a
                # rollback of this atomic block discards them automatically.
                # Attachment captions can carry URLs too, hence the same path
                # as plain-text posts.
                publish_new_message(message, context=self.get_serializer_context(), viewer_id=request.user.id)
                schedule_message_screening(message)
''',
)

print("group.py and chat/views.py resolved")
