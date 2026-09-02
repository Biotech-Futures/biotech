from apps.common.storage import ManagedFileService, get_submission_storage


# Competition entries get their own container (see AZURE_SUBMISSION_CONTAINER)
# so they are not mixed in with the general resource library.
SUBMISSION_FILE_SERVICE = ManagedFileService(get_submission_storage)
