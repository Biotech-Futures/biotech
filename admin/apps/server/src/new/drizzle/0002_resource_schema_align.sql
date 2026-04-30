BEGIN;

-- resources: rename old columns to target naming (only when old exists and new not yet present)
DO $$
BEGIN
  IF EXISTS (SELECT 1 FROM information_schema.columns WHERE table_schema='public' AND table_name='resources' AND column_name='resource_name')
     AND NOT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_schema='public' AND table_name='resources' AND column_name='name') THEN
    ALTER TABLE public.resources RENAME COLUMN resource_name TO name;
  END IF;
END $$;

DO $$
BEGIN
  IF EXISTS (SELECT 1 FROM information_schema.columns WHERE table_schema='public' AND table_name='resources' AND column_name='resource_description')
     AND NOT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_schema='public' AND table_name='resources' AND column_name='description') THEN
    ALTER TABLE public.resources RENAME COLUMN resource_description TO description;
  END IF;
END $$;

DO $$
BEGIN
  IF EXISTS (SELECT 1 FROM information_schema.columns WHERE table_schema='public' AND table_name='resources' AND column_name='upload_datetime')
     AND NOT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_schema='public' AND table_name='resources' AND column_name='uploaded_at') THEN
    ALTER TABLE public.resources RENAME COLUMN upload_datetime TO uploaded_at;
  END IF;
END $$;

DO $$
BEGIN
  IF EXISTS (SELECT 1 FROM information_schema.columns WHERE table_schema='public' AND table_name='resources' AND column_name='deleted_datetime')
     AND NOT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_schema='public' AND table_name='resources' AND column_name='deleted_at') THEN
    ALTER TABLE public.resources RENAME COLUMN deleted_datetime TO deleted_at;
  END IF;
END $$;

DO $$
BEGIN
  IF EXISTS (SELECT 1 FROM information_schema.columns WHERE table_schema='public' AND table_name='resources' AND column_name='uploader_user_id_id')
     AND NOT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_schema='public' AND table_name='resources' AND column_name='uploaded_by_id') THEN
    ALTER TABLE public.resources RENAME COLUMN uploader_user_id_id TO uploaded_by_id;
  END IF;
END $$;

DO $$
BEGIN
  IF EXISTS (SELECT 1 FROM information_schema.columns WHERE table_schema='public' AND table_name='resources' AND column_name='resource_type_id')
     AND NOT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_schema='public' AND table_name='resources' AND column_name='type_id') THEN
    ALTER TABLE public.resources RENAME COLUMN resource_type_id TO type_id;
  END IF;
END $$;

DO $$
BEGIN
  IF EXISTS (SELECT 1 FROM information_schema.columns WHERE table_schema='public' AND table_name='resources' AND column_name='resource_kind')
     AND NOT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_schema='public' AND table_name='resources' AND column_name='kind') THEN
    ALTER TABLE public.resources RENAME COLUMN resource_kind TO kind;
  END IF;
END $$;

-- required new columns
ALTER TABLE public.resources ADD COLUMN IF NOT EXISTS visibility_scope varchar(50);
ALTER TABLE public.resources ADD COLUMN IF NOT EXISTS track_id bigint;

-- remove columns not used in target schema
ALTER TABLE public.resources DROP COLUMN IF EXISTS deleted_flag;
ALTER TABLE public.resources DROP COLUMN IF EXISTS file_name;
ALTER TABLE public.resources DROP COLUMN IF EXISTS content_html;

-- normalize required data
UPDATE public.resources SET visibility_scope='global' WHERE visibility_scope IS NULL;
ALTER TABLE public.resources ALTER COLUMN visibility_scope SET NOT NULL;

-- resource_roles -> resource_audience
DO $$
BEGIN
  IF EXISTS (SELECT 1 FROM information_schema.tables WHERE table_schema='public' AND table_name='resource_roles')
     AND NOT EXISTS (SELECT 1 FROM information_schema.tables WHERE table_schema='public' AND table_name='resource_audience') THEN
    ALTER TABLE public.resource_roles RENAME TO resource_audience;
  END IF;
END $$;

ALTER TABLE public.resource_audience ADD COLUMN IF NOT EXISTS track_id bigint;

