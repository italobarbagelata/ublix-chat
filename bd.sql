-- WARNING: This schema is for context only and is not meant to be run.
-- Table order and constraints may not be valid for execution.

CREATE TABLE public.agenda (
  project_id uuid NOT NULL,
  owner_email character varying,
  contact_email character varying,
  id uuid NOT NULL DEFAULT uuid_generate_v4(),
  email_templates jsonb DEFAULT '{}'::jsonb,
  workflow_settings jsonb DEFAULT '{}'::jsonb,
  general_settings jsonb DEFAULT '{}'::jsonb,
  created_at timestamp with time zone DEFAULT CURRENT_TIMESTAMP,
  updated_at timestamp with time zone DEFAULT CURRENT_TIMESTAMP,
  CONSTRAINT agenda_pkey PRIMARY KEY (id),
  CONSTRAINT agenda_project_id_fkey FOREIGN KEY (project_id) REFERENCES public.projects(project_id)
);
CREATE TABLE public.ai_messages (
  message_id uuid,
  conversation_id uuid NOT NULL,
  type character varying NOT NULL CHECK (type::text = ANY (ARRAY['tool'::character varying, 'ai_tool'::character varying]::text[])),
  content text,
  tool character varying,
  call_timestamp timestamp with time zone,
  id uuid NOT NULL DEFAULT uuid_generate_v4(),
  input_tokens integer DEFAULT 0,
  output_tokens integer DEFAULT 0,
  duration double precision DEFAULT 0,
  CONSTRAINT ai_messages_pkey PRIMARY KEY (id),
  CONSTRAINT ai_messages_message_id_fkey FOREIGN KEY (message_id) REFERENCES public.messages(id)
);
CREATE TABLE public.apis (
  project_id uuid NOT NULL,
  api_name character varying NOT NULL,
  api_description text,
  api_request_type character varying NOT NULL,
  api_endpoint text NOT NULL,
  id uuid NOT NULL DEFAULT gen_random_uuid(),
  api_headers jsonb DEFAULT '[]'::jsonb,
  api_body jsonb DEFAULT '[]'::jsonb,
  api_parameters jsonb DEFAULT '[]'::jsonb,
  created_at timestamp with time zone DEFAULT now(),
  updated_at timestamp with time zone DEFAULT now(),
  CONSTRAINT apis_pkey PRIMARY KEY (id)
);
CREATE TABLE public.calendar_events (
  calendar_id uuid,
  title text NOT NULL,
  description text,
  start_time timestamp with time zone NOT NULL,
  end_time timestamp with time zone NOT NULL,
  id uuid NOT NULL DEFAULT gen_random_uuid(),
  created_at timestamp with time zone DEFAULT now(),
  user_id text,
  CONSTRAINT calendar_events_pkey PRIMARY KEY (id),
  CONSTRAINT calendar_events_calendar_id_fkey FOREIGN KEY (calendar_id) REFERENCES public.calendars(id)
);
CREATE TABLE public.calendar_integrations (
  project_id uuid NOT NULL,
  access_token text NOT NULL,
  refresh_token text NOT NULL,
  token_expiry timestamp with time zone,
  user_email character varying,
  id uuid NOT NULL DEFAULT gen_random_uuid(),
  provider character varying NOT NULL DEFAULT 'google'::character varying,
  calendar_id character varying DEFAULT 'primary'::character varying,
  is_active boolean DEFAULT true,
  created_at timestamp with time zone DEFAULT now(),
  updated_at timestamp with time zone DEFAULT now(),
  CONSTRAINT calendar_integrations_pkey PRIMARY KEY (id)
);
CREATE TABLE public.calendars (
  project_id uuid,
  name text NOT NULL,
  color text,
  id uuid NOT NULL DEFAULT gen_random_uuid(),
  created_at timestamp with time zone DEFAULT now(),
  CONSTRAINT calendars_pkey PRIMARY KEY (id),
  CONSTRAINT calendars_project_id_fkey FOREIGN KEY (project_id) REFERENCES public.projects(project_id)
);
CREATE TABLE public.config_chat (
  project_id uuid,
  theme_color text,
  background_color text,
  text_color text,
  font_family text,
  welcome_message text,
  footer_message text,
  avatar_url text,
  id uuid NOT NULL DEFAULT gen_random_uuid(),
  show_typing_indicator boolean DEFAULT true,
  created_at timestamp with time zone DEFAULT now(),
  updated_at timestamp with time zone DEFAULT now(),
  background_buble_send text,
  background_buble_recieve text,
  color_text_send text,
  color_text_recieve text,
  background_color_input text,
  text_color_input text,
  form_data_1 text,
  form_data_2 text,
  form_data_3 text,
  color_burble text,
  color_burble_text text,
  title_chat text,
  color_bg_btn text,
  text_btn text,
  border_form text,
  color_text_btn text,
  form_data_4 text,
  show_form boolean,
  active_form_1 boolean,
  border_input_color text,
  active_form_2 boolean,
  active_form_3 boolean,
  active_form_4 boolean,
  CONSTRAINT config_chat_pkey PRIMARY KEY (id),
  CONSTRAINT config_chat_project_id_fkey FOREIGN KEY (project_id) REFERENCES public.projects(project_id)
);
CREATE TABLE public.contact_field_configs (
  project_id uuid NOT NULL,
  field_name character varying NOT NULL,
  field_type character varying NOT NULL CHECK (field_type::text = ANY (ARRAY['string'::character varying, 'number'::character varying, 'boolean'::character varying]::text[])),
  description text,
  id uuid NOT NULL DEFAULT gen_random_uuid(),
  keywords jsonb NOT NULL DEFAULT '[]'::jsonb,
  priority integer DEFAULT 1,
  created_at timestamp with time zone DEFAULT now(),
  updated_at timestamp with time zone DEFAULT now(),
  is_active boolean DEFAULT true,
  CONSTRAINT contact_field_configs_pkey PRIMARY KEY (id)
);
CREATE TABLE public.contacts (
  project_id uuid NOT NULL,
  name character varying NOT NULL,
  phone_number character varying,
  email character varying,
  id uuid NOT NULL DEFAULT gen_random_uuid(),
  contact_id uuid NOT NULL DEFAULT gen_random_uuid(),
  created_at timestamp with time zone DEFAULT timezone('America/Santiago'::text, now()),
  updated_at timestamp with time zone DEFAULT timezone('America/Santiago'::text, now()),
  user_id text,
  additional_fields jsonb DEFAULT '{}'::jsonb,
  CONSTRAINT contacts_pkey PRIMARY KEY (id),
  CONSTRAINT contacts_project_id_fkey FOREIGN KEY (project_id) REFERENCES public.projects(project_id)
);
CREATE TABLE public.conversation_data (
  project_id uuid NOT NULL,
  phone_number character varying NOT NULL,
  summary text,
  id uuid NOT NULL DEFAULT uuid_generate_v4(),
  created_at timestamp with time zone DEFAULT CURRENT_TIMESTAMP,
  updated_at timestamp with time zone DEFAULT CURRENT_TIMESTAMP,
  CONSTRAINT conversation_data_pkey PRIMARY KEY (id),
  CONSTRAINT conversation_data_project_id_fkey FOREIGN KEY (project_id) REFERENCES public.projects(project_id)
);
CREATE TABLE public.datasources (
  name character varying NOT NULL,
  status character varying,
  type character varying NOT NULL,
  configuration jsonb,
  project_id uuid NOT NULL,
  metadata jsonb,
  datasource_id uuid NOT NULL DEFAULT uuid_generate_v4(),
  created_at timestamp with time zone DEFAULT CURRENT_TIMESTAMP,
  updated_at timestamp with time zone DEFAULT CURRENT_TIMESTAMP,
  CONSTRAINT datasources_pkey PRIMARY KEY (datasource_id),
  CONSTRAINT datasources_project_id_fkey FOREIGN KEY (project_id) REFERENCES public.projects(project_id)
);
CREATE TABLE public.documents (
  content text,
  content_vector USER-DEFINED,
  filename text,
  title text,
  keywords text,
  description text,
  question text,
  answer text,
  metadata jsonb,
  id uuid NOT NULL DEFAULT uuid_generate_v4(),
  created_at timestamp with time zone DEFAULT timezone('utc'::text, now()),
  project_id uuid,
  CONSTRAINT documents_pkey PRIMARY KEY (id)
);
CREATE TABLE public.instagram_conversation_states (
  project_id uuid NOT NULL,
  instagram_page_id text NOT NULL,
  instagram_user_id text NOT NULL,
  id uuid NOT NULL DEFAULT uuid_generate_v4(),
  bot_active boolean DEFAULT true,
  last_updated timestamp with time zone DEFAULT CURRENT_TIMESTAMP,
  created_at timestamp with time zone DEFAULT CURRENT_TIMESTAMP,
  CONSTRAINT instagram_conversation_states_pkey PRIMARY KEY (id)
);
CREATE TABLE public.instructions (
  project_id uuid NOT NULL,
  name character varying NOT NULL,
  content text NOT NULL,
  created_by uuid,
  instruction_id uuid NOT NULL DEFAULT uuid_generate_v4(),
  version integer NOT NULL DEFAULT 1,
  is_active boolean NOT NULL DEFAULT true,
  created_at timestamp with time zone DEFAULT CURRENT_TIMESTAMP,
  updated_at timestamp with time zone DEFAULT CURRENT_TIMESTAMP,
  CONSTRAINT instructions_pkey PRIMARY KEY (instruction_id),
  CONSTRAINT instructions_project_id_fkey FOREIGN KEY (project_id) REFERENCES public.projects(project_id),
  CONSTRAINT instructions_created_by_fkey FOREIGN KEY (created_by) REFERENCES auth.users(id)
);
CREATE TABLE public.integration_instagram (
  is_long_lived_token boolean DEFAULT true,
  token_expires_at timestamp with time zone,
  synced boolean DEFAULT false,
  project_id uuid NOT NULL,
  instagram_app_id character varying,
  webhook_verify_token character varying,
  webhook_url character varying,
  instagram_page_id character varying,
  id uuid NOT NULL DEFAULT uuid_generate_v4(),
  active boolean DEFAULT true,
  created_at timestamp with time zone DEFAULT CURRENT_TIMESTAMP,
  updated_at timestamp with time zone DEFAULT CURRENT_TIMESTAMP,
  user_access_token text,
  instagram_page_name character varying,
  instagram_page_access_token text,
  instagram_business_account_id character varying,
  instagram_username character varying,
  instagram_name character varying,
  instagram_profile_picture text,
  access_token text,
  token_type text,
  CONSTRAINT integration_instagram_pkey PRIMARY KEY (id),
  CONSTRAINT fk_project FOREIGN KEY (project_id) REFERENCES public.projects(project_id)
);
CREATE TABLE public.integration_messenger (
  integration_type text,
  pages text,
  business_id text,
  webhook_url text,
  webhook_verify_token text,
  active boolean,
  project_id uuid NOT NULL UNIQUE,
  access_token text NOT NULL,
  id uuid NOT NULL DEFAULT uuid_generate_v4(),
  created_at timestamp with time zone NOT NULL DEFAULT now(),
  updated_at timestamp with time zone NOT NULL DEFAULT now(),
  permitted_roles text,
  whatsapp_account_id text,
  CONSTRAINT integration_messenger_pkey PRIMARY KEY (id),
  CONSTRAINT meta_configs_project_id_fkey FOREIGN KEY (project_id) REFERENCES public.projects(project_id)
);
CREATE TABLE public.integration_whatsapp (
  project_id uuid NOT NULL UNIQUE,
  access_token text NOT NULL,
  business_id text,
  integration_type text,
  pages text,
  webhook_url text,
  webhook_verify_token text,
  active boolean,
  permitted_roles text,
  whatsapp_account_id text,
  id uuid NOT NULL DEFAULT uuid_generate_v4(),
  created_at timestamp with time zone NOT NULL DEFAULT now(),
  updated_at timestamp with time zone NOT NULL DEFAULT now(),
  business_account_id text,
  phone_number_id text,
  CONSTRAINT integration_whatsapp_pkey PRIMARY KEY (id),
  CONSTRAINT integration_whatsapp_project_id_fkey FOREIGN KEY (project_id) REFERENCES public.projects(project_id)
);
CREATE TABLE public.integration_whatsapp_api (
  project_id uuid NOT NULL,
  phone_number_id character varying NOT NULL,
  access_token text NOT NULL,
  business_account_id character varying,
  webhook_verify_token character varying,
  webhook_url character varying,
  id uuid NOT NULL DEFAULT uuid_generate_v4(),
  active boolean DEFAULT true,
  created_at timestamp with time zone DEFAULT CURRENT_TIMESTAMP,
  updated_at timestamp with time zone DEFAULT CURRENT_TIMESTAMP,
  CONSTRAINT integration_whatsapp_api_pkey PRIMARY KEY (id)
);
CREATE TABLE public.integration_whatsapp_web (
  connected_at timestamp with time zone,
  last_connected_at timestamp with time zone,
  profile_name text,
  profile_id text,
  project_id uuid NOT NULL,
  phone_number_id character varying NOT NULL,
  business_account_id character varying,
  id uuid NOT NULL DEFAULT gen_random_uuid(),
  active boolean DEFAULT true,
  created_at timestamp with time zone NOT NULL DEFAULT now(),
  updated_at timestamp with time zone NOT NULL DEFAULT now(),
  access_token text,
  status text,
  CONSTRAINT integration_whatsapp_web_pkey PRIMARY KEY (id)
);
CREATE TABLE public.memory_states (
  project_id uuid NOT NULL,
  user_id text NOT NULL,
  id uuid NOT NULL DEFAULT uuid_generate_v4(),
  created_at timestamp with time zone DEFAULT CURRENT_TIMESTAMP,
  updated_at timestamp with time zone DEFAULT CURRENT_TIMESTAMP,
  state text NOT NULL,
  CONSTRAINT memory_states_pkey PRIMARY KEY (id),
  CONSTRAINT memory_states_project_id_fkey FOREIGN KEY (project_id) REFERENCES public.projects(project_id)
);
CREATE TABLE public.message_ai_metadata (
  id uuid NOT NULL,
  message_id uuid NOT NULL,
  type character varying NOT NULL CHECK (type::text = ANY (ARRAY['tool'::character varying::text, 'ai_tool'::character varying::text])),
  tool character varying,
  content text NOT NULL,
  input_tokens integer NOT NULL,
  output_tokens integer NOT NULL,
  duration double precision NOT NULL,
  call_timestamp timestamp without time zone DEFAULT CURRENT_TIMESTAMP,
  conversation_id uuid NOT NULL,
  CONSTRAINT message_ai_metadata_pkey PRIMARY KEY (id),
  CONSTRAINT message_ai_metadata_message_id_fkey FOREIGN KEY (message_id) REFERENCES public.messages(id)
);
CREATE TABLE public.messages (
  conversation_id uuid NOT NULL,
  project_id uuid NOT NULL,
  phone_number character varying NOT NULL,
  type character varying NOT NULL CHECK (type::text = ANY (ARRAY['human'::character varying, 'ai'::character varying]::text[])),
  content text NOT NULL,
  latency double precision,
  id uuid NOT NULL DEFAULT uuid_generate_v4(),
  has_context boolean DEFAULT false,
  created_at timestamp with time zone DEFAULT CURRENT_TIMESTAMP,
  username text,
  source_id text,
  source text,
  CONSTRAINT messages_pkey PRIMARY KEY (id),
  CONSTRAINT messages_project_id_fkey FOREIGN KEY (project_id) REFERENCES public.projects(project_id)
);
CREATE TABLE public.messenger_conversation_states (
  project_id uuid NOT NULL,
  page_id text NOT NULL,
  user_id text NOT NULL,
  id uuid NOT NULL DEFAULT uuid_generate_v4(),
  bot_active boolean DEFAULT true,
  last_updated timestamp with time zone DEFAULT CURRENT_TIMESTAMP,
  created_at timestamp with time zone DEFAULT CURRENT_TIMESTAMP,
  CONSTRAINT messenger_conversation_states_pkey PRIMARY KEY (id)
);
CREATE TABLE public.oauth_states (
  state character varying NOT NULL,
  project_id uuid NOT NULL,
  expires_at timestamp with time zone NOT NULL,
  id uuid NOT NULL DEFAULT gen_random_uuid(),
  created_at timestamp with time zone DEFAULT now(),
  CONSTRAINT oauth_states_pkey PRIMARY KEY (id),
  CONSTRAINT oauth_states_project_id_fkey FOREIGN KEY (project_id) REFERENCES public.projects(project_id)
);
CREATE TABLE public.products (
  title text NOT NULL,
  description text,
  content text,
  price numeric,
  sku text,
  category text,
  images jsonb,
  metadata jsonb,
  project_id uuid,
  id uuid NOT NULL DEFAULT uuid_generate_v4(),
  currency character varying DEFAULT 'CLP'::character varying,
  created_at timestamp with time zone DEFAULT timezone('America/Santiago'::text, now()),
  source_url text,
  embedding USER-DEFINED,
  tags ARRAY,
  CONSTRAINT products_pkey PRIMARY KEY (id)
);
CREATE TABLE public.projects (
  retriever_patterns jsonb DEFAULT '{"custom_patterns": [], "enabled_patterns": [], "disabled_patterns": []}'::jsonb,
  enabled_tools jsonb DEFAULT '[]'::jsonb,
  project_id uuid NOT NULL DEFAULT uuid_generate_v4(),
  created_at timestamp with time zone DEFAULT CURRENT_TIMESTAMP,
  updated_at timestamp with time zone DEFAULT CURRENT_TIMESTAMP,
  name character varying NOT NULL,
  description text,
  image character varying,
  user_id uuid,
  personality text,
  model text,
  instructions text,
  prompt_memory text,
  prompt text,
  favorite boolean DEFAULT false,
  CONSTRAINT projects_pkey PRIMARY KEY (project_id),
  CONSTRAINT projects_user_id_fkey FOREIGN KEY (user_id) REFERENCES auth.users(id)
);
CREATE TABLE public.projects_user (
  project_id uuid NOT NULL,
  user_id uuid NOT NULL,
  id uuid NOT NULL DEFAULT gen_random_uuid(),
  rol text NOT NULL DEFAULT 'viewer'::text CHECK (rol = ANY (ARRAY['owner'::text, 'editor'::text, 'viewer'::text])),
  CONSTRAINT projects_user_pkey PRIMARY KEY (id),
  CONSTRAINT projects_user_user_id_fkey FOREIGN KEY (user_id) REFERENCES auth.users(id),
  CONSTRAINT projects_user_project_id_fkey FOREIGN KEY (project_id) REFERENCES public.projects(project_id)
);
CREATE TABLE public.scraping_jobs (
  type character varying NOT NULL CHECK (type::text = ANY (ARRAY['full_site'::character varying, 'specific_urls'::character varying, 'websearch'::character varying, 'site_scraping'::character varying, 'product_scraping'::character varying, 'sitemap_scraping'::character varying]::text[])),
  base_url text NOT NULL,
  project_id uuid,
  title text,
  description text,
  current_step text,
  last_processed_url text,
  started_at timestamp with time zone,
  completed_at timestamp with time zone,
  estimated_completion timestamp with time zone,
  duration_seconds numeric,
  error_message text,
  id uuid NOT NULL DEFAULT uuid_generate_v4(),
  status character varying NOT NULL DEFAULT 'pending'::character varying CHECK (status::text = ANY (ARRAY['pending'::character varying, 'running'::character varying, 'paused'::character varying, 'completed'::character varying, 'failed'::character varying, 'cancelled'::character varying]::text[])),
  progress_percentage numeric DEFAULT 0.0 CHECK (progress_percentage >= 0.0 AND progress_percentage <= 100.0),
  total_urls_found integer DEFAULT 0,
  urls_processed integer DEFAULT 0,
  products_found integer DEFAULT 0,
  products_stored integer DEFAULT 0,
  errors_count integer DEFAULT 0,
  successful_urls jsonb DEFAULT '[]'::jsonb,
  failed_urls jsonb DEFAULT '[]'::jsonb,
  created_at timestamp with time zone DEFAULT now(),
  parameters jsonb DEFAULT '{}'::jsonb,
  metadata jsonb DEFAULT '{}'::jsonb,
  CONSTRAINT scraping_jobs_pkey PRIMARY KEY (id),
  CONSTRAINT scraping_jobs_project_id_fkey FOREIGN KEY (project_id) REFERENCES public.projects(project_id)
);
CREATE TABLE public.search_items (
  type text NOT NULL CHECK (type = ANY (ARRAY['product'::text, 'document'::text, 'faq'::text])),
  title text,
  description text,
  content text,
  embedding USER-DEFINED,
  price numeric,
  sku text,
  category text,
  images jsonb,
  filename text,
  question text,
  answer text,
  tags ARRAY,
  source_url text,
  metadata jsonb,
  project_id uuid,
  id uuid NOT NULL DEFAULT uuid_generate_v4(),
  currency character varying DEFAULT 'CLP'::character varying,
  created_at timestamp with time zone DEFAULT timezone('America/Santiago'::text, now()),
  stock numeric,
  CONSTRAINT search_items_pkey PRIMARY KEY (id)
);
CREATE TABLE public.token_metrics (
  project_id text NOT NULL,
  user_id text NOT NULL,
  conversation_id text NOT NULL,
  message_id text NOT NULL,
  timestamp timestamp with time zone NOT NULL,
  cost double precision,
  source text NOT NULL,
  id uuid NOT NULL DEFAULT gen_random_uuid(),
  tokens jsonb NOT NULL DEFAULT '{"input": 0, "tools": 0, "total": 0, "output": 0, "context": 0, "system_prompt": 0}'::jsonb,
  created_at timestamp with time zone DEFAULT now(),
  CONSTRAINT token_metrics_pkey PRIMARY KEY (id)
);
CREATE TABLE public.whatsapp_conversation_states (
  project_id uuid NOT NULL,
  business_account_id text NOT NULL,
  phone_number_id text NOT NULL,
  user_id text NOT NULL,
  id uuid NOT NULL DEFAULT uuid_generate_v4(),
  bot_active boolean DEFAULT true,
  last_updated timestamp with time zone DEFAULT CURRENT_TIMESTAMP,
  created_at timestamp with time zone DEFAULT CURRENT_TIMESTAMP,
  CONSTRAINT whatsapp_conversation_states_pkey PRIMARY KEY (id)
);
CREATE TABLE public.whatsapp_web_conversation_states (
  project_id uuid NOT NULL,
  business_account_id text NOT NULL,
  phone_number_id text NOT NULL,
  user_id text NOT NULL,
  id uuid NOT NULL DEFAULT uuid_generate_v4(),
  bot_active boolean DEFAULT true,
  last_updated timestamp with time zone DEFAULT CURRENT_TIMESTAMP,
  created_at timestamp with time zone DEFAULT CURRENT_TIMESTAMP,
  CONSTRAINT whatsapp_web_conversation_states_pkey PRIMARY KEY (id)
);