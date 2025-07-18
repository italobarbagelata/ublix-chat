CREATE OR REPLACE FUNCTION get_contact_field_config(project_uuid UUID)
RETURNS JSONB AS $$
DECLARE
    config JSONB := '{}';
    field_record RECORD;
BEGIN
    FOR field_record IN 
        SELECT field_name, keywords, field_type, description
        FROM contact_field_configs 
        WHERE project_id = project_uuid AND is_active = true
        ORDER BY priority ASC
    LOOP
        config := config || jsonb_build_object(
            field_record.field_name,
            jsonb_build_object(
                'keywords', field_record.keywords,
                'type', field_record.field_type,
                'description', field_record.description
            )
        );
    END LOOP;
    
    RETURN config;
END;
$$ LANGUAGE plpgsql;