// The profile photos an admin can give a user, as the backend checks them
// (apps.users.profile_images): PNG, JPEG or WebP, under 5 MB.

const PHOTO_TYPES = ['image/png', 'image/jpeg', 'image/webp']
const PHOTO_MAX_BYTES = 5 * 1024 * 1024

/** For a file box's accept. */
export const PROFILE_PHOTO_ACCEPT = PHOTO_TYPES.join(',')

export const PROFILE_PHOTO_PROBLEM = 'Choose a PNG, JPEG, or WebP image smaller than 5 MB.'

export const isProfilePhoto = (file: File) => PHOTO_TYPES.includes(file.type) && file.size <= PHOTO_MAX_BYTES