-- resource_types naming alignment
DO $$
BEGIN
  IF EXISTS (SELECT 1 FROM information_schema.columns WHERE table_schema='public' AND table_name='resource_types' AND column_name='type_name')
     AND NOT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_schema='public' AND table_name='resource_types' AND column_name='name') THEN
    ALTER TABLE public.resource_types RENAME COLUMN type_name TO name;
  END IF;
END $$;

DO $$
BEGIN
  IF EXISTS (SELECT 1 FROM information_schema.columns WHERE table_schema='public' AND table_name='resource_types' AND column_name='type_description')
     AND NOT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_schema='public' AND table_name='resource_types' AND column_name='description') THEN
    ALTER TABLE public.resource_types RENAME COLUMN type_description TO description;
  END IF;
END $$;

-- clean old duplicate FK names if present
ALTER TABLE public.resources
  DROP CONSTRAINT IF EXISTS resources_resource_type_id_8ca31a8a_fk_resource_types_id,
  DROP CONSTRAINT IF EXISTS resources_uploader_user_id_id_f9418bc1_fk_users_id;

-- enforce canonical FK names used by code
DO $$
BEGIN
  IF NOT EXISTS (
    SELECT 1 FROM pg_constraint WHERE conname='resources_type_id_fk_resource_types_id' AND conrelid='public.resources'::regclass
  ) THEN
    ALTER TABLE public.resources
      ADD CONSTRAINT resources_type_id_fk_resource_types_id
      FOREIGN KEY (type_id) REFERENCES public.resource_types(id);
  END IF;
END $$;

DO $$
BEGIN
  IF NOT EXISTS (
    SELECT 1 FROM pg_constraint WHERE conname='resources_uploaded_by_id_fk_users_id' AND conrelid='public.resources'::regclass
  ) THEN
    ALTER TABLE public.resources
      ADD CONSTRAINT resources_uploaded_by_id_fk_users_id
      FOREIGN KEY (uploaded_by_id) REFERENCES public.users(id);
  END IF;
END $$;

DO $$
BEGIN
  IF NOT EXISTS (
    SELECT 1 FROM pg_constraint WHERE conname='resources_group_id_fk_groups_id' AND conrelid='public.resources'::regclass
  ) THEN
    ALTER TABLE public.resources
      ADD CONSTRAINT resources_group_id_fk_groups_id
      FOREIGN KEY (group_id) REFERENCES public.groups(id);
  END IF;
END $$;

DO $$
BEGIN
  IF NOT EXISTS (
    SELECT 1 FROM pg_constraint WHERE conname='resources_track_id_fk_tracks_id' AND conrelid='public.resources'::regclass
  ) THEN
    ALTER TABLE public.resources
      ADD CONSTRAINT resources_track_id_fk_tracks_id
      FOREIGN KEY (track_id) REFERENCES public.tracks(id);
  END IF;
END $$;

DO $$
BEGIN
  IF NOT EXISTS (
    SELECT 1 FROM pg_constraint WHERE conname='resource_audience_resource_id_fk_resources_id' AND conrelid='public.resource_audience'::regclass
  ) THEN
    ALTER TABLE public.resource_audience
      ADD CONSTRAINT resource_audience_resource_id_fk_resources_id
      FOREIGN KEY (resource_id) REFERENCES public.resources(id);
  END IF;
END $$;

DO $$
BEGIN
  IF NOT EXISTS (
    SELECT 1 FROM pg_constraint WHERE conname='resource_audience_role_id_fk_roles_id' AND conrelid='public.resource_audience'::regclass
  ) THEN
    ALTER TABLE public.resource_audience
      ADD CONSTRAINT resource_audience_role_id_fk_roles_id
      FOREIGN KEY (role_id) REFERENCES public.roles(id);
  END IF;
END $$;

DO $$
BEGIN
  IF NOT EXISTS (
    SELECT 1 FROM pg_constraint WHERE conname='resource_audience_track_id_fk_tracks_id' AND conrelid='public.resource_audience'::regclass
  ) THEN
    ALTER TABLE public.resource_audience
      ADD CONSTRAINT resource_audience_track_id_fk_tracks_id
      FOREIGN KEY (track_id) REFERENCES public.tracks(id);
  END IF;
END $$;

COMMIT;
