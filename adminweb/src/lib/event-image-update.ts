import type { UpdateEvent } from "@/schema/event";

/**
 * Keep an existing banner unless the administrator explicitly removed it.
 *
 * The Image URL input is normalized from an empty string to null by Zod, so
 * form dirty tracking is not a safe deletion signal. A null is sent only for
 * the dedicated Remove action; selecting a replacement leaves the old banner
 * in place until the subsequent upload succeeds.
 */
export function buildEventUpdateWithImageIntent(
  formData: UpdateEvent,
  imageRemoved: boolean,
): UpdateEvent {
  const updateData = { ...formData };

  if (imageRemoved) {
    updateData.eventImage = null;
  } else {
    delete updateData.eventImage;
  }

  return updateData;
}
