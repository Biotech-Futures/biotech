from unittest.mock import patch

from django.test import TestCase

from apps.common.storage import (
    ChatAzureStorage,
    ManagedContainerStorage,
    get_chat_storage,
    get_resource_storage,
    get_ticket_storage,
)


class _RecordingBackend:
    """Stands in for a storage backend and remembers the key it was handed."""

    def __init__(self):
        self.saved_as = None

    def save(self, name, content):
        self.saved_as = name
        return name


def _storage_with(prefix, *, remote):
    storage = ManagedContainerStorage("tickets", ChatAzureStorage, azure_prefix=prefix)
    backend = _RecordingBackend()
    storage._storage = backend
    patcher = patch.object(
        ManagedContainerStorage, "is_remote", property(lambda self: remote)
    )
    return storage, backend, patcher


class AzurePrefixTests(TestCase):
    """DEC-016 D5.

    The class always accepted a namespace, but the Azure branch ignored it —
    every caller's keys landed in the root of the shared container. The prefix
    makes the isolation the design promised actually true, and defaults to
    empty so nothing that exists today moves.
    """

    def test_without_a_prefix_the_key_is_untouched(self):
        storage, backend, patcher = _storage_with("", remote=True)
        with patcher:
            storage.save("2026/08/25/abc/report.pdf", b"x")
        self.assertEqual(backend.saved_as, "2026/08/25/abc/report.pdf")

    def test_the_prefix_lands_on_the_key_when_the_backend_is_azure(self):
        storage, backend, patcher = _storage_with("tickets", remote=True)
        with patcher:
            storage.save("2026/08/25/abc/report.pdf", b"x")
        self.assertEqual(backend.saved_as, "tickets/2026/08/25/abc/report.pdf")

    def test_local_storage_is_left_alone_because_it_already_has_its_own_folder(self):
        storage, backend, patcher = _storage_with("tickets", remote=False)
        with patcher:
            storage.save("2026/08/25/abc/report.pdf", b"x")
        self.assertEqual(backend.saved_as, "2026/08/25/abc/report.pdf")

    def test_the_existing_containers_still_declare_no_prefix(self):
        self.assertEqual(get_chat_storage().azure_prefix, "")
        self.assertEqual(get_resource_storage().azure_prefix, "")

    def test_ticket_attachments_share_the_chat_container_behind_a_prefix(self):
        storage = get_ticket_storage()
        self.assertEqual(storage.azure_prefix, "tickets")
        self.assertIs(storage._azure_storage_cls, ChatAzureStorage)
